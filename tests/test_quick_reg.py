import sys,sqlite3,tempfile,unittest,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quick_reg import *

class TestQuickReg(unittest.TestCase):
    def test_schema_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,'test.sqlite');con=sqlite3.connect(p)
            con.execute('create table demo_connectors(id text primary key,config text)');con.commit();con.close()
            tables=inspect_dips_read_only(p)
            self.assertIn({'name':'demo_connectors','type':'table'},tables)
            self.assertTrue(os.path.exists(p))
    def test_registration_is_prohibited(self):
        with self.assertRaises(RegistrationUnsupported):register_quick_automatically()

class TestQuickCopyFields(unittest.TestCase):
    def test_ssh_arguments_one_line(self):
        cfg={'id':'aq-sentry','name':'sentry','command':'ssh',
             'arguments':['-T','-q','montjac@10.79.85.47',
                          '/home/montjac/aq-mcp/aq-run.sh','sentry'],
             'timeout_seconds':120}
        v=quick_copy_fields(cfg)
        self.assertEqual(v['command'],'ssh')
        self.assertEqual(v['arguments'],
                         '-T -q montjac@10.79.85.47 /home/montjac/aq-mcp/aq-run.sh sentry')

    def test_native_arguments_one_line(self):
        cfg={'id':'aq-sentry','name':'sentry',
             'command':r'C:\Users\engineer\AQ-MCP-Gateway\venv\Scripts\python.exe',
             'arguments':[r'C:\Users\engineer\AQ-MCP-Gateway\aq_registry.py','run','sentry']}
        v=quick_copy_fields(cfg)
        self.assertEqual(v['command'],cfg['command'])
        self.assertEqual(v['arguments'],r'C:\Users\engineer\AQ-MCP-Gateway\aq_registry.py run sentry')

    def test_bad_arguments_refused(self):
        for cfg in ({'command':'ssh','arguments':[]},
                    {'command':'ssh','arguments':['-T','bad\nvalue']},
                    {'command':'ssh','arguments':['C:/Program Files/a.py']}):
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):
                quick_copy_fields(cfg)
