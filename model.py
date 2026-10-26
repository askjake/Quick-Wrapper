"""Pure input validation and Quick config generation (Python 3.8+)."""
import json
import hashlib
import re
from urllib.parse import urlsplit

TARGET_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
TOOL_RE = re.compile(r'^[A-Za-z0-9_.:/-]{1,128}$')
LAMBDA_HOST_RE = re.compile(r'^[a-z0-9]+\.lambda-url\.([a-z0-9-]+)\.on\.aws$')
SSH_HOST_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$')
SSH_USER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]{0,63}$')
LOCAL_SERVER = 'aq_build_artifacts_mcp.py'

class ValidationError(ValueError):
    pass


def validate_gateway(host, user):
    if not SSH_HOST_RE.fullmatch(host or '') or '..' in host or host.startswith('-'):
        raise ValidationError('Invalid SSH hostname/IP. Use a trusted, resolved server.')
    if not SSH_USER_RE.fullmatch(user or '') or user.startswith('-'):
        raise ValidationError('Invalid SSH username.')


def normalize_tools(tools):
    if not isinstance(tools, list) or not tools:
        raise ValidationError('Select at least one exact tool name; an empty allow-list exposes ALL tools.')
    if len(tools) > 300:
        raise ValidationError('Too many tools selected.')
    if any(not isinstance(t, str) or not TOOL_RE.fullmatch(t) for t in tools):
        raise ValidationError('Invalid tool name in allow-list.')
    if len(set(tools)) != len(tools):
        raise ValidationError('Duplicate tool names.')
    return sorted(tools)


def validate_lambda_url(url):
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise ValidationError('Malformed Lambda URL.')
    if parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ValidationError('Only HTTPS Lambda Function URLs are supported.')
    match = LAMBDA_HOST_RE.fullmatch(parsed.hostname or '')
    if not match or parsed.query or parsed.fragment or parsed.path not in ('', '/', '/mcp'):
        raise ValidationError('Expected https://ID.lambda-url.REGION.on.aws[/mcp] only.')
    if parsed.netloc.lower() != (parsed.hostname or '').lower():
        raise ValidationError('Non-standard URL port is not supported.')
    return parsed.hostname, match.group(1)


def validate_spec(spec):
    transport=spec.get('transport', 'linux-ssh')
    if transport not in ('linux-ssh','native-local'):
        raise ValidationError('Unsupported gateway transport (Windows remote SSH requires an approved SSH server).')
    if transport=='native-local':
        if spec.get('host') not in ('127.0.0.1','localhost'):
            raise ValidationError('Native-local gateway may only target this computer')
        if spec.get('kind')!='lambda':
            raise ValidationError('Native-local v0.4 supports Lambda targets; Git and existing local require Linux SSH')
    validate_gateway(spec.get('host', ''), spec.get('user', ''))
    name = spec.get('target', '')
    if not TARGET_RE.fullmatch(name):
        raise ValidationError('Target: lowercase letters, digits, dashes (max 64).')
    kind = spec.get('kind')
    if kind not in ('lambda', 'git', 'local'):
        raise ValidationError('Choose Lambda, Git or Local.')
    if kind == 'lambda':
        validate_lambda_url(spec.get('url', ''))
        normalize_tools(spec.get('allow', []))
    elif kind == 'git':
        if name not in ('github-ghes', 'gitlab'):
            raise ValidationError('MVP Git mode registers only preconfigured github-ghes or gitlab targets.')
    elif kind == 'local':
        if spec.get('server') not in (None, '', LOCAL_SERVER):
            raise ValidationError('Local server must be the gateway-approved Build Artifacts server.')
        # Existing target registration only, avoids accidentally adding a local server with no roots.
    return spec


def make_registry_entry(spec):
    validate_spec(spec)
    if spec['kind'] != 'lambda':
        raise ValidationError('Registry modification in v0.1 supports new Lambda targets only.')
    _host, region = validate_lambda_url(spec['url'])
    entry = {'url': spec['url'].rstrip('/'), 'region': region,
             'env': 'wizard', 'note': 'Installed by AQ-MCP Connector Wizard',
             'allow': normalize_tools(spec['allow'])}
    return entry


