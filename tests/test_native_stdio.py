"""Synthetic MCP stdio child test: no network, no AWS, no privileged operations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class StdioTests(unittest.TestCase):
    def test_registry_launch_preserves_jsonrpc_stdio_and_allow_list(self):
        with tempfile.TemporaryDirectory() as dirname:
            r=Path(dirname)
            import shutil
            shutil.copyfile(ROOT/'bootstrap_payload'/'aq_registry.py',r/'aq_registry.py')
            (r/'targets.json').write_text(json.dumps({'targets':{'example':{
                'url':'https://abc.lambda-url.us-west-2.on.aws/mcp','region':'us-west-2',
                'allow':['read_one']}}}))
            (r/'fake_mcp.py').write_text('''import json,os,sys
allowed=os.environ.get('AQ_TOOL_ALLOWLIST')
for line in sys.stdin:
    msg=json.loads(line)
    if msg.get('id')==1:
        print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-06-18','capabilities':{},'serverInfo':{'name':'fake','version':'1'}}}),flush=True)
    if msg.get('id')==2:
        print(json.dumps({'jsonrpc':'2.0','id':2,'result':{'tools':[{'name':allowed}]}}),flush=True)
        break
''')
            env=dict(os.environ,AQ_STDIO_SCRIPT=str(r/'fake_mcp.py'))
            messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
                      {'jsonrpc':'2.0','method':'notifications/initialized'},
                      {'jsonrpc':'2.0','id':2,'method':'tools/list'}]
            p=subprocess.run([sys.executable,str(r/'aq_registry.py'),'run','example'],
                             input='\n'.join(json.dumps(x) for x in messages)+'\n',
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                             env=env,timeout=15)
            self.assertEqual(p.returncode,0,p.stderr)
            replies=[json.loads(line) for line in p.stdout.splitlines()]
            self.assertEqual(replies[-1]['result']['tools'],[{'name':'read_one'}])
            self.assertNotIn('read_one',p.stderr)

if __name__=='__main__':unittest.main()
