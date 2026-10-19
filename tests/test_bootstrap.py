import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap_lib
import remote_agent
from deploy_lib import ConnectorDeployer, DeploymentError


class TestBundle(unittest.TestCase):
    def test_curated_payload_and_determinism(self):
        a=bootstrap_lib.make_bundle()
        b=bootstrap_lib.make_bundle()
        self.assertEqual(a['bundle_sha256'],b['bundle_sha256'])
        import base64,zipfile,io
        z=zipfile.ZipFile(io.BytesIO(base64.b64decode(a['bundle_b64'])))
        self.assertEqual(sorted(z.namelist()),sorted(bootstrap_lib.FILES))
        self.assertFalse(any('secret' in name or 'git_targets' in name or 'backup' in name for name in z.namelist()))


class FakeGateway:
    def __init__(self,state='MISSING'):
        self.state=state
        self.calls=[]
    def run(self,payload,timeout=65):
        self.calls.append(payload['op'])
        if payload['op']=='inspect':return {'state':self.state, 'installed':self.state!='MISSING'}
        if payload['op']=='bootstrap':
            self.state='READY';return {'status':'BOOTSTRAPPED'}
        if payload['op']=='repair_permissions':
            self.state='READY';return {'status':'PERMISSIONS_REPAIRED'}
        raise AssertionError(payload)


class TestBootstrapTransport(unittest.TestCase):
    def test_no_approval_is_read_only(self):
        g=FakeGateway()
        with self.assertRaises(DeploymentError):ConnectorDeployer(g).bootstrap()
        self.assertEqual(g.calls,[])
    def test_create_only_and_second_attempt_fails(self):
        g=FakeGateway()
        self.assertEqual(ConnectorDeployer(g).bootstrap(True)['status'],'BOOTSTRAPPED')
        self.assertEqual(g.calls,['inspect','bootstrap','inspect'])
        with self.assertRaises(DeploymentError):ConnectorDeployer(g).bootstrap(True)
        self.assertEqual(g.calls[-1],'inspect')
    def test_missing_is_not_permission_repair(self):
        g=FakeGateway()
        with self.assertRaises(DeploymentError):ConnectorDeployer(g).repair_permissions({'state':'MISSING'},True)
        self.assertEqual(g.calls,[])


@unittest.skipUnless(os.name=='posix','Remote filesystem/permissions are POSIX-only')
class TestRemoteBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.home=Path(self.tmp.name)
        self.old=(remote_agent.ROOT,remote_agent.REG,remote_agent.LOCK,remote_agent.BACKUPS)
        remote_agent.ROOT=self.home/'aq-mcp'
        remote_agent.REG=remote_agent.ROOT/'targets.json'
        remote_agent.LOCK=remote_agent.ROOT/'.aq-wizard.lock'
        remote_agent.BACKUPS=remote_agent.ROOT/'.wizard-backups'
    def tearDown(self):
        remote_agent.ROOT,remote_agent.REG,remote_agent.LOCK,remote_agent.BACKUPS=self.old
        self.tmp.cleanup()
    def mock_proc(self,args,**kwargs):
        if len(args)>2 and args[1:3]==['-m','venv']:
            v=Path(args[3]);(v/'bin').mkdir(parents=True)
            (v/'bin/python').symlink_to(sys.executable)
        class Result:returncode=0
        return Result()
    def test_missing_gateway_read_only_inspect(self):
        self.assertEqual(remote_agent.safe_info()['state'],'MISSING')
        self.assertFalse(remote_agent.ROOT.exists())
    def test_new_installer_staged_and_create_only(self):
        req=dict(op='bootstrap',confirm='CREATE_FRESH_GATEWAY',install_dependencies=True,**bootstrap_lib.make_bundle())
        with patch.object(remote_agent.subprocess,'run',side_effect=self.mock_proc):
            r=remote_agent.bootstrap(req)
        self.assertEqual(r['status'],'BOOTSTRAPPED')
        self.assertEqual(remote_agent.gateway_state()['state'],'READY')
        self.assertEqual(json.loads(remote_agent.REG.read_text()),{'targets':{}})
        self.assertEqual(remote_agent.ROOT.stat().st_mode & 0o777,0o700)
        self.assertEqual(remote_agent.REG.stat().st_mode & 0o777,0o600)
        with self.assertRaisesRegex(ValueError,'exists'):
            remote_agent.bootstrap(req)
    def test_bootstrap_requires_approval_and_integrity(self):
        req=dict(confirm='NO',install_dependencies=True,**bootstrap_lib.make_bundle())
        with self.assertRaisesRegex(ValueError,'approval'): remote_agent.bootstrap(req)
        req['confirm']='CREATE_FRESH_GATEWAY'
        req['bundle_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'checksum'): remote_agent.bootstrap(req)
        self.assertFalse(remote_agent.ROOT.exists())
    def test_existing_group_writable_inspect_then_repair(self):
        root=remote_agent.ROOT
        root.mkdir(mode=0o755)
        for n in ('aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py','targets.json'):
            (root/n).write_text('{}' if n=='targets.json' else 'x')
        v=root/'venv/bin';v.mkdir(parents=True)
        (v/'python').symlink_to(sys.executable)
        remote_agent.REG.write_text('{"targets":{}}')
        os.chmod(root,0o775)
        os.chmod(remote_agent.REG,0o664)
        before=remote_agent.safe_info()
        self.assertEqual(before['state'],'PERMISSIONS_NEED_REPAIR')
        with self.assertRaisesRegex(ValueError,'approval'):
            remote_agent.repair_permissions({'mode_issues':before['mode_issues']})
        with self.assertRaisesRegex(ValueError,'unsafe write permissions'):
            remote_agent.good_root()
        result=remote_agent.repair_permissions({'confirm':'REPAIR_OWNED_CORE_PERMISSIONS','mode_issues':before['mode_issues']})
        self.assertEqual(result['state'],'READY')
        remote_agent.good_root()
