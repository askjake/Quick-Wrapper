"""Headless engineering interface to the same safe wizard deployment engine."""
import argparse
import json
import pathlib
import sys
from deploy_lib import SSHGateway, ConnectorDeployer
from model import validate_spec, quick_connector
from quick_reg import write_quick_config, quick_instructions


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))


def write_new_json(path,data):
    with open(path,'x',encoding='utf-8') as f:json.dump(data,f,indent=2,sort_keys=True);f.write('\n')


def main(argv=None):
    p=argparse.ArgumentParser(description='AQ-MCP Wizard CLI (registered Quick connector still requires manual UI action)')
    p.add_argument('operation',choices=['inspect','discover','plan','apply','export','rollback','bootstrap','repair-permissions'])
    p.add_argument('manifest',nargs='?',help='JSON manifest (no secrets)')
    p.add_argument('--known-hosts',default=str(pathlib.Path.home()/'.ssh/known_hosts'))
    p.add_argument('--plan-file')
    p.add_argument('--receipt-file')
    p.add_argument('--output-file')
    p.add_argument('--approve-target',default='')
    p.add_argument('--host')
    p.add_argument('--user')
    p.add_argument('--approve-bootstrap',action='store_true',help='Create missing gateway and install pinned dependencies')
    p.add_argument('--approve-repair',action='store_true',help='Remove group/world write from inspected owned core files')
    args=p.parse_args(argv)
    if args.operation in ('bootstrap','repair-permissions'):
        if not args.host or not args.user:
            p.error('bootstrap/repair requires --host and --user')
        d=ConnectorDeployer(SSHG(args.host,args.user,args.known_hosts))
        if args.operation=='bootstrap':
            if not args.approve_bootstrap:p.error('bootstrap requires --approve-bootstrap')
            result=d.bootstrap(approved=True)
        else:
            if not args.approve_repair:p.error('repair-permissions requires --approve-repair')
            before=d.inspect()
            result=d.repair_permissions(before,approved=True)
        print(json.dumps(result,indent=2));return 0
    if args.operation=='rollback':
        if not args.receipt_file or not args.host or not args.user:
            p.error('rollback requires --receipt-file, --host and --user')
        receipt=read_json(args.receipt_file)
        if args.approve_target != receipt.get('target'):
            p.error('--approve-target must match the rollback receipt target')
        result=ConnectorDeployer(SSHG(args.host,args.user,args.known_hosts)).rollback(receipt)
        print(json.dumps(result,indent=2));return 0
    if not args.manifest:p.error('manifest required')
    spec=read_json(args.manifest);validate_spec(spec)
    if args.operation=='export':
        if not args.output_file:p.error('export requires --output-file')
        write_quick_config(spec,args.output_file)
        print(quick_instructions(spec));return 0
    d=ConnectorDeployer(SSHG(spec['host'],spec['user'],args.known_hosts))
    if args.operation=='inspect': result=d.inspect()
    elif args.operation=='discover': result=d.discover(spec)
    elif args.operation=='plan':
        result=d.prepare(spec)
        if args.plan_file:write_new_json(args.plan_file,result)
    elif args.operation=='apply':
        if not args.plan_file or not args.receipt_file or args.approve_target!=spec['target']:
            p.error('apply requires --plan-file, --receipt-file and --approve-target matching manifest target')
        result=d.deploy(spec,read_json(args.plan_file),True)
        write_new_json(args.receipt_file,result)
    print(json.dumps(result,indent=2));return 0


def SSHG(host,user,known_hosts):
    return SSHGateway(host,user,known_hosts)

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
