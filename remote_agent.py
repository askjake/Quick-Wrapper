"""Fixed, tightly scoped, self-contained remote worker (stdlib Python 3.8+).

Executed over a strictly authenticated SSH connection. No arbitrary shell/file paths
come from the user. Input is one JSON request through stdin, output one JSON reply.
Only Lambda registry creation is allowed; Git/Local are inspect-only.
"""
import hashlib
import json
import os
import pathlib
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
import io
import shutil
import zipfile
import base64
from urllib.parse import urlsplit

ROOT = pathlib.Path.home() / 'aq-mcp'
REG = ROOT / 'targets.json'
LOCK = ROOT / '.aq-wizard.lock'
BACKUPS = ROOT / '.wizard-backups'
NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
URL = re.compile(r'^https://[a-z0-9]+\.lambda-url\.([a-z0-9-]+)\.on\.aws(?:/mcp|/)?$')
TOOLS = re.compile(r'^[A-Za-z0-9_.:/-]{1,128}$')


def fail(msg):
    raise ValueError(msg)


def own_uid():
    # On a Windows test runner, POSIX ownership is unavailable. Never used on
    # remote Linux bootstrap/apply because the remote entrypoint requires POSIX.
    return os.geteuid() if hasattr(os, 'geteuid') else None


def is_owned(path):
    uid = own_uid()
    return uid is None or path.stat().st_uid == uid


def runtime_warnings():
    # Read-only observation only: do NOT recursively chmod a shared venv.
    result=[]
    candidates=[ROOT/'venv', ROOT/'venv/bin', ROOT/'venv/lib']
    lib=ROOT/'venv/lib'
    if lib.is_dir():
        for candidate in sorted(lib.glob('python*/site-packages')):
            candidates.append(candidate)
    for path in candidates:
        try:
            if path.is_dir() and (path.stat().st_mode & 0o022):
                result.append({'path':str(path.relative_to(ROOT)),
                               'mode':oct(path.stat().st_mode & 0o777)})
        except (OSError,ValueError):
            continue
    return result

def gateway_state():
    if os.name != 'posix':
        return {'state':'UNSUPPORTED_OS','installed':False,'message':'Gateway requires Linux'}
    if ROOT.is_symlink():
        return {'state':'SYMLINK','installed':False,'message':'Refusing symlink gateway'}
    if not ROOT.exists():
        return {'state':'MISSING','installed':False,'message':'Gateway can be bootstrapped'}
    if not ROOT.is_dir() or not is_owned(ROOT):
        return {'state':'FOREIGN','installed':False,'message':'Gateway is not an owned directory'}
    required=('aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py','targets.json','venv/bin/python')
    missing=[name for name in required if not (ROOT/name).is_file() or (ROOT/name).is_symlink()]
    # The venv/bin/python executable is commonly a symlink to the venv/system python.
    missing=[name for name in missing if name!='venv/bin/python' or not (ROOT/name).exists()]
    if missing:
        return {'state':'INCOMPLETE','installed':False,'missing':missing,
                'message':'Existing incomplete gateway: refusing to replace or bootstrap over it'}
    relevant=('targets.json','aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py')
    issues=[]
    if ROOT.stat().st_mode & 0o022:issues.append({'file':'aq-mcp/','mode':oct(ROOT.stat().st_mode & 0o777)})
    for name in relevant:
        path=ROOT/name
        if path.is_symlink() or not is_owned(path):
            return {'state':'FOREIGN','installed':False,'message':'Unowned/symlink core file: '+name}
        if path.stat().st_mode & 0o022:
            issues.append({'file':name,'mode':oct(path.stat().st_mode & 0o777)})
    if issues:
        return {'state':'PERMISSIONS_NEED_REPAIR','installed':True,'mode_issues':issues,
                'runtime_warnings':runtime_warnings(),
                'message':'Read-only inspection is allowed; apply requires explicit core-file permission repair'}
    return {'state':'READY','installed':True,
            'runtime_warnings':runtime_warnings(),
            'message':'Core permissions pass; review any separately listed venv permission warnings'}


