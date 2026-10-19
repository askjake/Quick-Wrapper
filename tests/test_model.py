import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model import *

S={'host':'gateway.example.internal','user':'engineer','kind':'lambda',
   'target':'test-epg','display_name':'Test EPG',
   'url':'https://abc123.lambda-url.us-west-2.on.aws/mcp','allow':['get_programs','list_genres']}

class TestModel(unittest.TestCase):
    def test_valid(self):
        validate_spec(S)
        e=make_registry_entry(S)
        self.assertEqual(e['region'],'us-west-2')
        self.assertEqual(e['allow'],sorted(S['allow']))
        self.assertEqual(quick_connector(S)['arguments'][-2:],['/home/engineer/aq-mcp/aq-run.sh','test-epg'])
    def test_no_tool_policy_is_fail_closed(self):
        s=dict(S,allow=[])
        with self.assertRaises(ValidationError): validate_spec(s)
    def test_external_urls_rejected(self):
        for url in ['http://abc.lambda-url.us-west-2.on.aws','https://example.com/mcp',
                    'https://abc.lambda-url.us-west-2.on.aws/?key=sekrit',
                    'https://user:password@abc.lambda-url.us-west-2.on.aws',
                    'https://abc.lambda-url.us-west-2.on.aws:8443/mcp',
                    'https://abc.lambda-url.us-west-2.on.aws/other']:
            with self.subTest(url=url),self.assertRaises(ValidationError):validate_lambda_url(url)
    def test_bad_targets(self):
        for target in ['Feature/x','feature/../main','main\nhello','-foo','']:
            with self.subTest(target=target),self.assertRaises(ValidationError):validate_spec(dict(S,target=target))
    def test_git_existing_only(self):
        g=dict(S,kind='git',target='github-ghes',allow=[])
        validate_spec(g)
        self.assertEqual(len(quick_connector(g)['arguments']),6)
        with self.assertRaises(ValidationError):validate_spec(dict(g,target='unknown-git'))
    def test_quick_config(self):
        payload=json.loads(config_export(S))
        self.assertEqual(payload['mcpServers']['aq-test-epg']['command'],'ssh')
