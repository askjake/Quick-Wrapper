import os,sys,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import remote_agent

class ToolCountTest(unittest.TestCase):
    def test_count_must_match(self):
        class Fake:
            returncode=0
            stdout=b'target  wizard   OK  0.1s  2 tools\n\n1/1 OK\n'
        with patch.object(remote_agent.subprocess,'run',return_value=Fake()):
            with tempfile.TemporaryDirectory() as d:
                old=remote_agent.ROOT
                try:
                    remote_agent.ROOT=Path(d)
                    self.assertFalse(remote_agent.check_target('test-target',3)['ok'])
                    self.assertTrue(remote_agent.check_target('test-target',2)['ok'])
                finally:remote_agent.ROOT=old