def good_root():
    if ROOT.is_symlink() or not ROOT.is_dir(): fail('Gateway installation is absent or is a symlink')
    if not is_owned(ROOT): fail('Gateway root is not owned by SSH user')
    if ROOT.stat().st_mode & 0o022:fail('Gateway directory has unsafe write permissions; use explicit permission repair')
    if REG.is_symlink() or not REG.is_file() or not is_owned(REG):
        fail('Missing, unowned or symlinked targets.json')
    for f in ('aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py'):
        if not (ROOT / f).is_file() or (ROOT/f).is_symlink(): fail('Required gateway component missing/unsafe: '+f)
    for f in ('targets.json','aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py'):
        if (ROOT/f).stat().st_mode & 0o022:fail('Core file is group/world-writable: '+f)


def load_reg():
    good_root()
    data = REG.read_bytes()
    try: r=json.loads(data.decode('utf-8'))
    except Exception: fail('Registry is not valid UTF-8 JSON')
    if not isinstance(r,dict) or not isinstance(r.get('targets'),dict):fail('Malformed registry schema')
    return r,data,hashlib.sha256(data).hexdigest()


def check_entry(name, entry):
    if not isinstance(name,str) or not NAME.fullmatch(name): fail('Invalid registry target name')
    if not isinstance(entry,dict): fail('Invalid registry entry')
    url=entry.get('url')
    if not isinstance(url,str) or not URL.fullmatch(url): fail('Only strict AWS Lambda Function URLs are permitted')
    items=entry.get('allow')
    if not isinstance(items,list) or not items or len(items)>300 or len(items)!=len(set(items)):
        fail('Nonempty, unique allow-list required')
    if any(not isinstance(t,str) or not TOOLS.fullmatch(t) for t in items):fail('Invalid tool name')
    if set(entry)-{'url','region','env','note','allow'}:fail('Unexpected registry fields')
    region=URL.fullmatch(url).group(1)
    if entry.get('region')!=region:fail('Region mismatch')
    if len(json.dumps(entry))>32768:fail('Entry too large')


def safe_info():
    state=gateway_state()
    if not state['installed']:
        return state
    if state['state'] not in ('READY','PERMISSIONS_NEED_REPAIR'):
        return state
    # Inspection is allowed when the owner has an older group-writable install.
    # Mutations still require good_root(), enforced by apply/rollback.
    data=REG.read_bytes()
    r=json.loads(data.decode('utf-8'))
    if not isinstance(r,dict) or not isinstance(r.get('targets'),dict):
        fail('Malformed registry')
    sha=hashlib.sha256(data).hexdigest()
    git=[]
    gp=ROOT/'git_targets.json'
    if gp.is_file() and not gp.is_symlink():
        try:git=sorted(json.loads(gp.read_text()).get('targets',{}))
        except Exception: pass
    return dict(state,sha256=sha,target_names=sorted(r['targets']),
            kinds={n:(t.get('kind') or 'remote') for n,t in r['targets'].items()},
            allow_counts={n:len(t.get('allow') or []) for n,t in r['targets'].items()},
            git_targets=git, local_servers=['aq_build_artifacts_mcp.py'])


def atomic_replace(path, content):
    fd, tmp=tempfile.mkstemp(prefix='.aq-wizard-',dir=str(ROOT))
    try:
        with os.fdopen(fd,'wb') as fh:
            fh.write(content); fh.flush(); os.fsync(fh.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,str(path))
        df=os.open(str(ROOT),os.O_RDONLY)
        try:os.fsync(df)
        finally:os.close(df)
    finally:
        if os.path.lexists(tmp): os.unlink(tmp)


