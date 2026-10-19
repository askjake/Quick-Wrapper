"""Pure input validation and Quick config generation (Python 3.8+)."""
import json
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


def plan(spec, current_sha):
    entry = make_registry_entry(spec) if spec['kind']=='lambda' else None
    return {'version': 1, 'mode':'plan-only', 'target':spec['target'],
            'kind':spec['kind'], 'expected_registry_sha256':current_sha,
            'registry_entry':entry, 'quick_connector':quick_connector(spec),
            'registration':'MANUAL_REQUIRED', 'no_secrets_in_manifest':True}
