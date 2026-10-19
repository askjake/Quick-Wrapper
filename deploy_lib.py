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

from model import (validate_spec, make_registry_entry, plan, quick_connector,
                   backend_identity, risk_tool_names, identity_warnings, ValidationError)

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

    def bootstrap(self, approved=False):
        """Creates gateway only when absent. Requires explicit dependency-install consent."""
        if not approved:
            raise DeploymentError('Fresh gateway install requires explicit approval')
        state = self.inspect()
        if state.get('state') != 'MISSING':
            raise DeploymentError('Bootstrap refused: gateway is not absent (' + str(state.get('state')) + ')')
        from bootstrap_lib import make_bundle
        payload = make_bundle()
        reply = self.gateway.run(dict(op='bootstrap', confirm='CREATE_FRESH_GATEWAY',
                                      install_dependencies=True, **payload), timeout=490)
        after = self.inspect()
        if after.get('state') != 'READY':
            raise DeploymentError('Gateway bootstrap did not produce READY state; inspect manually')
        return reply

    def repair_permissions(self, observed, approved=False):
        if not approved:
            raise DeploymentError('Permission repair requires explicit approval')
        if observed.get('state') != 'PERMISSIONS_NEED_REPAIR':
            raise DeploymentError('Gateway is not in repairable permission state')
        result=self.gateway.run({'op':'repair_permissions',
                                 'confirm':'REPAIR_OWNED_CORE_PERMISSIONS',
                                 'mode_issues':observed['mode_issues']})
        if self.inspect().get('state')!='READY':
            raise DeploymentError('Permission repair incomplete; inspect before proceeding')
        return result

    def verify_backend(self, spec):
        """Live MCP metadata-only backend check. Does NOT execute application tools."""
        valid=dict(spec)
        if valid.get('kind')=='lambda':
            valid['allow']=['verification-placeholder']
        validate_spec(valid)
        state=self.inspect()
        if state.get('state')!='READY':
            raise DeploymentError('Gateway not READY; inspect gateway first: '+str(state.get('state')))
        kind=spec['kind']
        name=spec['target']
        installed=None
        if kind=='lambda':
            if name in state.get('target_names',[]):
                installed=self.gateway.run({'op':'inspect_lambda_target','target':name})
                if installed['url'].rstrip('/')!=spec['url'].rstrip('/'):
                    raise DeploymentError('This name already targets a DIFFERENT Lambda URL; refuse verification under the wrong label.')
            info=self.discover(valid)
            method='SigV4 Lambda Function URL -> MCP initialize/tools/list'
        else:
            if kind=='git':
                if name not in state.get('git_targets',[]):
                    raise DeploymentError('Git target is not configured on this gateway')
            elif name not in state.get('target_names',[]) or state.get('kinds',{}).get(name)!='local':
                raise DeploymentError('Selected local MCP target is not registered on gateway')
            info=self.gateway.run({'op':'probe_existing','kind':kind,'target':name},timeout=63)
            method=('Guarded Git MCP launcher -> initialize/tools/list' if kind=='git' else
                    'Existing local registry launcher -> initialize/tools/list')
        names=[t['name'] for t in info.get('tools',[])]
        if info.get('truncated') or info.get('count')!=len(names) or not names or len(set(names))!=len(names):
            raise DeploymentError('Incomplete or empty MCP tools/list result; backend not verified')
        return {'status':'BACKEND_VERIFIED', 'kind':kind,'target':name,
                'existing_target': installed is not None,
                'existing_allow': installed['allow'] if installed else None,
                'existing_extra_config_present': installed.get('extra_config_present',[]) if installed else [],
                'backend_identity_sha256':backend_identity(spec),
                'registry_sha256':state['sha256'],
                'handshake':method,'tool_count':len(names),'tools':info['tools'],
                'potentially_mutating_tools_name_only':risk_tool_names(names),
                'warnings':identity_warnings(spec,names),
                'qualification':'MCP metadata handshake only: no tool execution, no proof of write safety'}

    def prepare(self,spec):
        validate_spec(spec)
        info=self.inspect()
        if info.get('state')!='READY':
            raise DeploymentError('Gateway not ready: '+str(info.get('state'))+'. Inspect, bootstrap or repair permissions first.')
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
            installed=self.gateway.run({'op':'inspect_lambda_target','target':spec['target']})
            if installed.get('registry_sha256')!=info['sha256']:
                raise DeploymentError('Registry changed during inspection; replan')
            if installed['url'].rstrip('/')!=spec['url'].rstrip('/') or sorted(installed['allow'])!=sorted(spec['allow']):
                raise DeploymentError('Existing target differs in URL or allow-list; this wizard never overwrites it. Match the installed configuration or use a new target name.')
            result=plan(spec,info['sha256'])
            result['mode']='existing-target-registration-only'
            result['execution_plan']=['1. Confirm existing Lambda URL and allow-list match your selection.',
                '2. Validate the existing target through aq_check.py (tools/list only).',
                '3. Leave the registry and existing target UNCHANGED.',
                '4. Register the Local SSH connector manually in Quick.',
                '5. Start a new Quick chat and verify one harmless read.']
            result['warnings'].append('This target already exists: registration-only; no gateway files will be changed.')
            result['gateway']={'host':spec['host'],'user':spec['user']}
            return result
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
        if prepared.get('mode')=='existing-target-registration-only':
            current=self.inspect()
            if current.get('sha256')!=prepared.get('expected_registry_sha256'):
                raise DeploymentError('Registry changed since existing-target plan; replan')
            existing=self.gateway.run({'op':'inspect_lambda_target','target':spec['target']})
            if existing['url'].rstrip('/')!=spec['url'].rstrip('/') or sorted(existing['allow'])!=sorted(spec['allow']):
                raise DeploymentError('Installed target changed; no registration receipt produced')
            health=self.gateway.run({'op':'check','target':spec['target'],
                                     'expected_allow_count':len(spec['allow'])},timeout=70)
            if not health.get('ok'):
                raise DeploymentError('Existing target tools/list failed; no registry modifications attempted')
            return {'status':'EXISTING_TARGET_VERIFIED','target':spec['target'],
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
