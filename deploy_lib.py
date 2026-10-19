"""Transport and safe gateway transactions, Python 3.8+.

Paramiko is optional until a live SSH operation. Uses RejectPolicy only.
All fixed remote Python source is supplied as base64 code; request data travels via stdin.
No password/token authentication is implemented (SSH keys/agent only).
"""
import base64
import json
import os
import pathlib
import threading

from model import validate_spec, make_registry_entry, plan, quick_connector, ValidationError

HERE = pathlib.Path(__file__).resolve().parent

class DeploymentError(RuntimeError):
    pass


class SSHGateway(object):
    def __init__(self, host, user, known_hosts=None, timeout=15):
        self.host=host
        self.user=user
        self.known_hosts=known_hosts or os.path.expanduser('~/.ssh/known_hosts')
        self.timeout=timeout

    def run(self, request, timeout=65):
        try:
            import paramiko
        except ImportError:
            raise DeploymentError('Install Paramiko first: py -m pip install paramiko')
        if not os.path.isfile(self.known_hosts):
            raise DeploymentError('Known-hosts file is missing. Connect via trusted OpenSSH first; verify host fingerprint.')
        src=(HERE/'remote_agent.py').read_bytes()
        cmd='python3 -c "import base64;exec(base64.b64decode(\'{}\'))"'.format(base64.b64encode(src).decode('ascii'))
        client=paramiko.SSHClient()
        client.load_system_host_keys()
        client.load_host_keys(self.known_hosts)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            client.connect(self.host,username=self.user,timeout=self.timeout,auth_timeout=self.timeout,
                           banner_timeout=self.timeout,allow_agent=True,look_for_keys=True)
            inp,out,err=client.exec_command(cmd,timeout=timeout)
            payload=json.dumps(request,sort_keys=True)
            if len(payload)>262144:
                raise DeploymentError('Request exceeds safety size limit')
            inp.write(payload.encode('utf-8'))
            inp.flush()
            inp.channel.shutdown_write()
            raw=out.read(1024*1024)
            stderr=err.read(8192) # never echo stderr: may contain internal URLs
            status=out.channel.recv_exit_status()
            if status!=0:
                raise DeploymentError('Gateway worker exited with status {}'.format(status))
            data=json.loads(raw.decode('utf-8'))
            if not data.get('ok'):
                raise DeploymentError(data.get('error','Remote operation failed'))
            return data['result']
        except DeploymentError:
            raise
        except Exception as exc:
            # Paramiko error strings can disclose usernames and internal URLs; display type only.
            raise DeploymentError('SSH/transport failed ({}). Check trusted host key, SSH agent and connectivity.'.format(type(exc).__name__))
        finally:
            client.close()


class ConnectorDeployer(object):
    def __init__(self, gateway):
        self.gateway=gateway

    def inspect(self):
        return self.gateway.run({'op':'inspect'})

    def prepare(self,spec):
        validate_spec(spec)
        info=self.inspect()
        if spec['kind']=='git':
            if spec['target'] not in info['git_targets']:
                raise DeploymentError('Git target is not installed/configured on the gateway')
            result=self.gateway.run({'op':'git_check','target':spec['target']})
            if not result.get('ok'):
                raise DeploymentError('Git launcher preflight failed. Check target configuration and token file mode.')
        elif spec['kind']=='local':
            if spec['target'] not in info['target_names'] or info['kinds'].get(spec['target'])!='local':
                raise DeploymentError('MVP Local mode supports registration of an EXISTING local registry target only')
            result=self.gateway.run({'op':'check','target':spec['target']})
            if not result.get('ok'):
                raise DeploymentError('Local target tools/list health check failed')
        elif spec['target'] in info['target_names']:
            raise DeploymentError('Target already exists; this release does not overwrite registry targets')
        result=plan(spec,info['sha256'])
        result['gateway']={'host':spec['host'],'user':spec['user']}
        return result

    def discover(self,spec):
        validate_spec(dict(spec,allow=spec.get('allow') or ['discovery-placeholder']))
        if spec['kind']!='lambda':
            raise DeploymentError('MVP live discovery supports AWS Lambda Function URLs only')
        return self.gateway.run({'op':'discover','entry':make_registry_entry(dict(spec,allow=['discovery-placeholder']))},timeout=55)

    def deploy(self,spec,prepared,confirm):
        validate_spec(spec)
        if not confirm:
            raise DeploymentError('Explicit deploy approval is required')
        if (prepared.get('target')!=spec['target'] or prepared.get('kind')!=spec['kind'] or
                prepared.get('gateway')!={'host':spec['host'],'user':spec['user']}):
            raise DeploymentError('Plan and target no longer match')
        if spec['kind']!='lambda':
            # Git / local adapter only tests existing installation: no remote writes.
            return {'status':'EXISTING_TARGET_ONLY','target':spec['target'],
                    'registration':'MANUAL_REQUIRED','quick_connector':quick_connector(spec)}
        entry=make_registry_entry(spec)
        # Re-discover using IAM on the actual gateway just before any registry change.
        offered=self.discover(spec)
        names={t['name'] for t in offered['tools']}
        if offered.get('truncated') or not set(spec['allow']).issubset(names):
            raise DeploymentError('Tool discovery incomplete or selected tool absent: no deployment')
        if entry!=prepared.get('registry_entry'):
            raise DeploymentError('Plan differs from current form; preview again')
        receipt=self.gateway.run({'op':'apply','target':spec['target'],'entry':entry,
                                 'expected_sha256':prepared['expected_registry_sha256']})
        try:
            check=self.gateway.run({'op':'check','target':spec['target'],
                                    'expected_allow_count':len(entry['allow'])},timeout=70)
            if not check.get('ok'):
                raise DeploymentError('Gateway MCP health check failed; auto-rollback requested')
        except Exception as exc:
            try:
                self.gateway.run({'op':'rollback','receipt':receipt})
            except Exception as rollback_exc:
                raise DeploymentError('Health check failed AND rollback was blocked; inspect registry before retrying. Original: {}; rollback: {}'.format(str(exc),str(rollback_exc)))
            raise DeploymentError('Health check failed; registry was safely rolled back. '+str(exc))
        receipt['status']='GATEWAY_VERIFIED'
        receipt['registration']='MANUAL_REQUIRED'
        receipt['quick_connector']=quick_connector(spec)
        return receipt

    def rollback(self,receipt):
        return self.gateway.run({'op':'rollback','receipt':receipt})
