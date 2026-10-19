import os,sys,unittest,tempfile,stat
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import remote_agent as remote

class TestDiscovery(unittest.TestCase):
    def test_mcp_session_stays_open_until_tools_reply(self):
        with tempfile.TemporaryDirectory() as d:
            old=remote.ROOT
            try:
                remote.ROOT=Path(d)
                b=Path(d)/'venv/bin';b.mkdir(parents=True)
                (b/'python').symlink_to(sys.executable)
                server=Path(d)/'aq_mcp_stdio.py'
                server.write_text('''import json,sys
for line in sys.stdin:
    msg=json.loads(line)
    if msg.get("id")==2:
        print(json.dumps({"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"get_programs","description":"Get programs"},{"name":"danger_write","description":"Mutation"}]}}),flush=True)
''')
                ent={'url':'https://abc.lambda-url.us-west-2.on.aws/mcp','region':'us-west-2',
                     'allow':['get_programs'],'env':'wizard','note':'demo'}
                result=remote.probe_tools(ent)
                self.assertEqual(result['count'],2)
                self.assertEqual(result['tools'][0]['name'],'get_programs')
            finally:remote.ROOT=old
