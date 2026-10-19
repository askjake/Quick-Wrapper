import json
import sys
import unittest
import tempfile
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import remote_agent as remote
from deploy_lib import ConnectorDeployer, DeploymentError
from model import backend_identity, risk_tool_names, identity_warnings, plan, validate_spec
from quick_reg import quick_instructions

SPEC={'host':'jump.example.internal','user':'engineer','kind':'lambda','target':'epg-demo',
      'display_name':'AQ EPG Demo','url':'https://abc.lambda-url.us-west-2.on.aws/mcp',
      'allow':['count_alerts']}
TOOLS=[{'name':'count_alerts','description':'Read alerts'},{'name':'submit_receivers_export','description':'Starts an export'}]

class Gateway:
    def __init__(self):
        self.calls=[]
        self.tools=list(TOOLS)
        self.status='READY'
        self.installed=False
        self.url=SPEC['url']
    def run(self, request, timeout=65):
        self.calls.append(request)
        op=request['op']
        if op=='inspect':
            return {'state':self.status,'sha256':'a'*64,'target_names':['build-artifacts']+(['epg-demo'] if self.installed else []),
                    'git_targets':['github-ghes'],'kinds':{'build-artifacts':'local'}}
        if op=='inspect_lambda_target':return {'target':'epg-demo','url':self.url,'allow':['count_alerts'], 'registry_sha256':'a'*64,'extra_config_present':[]}
        if op in ('discover','probe_existing'):
            return {'tools':list(self.tools),'count':len(self.tools),'truncated':False}
        if op=='git_check':return {'ok':True}
        if op=='check':return {'ok':True}
        raise AssertionError(request)

class BackendVerificationTests(unittest.TestCase):
    def test_identity_updates_on_changed_backend(self):
        key=backend_identity(SPEC)
        for k,v in [('url','https://def.lambda-url.us-west-2.on.aws/mcp'),
                    ('target','another'),('host','other.example.internal'),('display_name','RTR Alerts')]:
            with self.subTest(field=k):self.assertNotEqual(key,backend_identity(dict(SPEC,**{k:v})))
        self.assertEqual(key,backend_identity(dict(SPEC,allow=['another'])))

    def test_lambda_verification_uses_actual_discovery(self):
        g=Gateway();r=ConnectorDeployer(g).verify_backend(SPEC)
        self.assertEqual(r['status'],'BACKEND_VERIFIED')
        self.assertEqual([q['op'] for q in g.calls],['inspect','discover'])
        self.assertEqual(r['tool_count'],2)
        self.assertIn('submit_receivers_export',r['potentially_mutating_tools_name_only'])
        self.assertTrue(any('mismatch' in w.lower() for w in r['warnings']))
        self.assertEqual(r['backend_identity_sha256'],backend_identity(SPEC))

    def test_existing_lambda_can_verify_and_plan_registration_only(self):
        g=Gateway();g.installed=True
        d=ConnectorDeployer(g)
        proof=d.verify_backend(SPEC)
        self.assertTrue(proof['existing_target'])
        self.assertEqual(proof['existing_allow'],['count_alerts'])
        p=d.prepare(SPEC)
        self.assertEqual(p['mode'],'existing-target-registration-only')
        self.assertNotIn('apply',[x['op'] for x in g.calls])
        result=d.deploy(SPEC,p,True)
        self.assertEqual(result['status'],'EXISTING_TARGET_VERIFIED')
        self.assertNotIn('apply',[x['op'] for x in g.calls])

    def test_existing_lambda_different_url_fails_closed(self):
        g=Gateway();g.installed=True;g.url='https://def.lambda-url.us-west-2.on.aws/mcp'
        with self.assertRaisesRegex(DeploymentError,'DIFFERENT Lambda URL'):
            ConnectorDeployer(g).verify_backend(SPEC)

    def test_git_and_local_are_real_live_metadata_probes(self):
        for kind,target in [('git','github-ghes'),('local','build-artifacts')]:
            with self.subTest(kind=kind):
                g=Gateway();s=dict(SPEC,kind=kind,target=target)
                r=ConnectorDeployer(g).verify_backend(s)
                self.assertEqual([q['op'] for q in g.calls],['inspect','probe_existing'])
                self.assertEqual(g.calls[-1]['kind'],kind)
                self.assertIn('tools/list',r['handshake'])

    def test_verification_refuses_empty_or_incomplete_or_unready(self):
        g=Gateway();g.status='PERMISSIONS_NEED_REPAIR'
        with self.assertRaisesRegex(DeploymentError,'not READY'):ConnectorDeployer(g).verify_backend(SPEC)
        g=Gateway();g.tools=[]
        with self.assertRaisesRegex(DeploymentError,'Incomplete or empty'):ConnectorDeployer(g).verify_backend(SPEC)

    def test_risks_are_advisory_not_all_read_claim(self):
        r=plan(SPEC,'a'*64)
        self.assertEqual(r['tool_count_to_expose'],1)
        self.assertIn('execution_plan',r)
        self.assertIn('expected_registry_sha256',r)
        self.assertFalse(r['potentially_mutating_tools_name_only'])
        r=plan(dict(SPEC,allow=['count_alerts','submit_receivers_export']),'a'*64)
        self.assertIn('submit_receivers_export',r['potentially_mutating_tools_name_only'])
        self.assertTrue(r['warnings'])

    def test_manual_registration_is_complete_and_no_secrets(self):
        instructions=quick_instructions(SPEC)
        for field in ['Customize > Connectors','Connection type : Local','Command         : ssh',
                      'Expected 5 argument chips','Environment variables : EMPTY',
                      'Test connection','Save changes','NEW Quick chat','does not modify Quick']:
            with self.subTest(field=field):self.assertIn(field,instructions)

