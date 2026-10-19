import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deploy_lib import ConnectorDeployer,DeploymentError
from model import make_registry_entry

SPEC={'host':'gateway.example.internal','user':'engineer','kind':'lambda',
      'target':'test-epg','url':'https://abc123.lambda-url.us-west-2.on.aws/mcp',
      'allow':['list_genres']}

class FakeGateway:
    def __init__(self):self.calls=[];self.sha='a'*64;self.change=False;self.pass_health=True
    def run(self,q,timeout=65):
        self.calls.append(q)
        if q['op']=='inspect':return {'state':'READY','installed':True,'sha256':self.sha,'target_names':[],'kinds':{},'git_targets':['github-ghes']}
        if q['op']=='discover':return {'tools':[{'name':'list_genres','description':'Read'}], 'truncated':False}
        if q['op']=='apply':return {'status':'DEPLOYED_PENDING_CHECK','target':q['target'],'before':self.sha,
                                   'after':'b'*64,'backup_name':'targets-1234567890-abcdef123456-aaaaaaaaaaaa.json'}
        if q['op']=='check':return {'ok':self.pass_health}
        if q['op']=='rollback':return {'status':'ROLLED_BACK'}
        raise AssertionError(q)

class TestDeployer(unittest.TestCase):
    def test_prepare_is_read_only(self):
        g=FakeGateway();p=ConnectorDeployer(g).prepare(SPEC)
        self.assertEqual([q['op'] for q in g.calls],['inspect'])
        self.assertEqual(p['expected_registry_sha256'],'a'*64)
    def test_apply_needs_confirmation(self):
        g=FakeGateway();d=ConnectorDeployer(g);p=d.prepare(SPEC)
        with self.assertRaises(DeploymentError):d.deploy(SPEC,p,False)
        self.assertEqual([q['op'] for q in g.calls],['inspect'])
    def test_deploy_rediscover_then_health(self):
        g=FakeGateway();d=ConnectorDeployer(g);p=d.prepare(SPEC)
        rec=d.deploy(SPEC,p,True)
        self.assertEqual(rec['status'],'GATEWAY_VERIFIED')
        self.assertEqual([q['op'] for q in g.calls],['inspect','discover','apply','check'])
    def test_health_fail_rolls_back(self):
        g=FakeGateway();g.pass_health=False;d=ConnectorDeployer(g);p=d.prepare(SPEC)
        with self.assertRaisesRegex(DeploymentError,'rolled back'):d.deploy(SPEC,p,True)
        self.assertEqual(g.calls[-1]['op'],'rollback')
    def test_form_changed_stops_before_apply(self):
        g=FakeGateway();d=ConnectorDeployer(g);p=d.prepare(SPEC)
        with self.assertRaises(DeploymentError):d.deploy(dict(SPEC,allow=['other']),p,True)
        self.assertNotIn('apply',[q['op'] for q in g.calls])
    def test_host_changed_stops(self):
        g=FakeGateway();d=ConnectorDeployer(g);p=d.prepare(SPEC)
        with self.assertRaises(DeploymentError):d.deploy(dict(SPEC,host='other.example.internal'),p,True)
