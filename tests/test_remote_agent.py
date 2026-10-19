import sys,os,tempfile,json,hashlib,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import remote_agent as remote

class TestRemoteAgent(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=(remote.ROOT,remote.REG,remote.LOCK,remote.BACKUPS)
        remote.ROOT=Path(self.tmp.name)/'aq-mcp'
        remote.ROOT.mkdir()
        remote.REG=remote.ROOT/'targets.json'
        remote.LOCK=remote.ROOT/'.aq-wizard.lock'
        remote.BACKUPS=remote.ROOT/'.wizard-backups'
        for f in ['aq_registry.py','aq-run.sh','aq_mcp_stdio.py','aq_check.py']:(remote.ROOT/f).touch()
        remote.REG.write_text(json.dumps({'defaults':{},'targets':{'existing':{'url':'https://abc.lambda-url.us-west-2.on.aws','allow':['read']}}}))
        self.base=hashlib.sha256(remote.REG.read_bytes()).hexdigest()
        self.entry={'url':'https://abc.lambda-url.us-west-2.on.aws/mcp','region':'us-west-2',
                    'env':'wizard','note':'Installed by AQ-MCP Connector Wizard','allow':['read']}
    def tearDown(self):
        remote.ROOT,remote.REG,remote.LOCK,remote.BACKUPS=self.old
        self.tmp.cleanup()
    def test_apply_and_rollback(self):
        r=remote.apply({'target':'new-one','entry':self.entry,'expected_sha256':self.base})
        self.assertIn('new-one',json.loads(remote.REG.read_text())['targets'])
        self.assertEqual((remote.BACKUPS/r['backup_name']).stat().st_mode & 0o777,0o600)
        result=remote.rollback({'receipt':r})
        self.assertEqual(result['sha256'],self.base)
        self.assertNotIn('new-one',json.loads(remote.REG.read_text())['targets'])
    def test_parallel_change_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError,'CONFLICT'):
            remote.apply({'target':'new-one','entry':self.entry,'expected_sha256':'0'*64})
        self.assertEqual(hashlib.sha256(remote.REG.read_bytes()).hexdigest(),self.base)
    def test_rollback_respects_other_edits(self):
        r=remote.apply({'target':'new-one','entry':self.entry,'expected_sha256':self.base})
        remote.REG.write_text(remote.REG.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'CONFLICT'):
            remote.rollback({'receipt':r})
    def test_existing_target_not_replaced(self):
        with self.assertRaisesRegex(ValueError,'already exists'):
            remote.apply({'target':'existing','entry':self.entry,'expected_sha256':self.base})
    def test_empty_list_rejected(self):
        with self.assertRaises(ValueError):remote.check_entry('new-one',dict(self.entry,allow=[]))
    def test_non_lambda_refused(self):
        with self.assertRaises(ValueError):remote.check_entry('new-one',dict(self.entry,url='https://bad.example/mcp'))