class ExistingMcpProbeTests(unittest.TestCase):
    def test_fake_mcp_metadata_handshake_does_not_call_application_tools(self):
        with tempfile.TemporaryDirectory() as dirname:
            root=Path(dirname)
            marker=root/'record.txt'
            server=root/'server.py'
            server.write_text('''import json,sys
with open(sys.argv[1],"w") as out:
    for line in sys.stdin:
        m=json.loads(line)
        out.write(m.get("method", "UNKNOWN")+"\\n");out.flush()
        if m.get("id")==2:
            print(json.dumps({"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"read_only","description":"test"}]}}),flush=True)
''')
            data=remote._read_stdio_tools([sys.executable,str(server),str(marker)])
            self.assertEqual(data['count'],1)
            self.assertEqual(marker.read_text().splitlines(),['initialize','notifications/initialized','tools/list'])

    def test_git_and_local_select_fixed_install_launchers_only(self):
        with tempfile.TemporaryDirectory() as dirname:
            p=Path(dirname)
            (p/'git_targets.json').write_text(json.dumps({'targets':{'github-ghes':{}}}))
            (p/'aq_git_guard.py').touch()
            (p/'aq_git_run.py').touch()
            (p/'targets.json').write_text(json.dumps({'targets':{'build-artifacts':{'kind':'local'}}}))
            original=remote.ROOT
            remote.ROOT=p
            try:
                with mock.patch.object(remote,'good_root',return_value=None),mock.patch.object(remote,'_read_stdio_tools',return_value={'tools':[{'name':'read'}],'count':1}) as probe:
                    remote.probe_existing('git','github-ghes')
                    self.assertTrue(probe.call_args.args[0][-2].endswith('aq_git_run.py'))
                    self.assertEqual(probe.call_args.args[0][-1],'github-ghes')
                    with mock.patch.object(remote,'load_reg',return_value=(json.loads((p/'targets.json').read_text()),b'', 'a'*64)):
                        remote.probe_existing('local','build-artifacts')
                    self.assertTrue(probe.call_args.args[0][-3].endswith('aq_registry.py'))
                    self.assertEqual(probe.call_args.args[0][-2:],['run','build-artifacts'])
            finally:remote.ROOT=original

if __name__=='__main__':unittest.main()
