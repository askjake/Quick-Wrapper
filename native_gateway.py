"""User-owned, no-admin local MCP gateway. Does not open any listener.

Native-local is intentionally distinct from SSH/Linux remote_agent. It uses the
same curated MCP proxy but executes it directly through the local Python venv.
"""
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

from model import validate_lambda_url, normalize_tools
from bootstrap_lib import FILES, PAYLOAD
from deploy_lib import DeploymentError

NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')


def native_root():
    """One predictable per-user root; never a system or application directory."""
    return Path.home() / 'AQ-MCP-Gateway'


def local_python(root):
    return root / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ensure_safe_root(root):
    if root.is_symlink() or not root.is_dir():
        raise DeploymentError('Native gateway is missing or is a symlink')
    if (root / 'targets.json').is_symlink():
        raise DeploymentError('Native registry must not be a symlink')


@contextlib.contextmanager
def exclusive_lock(root):
    """Advisory cross-platform exclusive file lock, shared by wizard transactions."""
    lock = root / '.wizard.lock'
    if lock.is_symlink():
        raise DeploymentError('Gateway lock must not be a symlink')
    with open(lock, 'a+b') as fh:
        fh.seek(0)
        if fh.read(1) == b'':
            fh.write(b'0'); fh.flush()
        fh.seek(0)
        if os.name == 'nt':
            import msvcrt
            # LK_LOCK waits for access; one byte at position zero.
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            try: yield
            finally:
                fh.seek(0); msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def atomic_write(path, data):
    """Create a user-owned temporary file adjacent to the destination, then replace."""
    fd, tmp = tempfile.mkstemp(prefix='.aq-wizard-', dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as fh:
            if os.name != 'nt': os.fchmod(fh.fileno(), 0o600)
            fh.write(data); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class NativeGateway:
    """Implements the same operation surface as SSHGateway for a local host."""
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else native_root()
        self.root = self.root.expanduser().absolute()
        self.registry = self.root / 'targets.json'
        self.backups = self.root / '.wizard-backups'

    def inspect(self):
        root = self.root
        if root.is_symlink():
            return {'state':'SYMLINK','installed':False}
        if not root.exists():
            return {'state':'MISSING','installed':False}
        if not root.is_dir():
            return {'state':'FOREIGN','installed':False}
        needed = ['aq_registry.py','aq_mcp_stdio.py','aq_check.py','targets.json',
                  'requirements-gateway.txt']
        missing = [x for x in needed if not (root/x).is_file() or (root/x).is_symlink()]
        if not local_python(root).is_file(): missing.append('venv/python')
        if missing: return {'state':'INCOMPLETE','installed':False,'missing':missing}
        if self.registry.is_symlink():return {'state':'SYMLINK','installed':False}
        try:
            data,raw,sha = self._load()
        except (ValueError, OSError, DeploymentError):
            return {'state':'INCOMPLETE','installed':False,'message':'Registry invalid'}
        return {'state':'READY','installed':True,'sha256':sha,
                'target_names':sorted(data['targets']),
                'kinds':{k:v.get('kind','remote') for k,v in data['targets'].items()},
                'git_targets':[], 'runtime':'NATIVE_LOCAL',
                'root':str(self.root), 'python':str(local_python(root)),
                'message':'User-owned native gateway; OS ACL policy requires separate review'}

    def _load(self):
        ensure_safe_root(self.root)
        raw = self.registry.read_bytes()
        if len(raw) > 1048576:raise DeploymentError('Registry exceeds 1 MiB')
        data=json.loads(raw.decode('utf-8'))
        if not isinstance(data,dict) or not isinstance(data.get('targets'),dict):
            raise DeploymentError('Registry missing targets object')
        return data,raw,digest(raw)

    def bootstrap(self, approved=False, install_dependencies=True):
        if not approved:raise DeploymentError('Explicit native-local installation approval required')
        if self.inspect().get('state')!='MISSING':
            raise DeploymentError('Create-only native bootstrap refuses existing gateway')
        if not install_dependencies:raise DeploymentError('Dependency installation approval missing')
        # Windows Python >=3.10 is required by the underlying MCP runtime.
        if sys.version_info < (3,10):raise DeploymentError('Python 3.10 or newer required')
        self.root.mkdir(mode=0o700,parents=False,exist_ok=False)
        try:
            for name in FILES:
                if name == 'aq-run.sh':continue  # never invoke Bash on Windows
                p=PAYLOAD/name
                if p.is_symlink() or not p.is_file():raise DeploymentError('Reviewed payload missing: '+name)
                dest=self.root/name
                with dest.open('xb') as fh: fh.write(p.read_bytes())
                if os.name!='nt':dest.chmod(0o600)
            atomic_write(self.registry,b'{"targets": {}}\n')
            subprocess.run([sys.executable,'-m','venv',str(self.root/'venv')],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           timeout=90,check=True)
            py=local_python(self.root)
            subprocess.run([str(py),'-m','pip','install','-r',
                            str(self.root/'requirements-gateway.txt')],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           timeout=300,check=True)
            subprocess.run([str(py),'-c','import mcp,botocore'],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           timeout=15,check=True)
        except Exception as exc:
            # Do NOT delete a partially installed gateway; never erase operator data.
            raise DeploymentError('Native bootstrap incomplete; inspect and reconcile before retrying. Cause: '+type(exc).__name__)
        return self.inspect()

    def _probe_entry(self,entry):
        # Only Lambda Function URLs; cannot probe arbitrary HTTP endpoints.
        url=entry['url']
        _host,region=validate_lambda_url(url)
        from remote_agent import _read_stdio_tools
        env=os.environ.copy()
        env.update(AQ_TARGET_URL=url.rstrip('/') if url.rstrip('/').endswith('/mcp') else url.rstrip('/')+'/mcp',
                   AQ_REGION=region,AQ_TOOL_ALLOWLIST=','.join(entry.get('allow') or []),
                   AQ_EXTRA_HEADERS='{}',AQ_FORCED_ARGS='{}',AQ_SECRET_ARGS='{}',
                   AQ_LOG_FILE=str(self.root/'aq-mcp.log'))
        return _read_stdio_tools([str(local_python(self.root)),str(self.root/'aq_mcp_stdio.py')],env)

    def run(self, request, timeout=65):
        op=request.get('op')
        if op=='inspect':return self.inspect()
        if op=='bootstrap':
            return self.bootstrap(approved=request.get('confirm')=='CREATE_FRESH_GATEWAY',
                                  install_dependencies=request.get('install_dependencies') is True)
        if op=='discover':
            if self.inspect()['state']!='READY':raise DeploymentError('Native gateway not READY')
            entry=request['entry']
            return self._probe_entry(dict(entry,allow=[]))
        if op=='inspect_lambda_target':
            data,raw,sha=self._load()
            name=request['target'];t=data['targets'].get(name)
            if t is None or t.get('kind','remote')!='remote':raise DeploymentError('Lambda target not found')
            return {'target':name,'url':t['url'],'allow':list(t.get('allow') or []),
                    'registry_sha256':sha,
                    'extra_config_present':[k for k in ('headers','forced_args','secret_args') if t.get(k)]}
        if op=='apply':return self._apply(request)
        if op=='rollback':return self._rollback(request['receipt'])
        if op=='check':
            data,_,_=self._load();t=data['targets'].get(request['target'])
            if not t:raise DeploymentError('Target not found')
            result=self._probe_entry(t)
            count=result['count'];expected=request.get('expected_allow_count')
            return {'ok':expected is None or count==expected,
                    'status':'OK' if expected is None or count==expected else 'FAIL',
                    'tool_count':count}
        if op=='probe_existing':
            raise DeploymentError('Native-local v0.4 supports new Lambda targets only; Git/local adapters remain Linux SSH')
        if op in ('git_check','repair_permissions'):
            raise DeploymentError('Unsupported native-local operation: '+op)
        raise DeploymentError('Unknown native-local operation')

    def _apply(self,request):
        from remote_agent import check_entry
        target=request['target']
        if not isinstance(target,str) or not NAME.fullmatch(target):raise DeploymentError('Invalid target')
        entry=dict(request['entry'])
        normalize_tools(entry.get('allow',[]))
        check_entry(target,entry)
        with exclusive_lock(self.root):
            data,old,sha=self._load()
            if sha!=request['expected_sha256']:raise DeploymentError('Registry changed; regenerate plan')
            if target in data['targets']:raise DeploymentError('Target already exists; never overwrite')
            self.backups.mkdir(mode=0o700,exist_ok=True)
            backup=self.backups/(sha+'-'+target+'.json')
            if backup.exists() or backup.is_symlink():raise DeploymentError('Backup already exists; investigate')
            with backup.open('xb') as fd:fd.write(old)
            if os.name!='nt':backup.chmod(0o600)
            if digest(self.registry.read_bytes())!=sha:
                raise DeploymentError('CONFLICT: external registry change before write')
            data['targets'][target]=entry
            new=(json.dumps(data,indent=2,sort_keys=True)+'\n').encode('utf-8')
            atomic_write(self.registry,new)
            return {'target':target,'before_sha256':sha,'after_sha256':digest(new),
                    'backup_file':str(backup),'status':'REGISTRY_UPDATED',
                    'gateway_kind':'NATIVE_LOCAL'}

    def _rollback(self,receipt):
        with exclusive_lock(self.root):
            data,current,sha=self._load()
            if sha != receipt.get('after_sha256'):
                raise DeploymentError('Registry changed since deployment; refuse unsafe rollback')
            name=receipt.get('target')
            if not isinstance(name,str) or not NAME.fullmatch(name):
                raise DeploymentError('Invalid rollback target')
            if not re.fullmatch(r'[0-9a-f]{64}',receipt.get('before_sha256','')):
                raise DeploymentError('Invalid rollback base hash')
            if name not in data['targets']:raise DeploymentError('Deployed target absent')
            backup=self.backups/(receipt['before_sha256']+'-'+name+'.json')
            if backup.is_symlink() or str(backup)!=receipt.get('backup_file'):
                raise DeploymentError('Invalid rollback backup identity')
            prior=backup.read_bytes()
            if digest(prior)!=receipt['before_sha256']:raise DeploymentError('Backup hash mismatch')
            atomic_write(self.registry,prior)
            return {'status':'ROLLED_BACK','target':name,'registry_sha256':digest(prior)}
