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