def apply(req):
    name,entry=req.get('target'),req.get('entry')
    check_entry(name,entry)
    expect=req.get('expected_sha256')
    if not isinstance(expect,str) or not re.fullmatch(r'[a-f0-9]{64}',expect):fail('Missing plan base SHA')
    good_root()
    fd=os.open(str(LOCK),os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        import fcntl
        fcntl.flock(fd,fcntl.LOCK_EX)
        r,b,sha=load_reg()
        if sha!=expect:fail('CONFLICT: registry changed since preview; replan before applying')
        if name in r['targets']:fail('Target already exists; wizard never overwrites an existing target')
        r['targets'][name]=entry
        encoded=(json.dumps(r,indent=2,sort_keys=True,ensure_ascii=True)+'\n').encode('utf-8')
        # Verify valid registry and environment WITHOUT starting a live tool call.
        json.loads(encoded)
        BACKUPS.mkdir(mode=0o700,exist_ok=True)
        if (BACKUPS.is_symlink() or not is_owned(BACKUPS) or
                BACKUPS.stat().st_mode & 0o077):fail('Unsafe backup directory')
        backup_name='targets-{}-{}-{}.json'.format(int(time.time()),secrets.token_hex(6),sha[:12])
        backup=BACKUPS/backup_name
        bfd=os.open(str(backup),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(bfd,'wb') as fh:fh.write(b);fh.flush();os.fsync(fh.fileno())
        if hashlib.sha256(REG.read_bytes()).hexdigest()!=sha:fail('CONFLICT: external registry modification')
        atomic_replace(REG,encoded)
        new_sha=hashlib.sha256(encoded).hexdigest()
        return {'status':'DEPLOYED_PENDING_CHECK','target':name,'before':sha,'after':new_sha,
                'backup_name':backup_name,'entry_sha256':hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest()}
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN); os.close(fd)


def rollback(req):
    receipt=req.get('receipt') or {}
    name=receipt.get('backup_name','')
    if not isinstance(name,str) or not re.fullmatch(r'targets-[0-9]+-[a-f0-9]{12}-[a-f0-9]{12}\.json',name):
        fail('Invalid rollback receipt/backup name')
    good_root()
    fd=os.open(str(LOCK),os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        import fcntl
        fcntl.flock(fd,fcntl.LOCK_EX)
        r,now,sha=load_reg()
        if sha != receipt.get('after'):fail('ROLLBACK CONFLICT: registry has changed since deployment')
        path=BACKUPS/name
        if path.is_symlink() or not path.is_file() or not is_owned(path):fail('Backup missing/unsafe')
        previous=path.read_bytes()
        if hashlib.sha256(previous).hexdigest()!=receipt.get('before'):fail('Backup SHA mismatch')
        atomic_replace(REG,previous)
        return {'status':'ROLLED_BACK','sha256':hashlib.sha256(previous).hexdigest()}
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)


def inspect_lambda_target(target):
    """Read the URL and exact allow-list for ONE existing remote Lambda target.
    Do not return forced args, secret file references, headers or other settings.
    """
    if not isinstance(target,str) or not NAME.fullmatch(target):fail('Invalid target')
    registry,_,sha=load_reg()
    entry=registry['targets'].get(target)
    if not isinstance(entry,dict) or entry.get('kind','remote')!='remote':
        fail('Not an existing Lambda remote target')
    url=entry.get('url')
    if not isinstance(url,str) or not URL.fullmatch(url):fail('Target is not a verified Lambda URL')
    allow=entry.get('allow')
    if not isinstance(allow,list) or not allow or any(not isinstance(t,str) or not TOOLS.fullmatch(t) for t in allow):
        fail('Existing target has no explicit valid allow-list; manual review required')
    if len(allow)!=len(set(allow)):fail('Duplicate tool names in target allow-list')
    return {'target':target,'url':url,'region':entry.get('region'),
            'allow':sorted(allow),'registry_sha256':sha,
            'extra_config_present':sorted(set(entry)-{'url','region','allow','env','note','kind'})}


def _read_stdio_tools(command, env=None, deadline_seconds=42):
    """Metadata-only MCP initialize/tools/list; no application tool calls.

    Command is fully server-selected; never constructed from arbitrary client scripts.
    Starting an installed local/Git MCP server may perform its own initialization.
    """
    import queue
    import threading
    msgs=[{'jsonrpc':'2.0','id':1,'method':'initialize',
           'params':{'protocolVersion':'2025-06-18','capabilities':{},
                     'clientInfo':{'name':'aq-wizard','version':'0.3'}}},
          {'jsonrpc':'2.0','method':'notifications/initialized'},
          {'jsonrpc':'2.0','id':2,'method':'tools/list'}]
    proc=subprocess.Popen(command,env=env,stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    q=queue.Queue()
    def drain():
        total=0
        try:
            for line in proc.stdout:
                total+=len(line)
                if total>1500000:
                    q.put({'failure':'Oversize tools/list response'});break
                try:q.put(json.loads(line))
                except (ValueError,UnicodeError):continue
        finally:q.put({'closed':True})
    threading.Thread(target=drain,daemon=True).start()
    threading.Thread(target=lambda:proc.stderr.read(),daemon=True).start()
    try:
        for message in msgs:
            proc.stdin.write((json.dumps(message)+'\n').encode('utf-8'))
            proc.stdin.flush()
        deadline=time.monotonic()+deadline_seconds
        while time.monotonic()<deadline:
            try:response=q.get(timeout=min(.4,max(.01,deadline-time.monotonic())))
            except queue.Empty:continue
            if not isinstance(response,dict):continue
            if response.get('failure'):fail(response['failure'])
            if response.get('closed'):break
            if response.get('id')==2:
                if 'error' in response:fail('Backend rejected MCP tools/list; inspect server logs and credentials')
                offered=response.get('result',{}).get('tools',[])
                if not isinstance(offered,list):fail('MCP tools/list is not a list')
                clean=[]
                for item in offered:
                    if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not TOOLS.fullmatch(item['name']):
                        fail('Backend advertised invalid tool name; cannot qualify')
                    clean.append({'name':item['name'], 'description':str(item.get('description') or '')[:240]})
                if len(clean)>300 or len({t['name'] for t in clean})!=len(clean):
                    fail('Backend tool list is too large or contains duplicate names')
                return {'tools':clean,'count':len(clean),'truncated':False}
        fail('No valid MCP tools/list response; check backend identity and credentials')
    finally:
        try:proc.stdin.close()
        except (OSError,ValueError):pass
        try:proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait()
        try:proc.stdout.close();proc.stderr.close()
        except (OSError,ValueError):pass


def probe_tools(entry):
    # For Lambda verification, run the actual SigV4 proxy with allow-list unset.
    check_entry('wizard-discovery',dict(entry,allow=['temporary-discovery-placeholder']))
    url=entry['url'].rstrip('/')
    if not url.endswith('/mcp'):url+='/mcp'
    env=os.environ.copy()
    env.update(AQ_TARGET_URL=url,AQ_REGION=entry['region'],AQ_TOOL_ALLOWLIST='',
               AQ_EXTRA_HEADERS='{}',AQ_FORCED_ARGS='{}',AQ_SECRET_ARGS='{}')
    return _read_stdio_tools([str(ROOT/'venv/bin/python'),str(ROOT/'aq_mcp_stdio.py')],env)


def probe_existing(kind,target):
    """Validate actual registered Git/local launcher with MCP metadata handshake."""
    good_root()
    if not isinstance(target,str) or not NAME.fullmatch(target):fail('Invalid target name')
    if kind=='git':
        if target not in ('github-ghes','gitlab'):fail('Unapproved Git target')
        path=ROOT/'git_targets.json'
        if path.is_symlink() or not path.is_file() or not is_owned(path):fail('Git targets configuration missing or unsafe')
        configured=json.loads(path.read_text('utf-8')).get('targets',{})
        if target not in configured:fail('Git target not configured')
        if not (ROOT/'aq_git_run.py').is_file() or not (ROOT/'aq_git_guard.py').is_file():
            fail('Git launcher or guard missing')
        command=[str(ROOT/'venv/bin/python'),str(ROOT/'aq_git_run.py'),target]
    elif kind=='local':
        data,_,_=load_reg()
        if target not in data['targets'] or data['targets'][target].get('kind')!='local':
            fail('Local server target is not already configured')
        command=[str(ROOT/'venv/bin/python'),str(ROOT/'aq_registry.py'),'run',target]
    else:fail('Unsupported existing backend kind')
    return _read_stdio_tools(command)


def check_target(target,expected_count=None):
    if not NAME.fullmatch(target or ''):fail('Invalid target')
    p=subprocess.run([str(ROOT/'venv/bin/python'),str(ROOT/'aq_check.py'),target],
                     stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=55)
    # aq_check.py prints a list row of the form: name  env  OK  0.3s  N tools.
    # Verify the exact filtered tool count, not just a successful process exit.
    output=p.stdout.decode('utf-8',errors='replace')
    m=re.search(r'\bOK\b[^\n]*?\b([0-9]+)\s+tools\b',output)
    observed=int(m.group(1)) if m else None
    success=(p.returncode==0 and observed is not None and
             (expected_count is None or observed==expected_count))
    return {'ok':success,'status':'OK' if success else 'FAIL',
            'tool_count':observed,
            'hint':'MCP tools/list failed or did not match approved tool count' if not success else 'tools/list succeeded'}


def git_check(target):
    if target not in ('github-ghes','gitlab'):fail('Invalid Git target')
    p=subprocess.run([str(ROOT/'venv/bin/python'),str(ROOT/'aq_git_run.py'),'--check',target],
                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=25)
    return {'ok':p.returncode==0,'status':'CONFIG_OK' if p.returncode==0 else 'CONFIG_FAILED'}


# A bootstrap is an opt-in, create-only operation. It never updates or replaces an
# existing root, even if that root is incomplete/unsafe. Dependency install uses
# the jump host's configured pip index, requires network access, and never reads
# or stores PATs or AWS credentials.
BOOTSTRAP_FILES = ('aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py','requirements-gateway.txt')

def bootstrap(req):
    if os.name != 'posix':fail('Bootstrap is Linux-only')
    if sys.version_info < (3,10):fail('Bootstrap requires Linux Python 3.10+')
    if ROOT.exists() or ROOT.is_symlink():fail('Gateway path exists: bootstrap never overwrites')
    if req.get('confirm') != 'CREATE_FRESH_GATEWAY':fail('Explicit bootstrap approval missing')
    if req.get('install_dependencies') is not True:fail('Approve dependency installation explicitly')
    bundle=req.get('bundle_b64')
    if not isinstance(bundle,str) or len(bundle)>150000:fail('Bundle missing/oversize')
    raw=base64.b64decode(bundle,validate=True)
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=req.get('bundle_sha256'):fail('Bundle checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sorted(z.namelist())!=sorted(BOOTSTRAP_FILES):fail('Unexpected bootstrap contents')
        contents={}
        for name in BOOTSTRAP_FILES:
            member=z.getinfo(name)
            if member.file_size>100000 or ((member.external_attr>>16)&0o170000)==0o120000:
                fail('Unsafe bootstrap member')
            contents[name]=z.read(name)
        pinned=b'mcp==2.3.0\nbotocore==1.43.113\nhttpx2==2.13.1'
        if pinned not in contents['requirements-gateway.txt']:
            fail('Unrecognized dependency contract')
    # Only one new installation in this user's home can start at once.
    if not is_owned(ROOT.parent):fail('Home directory not owned by current user')
    stage=pathlib.Path(tempfile.mkdtemp(prefix='.aq-mcp-stage-',dir=str(ROOT.parent)))
    os.chmod(stage,0o700)
    try:
        for name,content in contents.items():
            (stage/name).write_bytes(content)
            os.chmod(stage/name,0o700 if name=='aq-run.sh' else 0o600)
        (stage/'targets.json').write_text('{"targets":{}}\n',encoding='utf-8')
        os.chmod(stage/'targets.json',0o600)
        proc=subprocess.run([sys.executable,'-m','venv',str(stage/'venv')],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
        if proc.returncode!=0:fail('Could not create Python venv (install python3-venv)')
        proc=subprocess.run([str(stage/'venv/bin/python'),'-m','pip','install',
            '--disable-pip-version-check','--no-input','-r',str(stage/'requirements-gateway.txt')],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300)
        if proc.returncode!=0:fail('Dependency install failed; check jump-server package index or connectivity')
        verify=subprocess.run([str(stage/'venv/bin/python'),'-c',
            'import mcp, botocore, httpx2'],stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,timeout=25)
        if verify.returncode!=0:fail('Dependency import validation failed')
        # mkdir is exclusive: unlike os.rename(stage, ROOT), it CANNOT replace
        # another actor's freshly created empty gateway directory.
        try:
            os.mkdir(str(ROOT),0o700)
        except FileExistsError:
            fail('Gateway appeared during staged install; no files overwritten')
        try:
            for source in stage.iterdir():
                os.rename(str(source),str(ROOT/source.name))
        except Exception:
            fail('File activation incomplete; gateway left private/incomplete. Inspect before manual cleanup.')
        return {'status':'BOOTSTRAPPED','installed':True,'state':'READY',
                'gateway_root':'~/aq-mcp','registry_targets':0,'bundle_sha256':sha,
                'aws_credentials':'NOT_INSTALLED','quick_registration':'MANUAL_REQUIRED'}
    finally:
        if stage.exists():shutil.rmtree(str(stage))

def repair_permissions(req):
    state=gateway_state()
    if state['state']!='PERMISSIONS_NEED_REPAIR':fail('Not an owned existing gateway needing repair')
    if req.get('confirm')!='REPAIR_OWNED_CORE_PERMISSIONS':fail('Explicit permission repair approval missing')
    observed=req.get('mode_issues')
    if observed!=state['mode_issues']:fail('Permissions changed since inspection; re-inspect')
    paths=[ROOT if x['file']=='aq-mcp/' else ROOT/x['file'] for x in observed]
    for path in paths:
        if path.is_symlink() or not is_owned(path):fail('Unsafe core path; no changes applied')
    changed=[]
    for path in paths:
        old=path.stat().st_mode & 0o777
        os.chmod(str(path),old & ~0o022)
        changed.append({'file':'aq-mcp/' if path==ROOT else path.name,'before':oct(old),'after':oct(old & ~0o022)})
    return {'status':'PERMISSIONS_REPAIRED','changes':changed,'state':gateway_state()['state']}

def main(req):
    op=req.get('op')
    if op=='inspect': return safe_info()
    if op=='bootstrap': return bootstrap(req)
    if op=='repair_permissions': return repair_permissions(req)
    if op=='discover':return probe_tools(req['entry'])
    if op=='probe_existing':return probe_existing(req['kind'],req['target'])
    if op=='inspect_lambda_target':return inspect_lambda_target(req['target'])
    if op=='apply':return apply(req)
    if op=='rollback':return rollback(req)
    if op=='check':return check_target(req['target'],req.get('expected_allow_count'))
    if op=='git_check':return git_check(req['target'])
    fail('Unsupported remote operation')

if __name__=='__main__':
    try:
        request=json.loads(sys.stdin.read(262144))
        result={'ok':True,'result':main(request)}
    except Exception as exc:
        result={'ok':False,'error':type(exc).__name__+': '+str(exc)[:220]}
    sys.stdout.write(json.dumps(result,separators=(',',':'))+'\n')
