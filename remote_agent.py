"""Fixed, tightly scoped, self-contained remote worker (stdlib Python 3.8+).

Executed over a strictly authenticated SSH connection. No arbitrary shell/file paths
come from the user. Input is one JSON request through stdin, output one JSON reply.
Only Lambda registry creation is allowed; Git/Local are inspect-only.
"""
import fcntl
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


def good_root():
    if ROOT.is_symlink() or not ROOT.is_dir(): fail('Gateway installation is absent or is a symlink')
    if ROOT.stat().st_uid != os.geteuid(): fail('Gateway root is not owned by SSH user')
    if ROOT.stat().st_mode & 0o022:fail('Gateway directory has unsafe write permissions')
    if REG.is_symlink() or not REG.is_file() or REG.stat().st_uid != os.geteuid():
        fail('Missing, unowned or symlinked targets.json')
    for f in ('aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py'):
        if not (ROOT / f).is_file(): fail('Required gateway component missing: '+f)


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
    r,b,sha=load_reg()
    git=[]
    gp=ROOT/'git_targets.json'
    if gp.is_file() and not gp.is_symlink():
        try:git=sorted(json.loads(gp.read_text()).get('targets',{}))
        except Exception: pass
    return {'sha256':sha,'target_names':sorted(r['targets']),
            'kinds':{n:(t.get('kind') or 'remote') for n,t in r['targets'].items()},
            'allow_counts':{n:len(t.get('allow') or []) for n,t in r['targets'].items()},
            'git_targets':git, 'local_servers':['aq_build_artifacts_mcp.py']}


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
    fd=os.open(str(LOCK),os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        r,b,sha=load_reg()
        if sha!=expect:fail('CONFLICT: registry changed since preview; replan before applying')
        if name in r['targets']:fail('Target already exists; wizard never overwrites an existing target')
        r['targets'][name]=entry
        encoded=(json.dumps(r,indent=2,sort_keys=True,ensure_ascii=True)+'\n').encode('utf-8')
        # Verify valid registry and environment WITHOUT starting a live tool call.
        json.loads(encoded)
        BACKUPS.mkdir(mode=0o700,exist_ok=True)
        if (BACKUPS.is_symlink() or BACKUPS.stat().st_uid!=os.geteuid() or
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
    fd=os.open(str(LOCK),os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        r,now,sha=load_reg()
        if sha != receipt.get('after'):fail('ROLLBACK CONFLICT: registry has changed since deployment')
        path=BACKUPS/name
        if path.is_symlink() or not path.is_file() or path.stat().st_uid!=os.geteuid():fail('Backup missing/unsafe')
        previous=path.read_bytes()
        if hashlib.sha256(previous).hexdigest()!=receipt.get('before'):fail('Backup SHA mismatch')
        atomic_replace(REG,previous)
        return {'status':'ROLLED_BACK','sha256':hashlib.sha256(previous).hexdigest()}
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)


def probe_tools(entry):
    # For discovery only: no call_tool. This uses the real SigV4 proxy and 3090 credentials.
    check_entry('wizard-discovery',dict(entry,allow=['temporary-discovery-placeholder']))
    url=entry['url'].rstrip('/')
    if not url.endswith('/mcp'): url+='/mcp'
    env=os.environ.copy()
    env.update(AQ_TARGET_URL=url,AQ_REGION=entry['region'],AQ_TOOL_ALLOWLIST='',
               AQ_EXTRA_HEADERS='{}',AQ_FORCED_ARGS='{}',AQ_SECRET_ARGS='{}')
    messages=[{'jsonrpc':'2.0','id':1,'method':'initialize',
               'params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'aq-wizard','version':'0.1'}}},
              {'jsonrpc':'2.0','method':'notifications/initialized'},
              {'jsonrpc':'2.0','id':2,'method':'tools/list'}]
    import queue
    import threading
    proc=subprocess.Popen([str(ROOT/'venv/bin/python'),str(ROOT/'aq_mcp_stdio.py')],
                          env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    q=queue.Queue()
    stdout_total=[0]
    def consume_stdout():
        try:
            for line in proc.stdout:
                stdout_total[0]+=len(line)
                if stdout_total[0]>1500000:
                    q.put({'failure':'Oversize tool-list response'});break
                try: q.put(json.loads(line))
                except Exception: continue
        finally:q.put({'closed':True})
    threading.Thread(target=consume_stdout,daemon=True).start()
    # Capture/discard stderr so the child can't block on a full stderr pipe.
    threading.Thread(target=lambda:proc.stderr.read(),daemon=True).start()
    try:
        for m in messages:
            proc.stdin.write((json.dumps(m)+'\n').encode());proc.stdin.flush()
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            try:msg=q.get(timeout=0.4)
            except queue.Empty:
                if proc.poll() is not None:break
                continue
            if msg.get('failure'):fail(msg['failure'])
            if msg.get('closed'):break
            if msg.get('id')==2:
                if 'error' in msg:fail('MCP tools/list failed; check gateway logs and AWS credentials')
                offered=msg.get('result',{}).get('tools',[])
                if not isinstance(offered,list):fail('Invalid tools/list response')
                clean=[]
                for t in offered[:300]:
                    n=t.get('name') if isinstance(t,dict) else None
                    if isinstance(n,str) and TOOLS.fullmatch(n):
                        clean.append({'name':n,'description':str(t.get('description') or '')[:240]})
                return {'tools':clean,'count':len(offered),'truncated':len(offered)>300}
        fail('No MCP tools/list response. Verify URL, AWS credentials, and ~/aq-mcp/aq-mcp.log')
    finally:
        try:proc.stdin.close()
        except Exception:pass
        try:proc.wait(timeout=2)
        except Exception:
            proc.kill();proc.wait()
        try:proc.stdout.close();proc.stderr.close()
        except Exception:pass


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


def main(req):
    op=req.get('op')
    if op=='inspect': return safe_info()
    if op=='discover':return probe_tools(req['entry'])
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
