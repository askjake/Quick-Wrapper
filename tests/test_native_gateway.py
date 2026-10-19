"""Native localhost gateway tests: mock package install, never use real AWS."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deploy_lib import ConnectorDeployer, DeploymentError
from model import validate_spec, quick_connector, backend_identity, ValidationError
import native_gateway

SPEC={'host':'127.0.0.1','user':'local','transport':'native-local','kind':'lambda',
      'target':'rtr-demo','display_name':'Native RTR Demo',
      'url':'https://abc.lambda-url.us-west-2.on.aws/mcp',
      'allow':['count_alerts']}

class NativeGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'AQ-MCP-Gateway'
        self.gw=native_gateway.NativeGateway(self.root)

    def _ready(self):
        self.root.mkdir()
        for f in ('aq_registry.py','aq_mcp_stdio.py','aq_check.py','requirements-gateway.txt'):
            (self.root/f).write_text('test')
        python=native_gateway.local_python(self.root)
        python.parent.mkdir(parents=True)
        python.write_text('test')
        (self.root/'targets.json').write_text('{"targets": {}}\n')

    def test_create_only_check_before_any_install(self):
        self.assertEqual(self.gw.inspect()['state'],'MISSING')
        self.assertRaises(DeploymentError,self.gw.bootstrap)
        self.assertFalse(self.root.exists())
        self._ready()
        with self.assertRaisesRegex(DeploymentError,'existing'):
            self.gw.bootstrap(approved=True)

    def test_native_bootstrap_mocked_dependency_install(self):
        def execute(argv,*a,**kw):
            if argv[1:3] == ['-m','venv']:
                py=native_gateway.local_python(self.root)
                py.parent.mkdir(parents=True)
                py.write_text('stub')
            return mock.Mock(returncode=0)
        with mock.patch.object(native_gateway.subprocess,'run',side_effect=execute) as run:
            state=self.gw.bootstrap(approved=True)
        self.assertEqual(state['state'],'READY')
        self.assertTrue((self.root/'aq_registry.py').exists())
        self.assertEqual(json.loads((self.root/'targets.json').read_text()),{'targets':{}})
        self.assertTrue(run.called)
        with self.assertRaisesRegex(DeploymentError,'existing'):
            self.gw.bootstrap(approved=True)

    def test_bootstrap_failure_never_deletes_partially_installed_directory(self):
        with mock.patch.object(native_gateway.subprocess,'run',side_effect=OSError('pip failure')):
            with self.assertRaisesRegex(DeploymentError,'incomplete'):
                self.gw.bootstrap(approved=True)
        self.assertEqual(self.gw.inspect()['state'],'INCOMPLETE')
        self.assertTrue(self.root.exists())

    def test_plan_apply_conflict_and_rollback(self):
        self._ready()
        d=ConnectorDeployer(self.gw)
        with mock.patch.object(self.gw,'_probe_entry',return_value={
            'tools':[{'name':'count_alerts','description':'read'}], 'count':1,'truncated':False
        }):
            verify=d.verify_backend(SPEC)
            self.assertEqual(verify['status'],'BACKEND_VERIFIED')
            plan=d.prepare(SPEC)
            receipt=d.deploy(SPEC,plan,True)
            self.assertEqual(receipt['status'],'GATEWAY_VERIFIED')
            self.assertEqual(self.gw.inspect()['target_names'],['rtr-demo'])
            d.rollback(receipt)
        self.assertEqual(self.gw.inspect()['target_names'],[])

    def test_rollbacks_refuse_parallel_writes(self):
        self._ready()
        baseline=self.gw.inspect()['sha256']
        req={'op':'apply','target':'rtr-demo','entry':{
            'url':SPEC['url'],'region':'us-west-2','env':'wizard',
            'note':'Created by tests','allow':['count_alerts']},
            'expected_sha256':baseline}
        r=self.gw.run(req)
        self.assertTrue((self.root/'.wizard-backups').is_dir())
        (self.root/'targets.json').write_text((self.root/'targets.json').read_text()+'\n')
        with self.assertRaisesRegex(DeploymentError,'changed'):
            self.gw.run({'op':'rollback','receipt':r})
        self.assertIn('rtr-demo',self.gw.inspect()['target_names'])

    def test_hash_guard_and_duplicate_rejected(self):
        self._ready()
        spec={'url':SPEC['url'],'region':'us-west-2','allow':['count_alerts']}
        with self.assertRaisesRegex(DeploymentError,'changed'):
            self.gw.run({'op':'apply','target':'rtr-demo','entry':spec,'expected_sha256':'f'*64})
        self.gw.run({'op':'apply','target':'rtr-demo','entry':spec,'expected_sha256':self.gw.inspect()['sha256']})
        with self.assertRaisesRegex(DeploymentError,'already exists'):
            self.gw.run({'op':'apply','target':'rtr-demo','entry':spec,'expected_sha256':self.gw.inspect()['sha256']})

    def test_native_quick_settings_no_ssh_and_no_secrets(self):
        validate_spec(SPEC)
        with mock.patch.object(native_gateway,'native_root',return_value=Path('C:/Users/engineer/AQ-MCP-Gateway')):
            cfg=quick_connector(SPEC)
        self.assertNotEqual(cfg['command'],'ssh')
        self.assertIn('python',cfg['command'])
        self.assertEqual(cfg['arguments'][-2:],['run','rtr-demo'])
        self.assertEqual(cfg['environment_variables'],{})
        self.assertEqual(len(cfg['arguments']),3)

    def test_native_rejects_remote_and_git(self):
        with self.assertRaises(ValidationError):
            validate_spec(dict(SPEC,host='server.example.internal'))
        with self.assertRaises(ValidationError):
            validate_spec(dict(SPEC,kind='git',target='github-ghes'))
        with self.assertRaises(ValidationError):
            validate_spec(dict(SPEC,transport='remote-windows'))

    def test_transport_identity_changes_plan(self):
        self.assertNotEqual(backend_identity(SPEC), backend_identity(dict(SPEC,transport='linux-ssh')))

    def test_local_discovery_does_not_call_tools(self):
        self._ready()
        with mock.patch('remote_agent._read_stdio_tools',return_value={'tools':[{'name':'count_alerts'}],'count':1,'truncated':False}) as fake:
            d=ConnectorDeployer(self.gw)
            info=d.verify_backend(SPEC)
        self.assertEqual(info['tool_count'],1)
        self.assertEqual(fake.call_count,1)
        cmd=fake.call_args.args[0]
        self.assertTrue(cmd[-1].endswith('aq_mcp_stdio.py'))

if __name__=='__main__':unittest.main()

class NativeGuiModeSmoke(unittest.TestCase):
    @unittest.skipUnless(bool(os.environ.get('DISPLAY')) or os.name=='nt', 'Tk screen requires display')
    def test_native_selected_without_ssh_credentials(self):
        import wizard
        app=wizard.Wizard()
        try:
            app.vars['transport'].set('native-local')
            app.transport_changed()
            self.assertEqual(app.spec()['host'],'127.0.0.1')
            self.assertEqual(app.spec()['user'],'local')
            self.assertIsInstance(app.gateway(),native_gateway.NativeGateway)
            with mock.patch.object(wizard.messagebox,'showerror') as err:
                app.go_next()
                self.assertEqual(app.step,1)
                self.assertFalse(err.called)
        finally: app.destroy()