def quick_connector(spec):
    validate_spec(spec)
    if spec.get('transport')=='native-local':
        from native_gateway import native_root, local_python
        root=native_root()
        runner=local_python(root)
        if any(char.isspace() for char in str(root)):
            raise ValidationError('Local gateway directory includes spaces; Quick argument parsing must be independently verified')
        return {'id': 'aq-' + spec['target'],
                'name': spec.get('display_name') or 'AQ '+spec['target'],
                'connection_type':'Local', 'command': str(runner),
                'arguments': [str(root/'aq_registry.py'),'run',spec['target']],
                'timeout_seconds':120, 'environment_variables': {}}
    root = '/home/{}/aq-mcp'.format(spec['user'])
    name = spec['target']
    if spec['kind'] == 'git':
        arguments = ['-T','-q','{}@{}'.format(spec['user'], spec['host']),
                     '{}/venv/bin/python'.format(root), '{}/aq_git_run.py'.format(root), name]
    else:
        arguments = ['-T','-q','{}@{}'.format(spec['user'], spec['host']),
                     '{}/aq-run.sh'.format(root), name]
    return {'id': 'aq-' + name, 'name': spec.get('display_name') or 'AQ ' + name,
            'connection_type': 'Local', 'command': 'ssh', 'arguments': arguments,
            'timeout_seconds': 120, 'environment_variables': {}}


def config_export(spec):
    c = quick_connector(spec)
    # Export is a guide / not known to be directly importable by Quick.
    return json.dumps({'mcpServers': {c['id']: {'command': c['command'], 'args': c['arguments']}}}, indent=2)


def backend_identity(spec):
    """Fingerprints the inputs that bind a verification to a backend selection."""
    required = ['transport','host','user','kind','target','display_name']
    extra = ['url'] if spec.get('kind') == 'lambda' else ['server'] if spec.get('kind') == 'local' else []
    source = {key: spec.get(key, '') for key in required + extra}
    return hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def risk_tool_names(names):
    """Advisory name-based classifier, never a proof of read-only behavior."""
    prefixes = ('create_', 'write_', 'delete_', 'remove_', 'update_', 'set_', 'push_',
                'merge_', 'approve_', 'submit_', 'trigger_', 'upload_', 'export_',
                'send_', 'start_', 'run_', 'execute_', 'deploy_', 'publish_')
    keywords = ('_upload', '_write', '_delete', '_submit', '_export', '_trigger',
                '_mutate', 'build_log_capsule', 'grasshopper_plan_profile_upload')
    return sorted(name for name in names if name.lower().startswith(prefixes)
                  or any(token in name.lower() for token in keywords))


def identity_warnings(spec, names):
    """Heuristic mismatch signal; does not determine backend identity."""
    label = (spec.get('target', '') + ' ' + spec.get('display_name', '')).lower()
    n = {name.lower() for name in names}
    notes=[]
    if 'epg' in label and len(n & {'count_alerts','alert_time_series','export_receivers_csv',
                                    'submit_receivers_export','alert_geo_map'}) >= 2:
        notes.append('Possible backend mismatch: this connector is labeled EPG but the endpoint offers RTR Alerts tools. Verify the Lambda URL before approval.')
    if ('rtr' in label or 'alert' in label) and len(n & {'list_programs','get_genres','genre_distribution','top_programs'}) >= 2:
        notes.append('Possible backend mismatch: this connector is labeled Alerts but the endpoint offers EPG tools.')
    return notes


def plan(spec, current_sha):
    entry = make_registry_entry(spec) if spec['kind']=='lambda' else None
    chosen = entry['allow'] if entry else []
    risks = risk_tool_names(chosen)
    steps = (['1. Verify the selected backend and review tool discovery.',
              '2. Compare the live registry SHA-256 to this plan.',
              '3. Back up targets.json without changing other targets.',
              '4. Create exactly one new target with the chosen allow-list.',
              '5. Run MCP initialize/tools/list through the installed target.',
              '6. If health verification fails, attempt checksum-bound rollback.']
             if spec['kind']=='lambda' else
             ['1. Verify the existing launcher and complete an MCP tools/list handshake.',
              '2. Leave Git/local gateway configuration unchanged.'])
    steps += ['7. Register the generated Local SSH connector manually in Amazon Quick.',
              '8. Start a new Quick chat and verify a harmless read.']
    return {'version': 2, 'mode':'plan-only', 'target':spec['target'],
            'kind':spec['kind'], 'backend_identity_sha256':backend_identity(spec),
            'expected_registry_sha256':current_sha,
            'registry_entry':entry, 'tool_count_to_expose':len(chosen) if entry else 'existing policy',
            'potentially_mutating_tools_name_only':risks,
            'warnings':identity_warnings(spec, chosen) +
                       (['Name-based mutator detection is advisory; inspect ALL selected tools and schemas.'] if risks else []),
            'execution_plan':steps,
            'quick_connector':quick_connector(spec),
            'registration':'MANUAL_REQUIRED', 'no_secrets_in_manifest':True}
