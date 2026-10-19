"""Quick registration export and DIPS read-only inspection.

Direct writes to undocumented Quick SQLite schemas are intentionally prohibited.
A Quick-created connector can have internal cross-table invariants, signing or migrations.
"""
import json
import os
import sqlite3
from model import quick_connector, config_export

class RegistrationUnsupported(RuntimeError):
    pass


def write_quick_config(spec, file_path):
    # Only writes a user-selected standalone export; NEVER the Quick application profile.
    if not str(file_path).lower().endswith('.json'):
        raise ValueError('Configuration export must be .json')
    if os.path.exists(file_path):
        raise FileExistsError('Refusing to overwrite an existing export.')
    with open(file_path, 'x', encoding='utf-8') as fh:
        fh.write(config_export(spec)+'\n')
    return file_path


def inspect_dips_read_only(path):
    """Inventory table/schema NAMES only; no personal connector rows or database writes."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    # URI read-only avoids modifying schema; Quick should be closed for consistent inspection.
    from pathlib import Path
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    cn = sqlite3.connect(uri, uri=True, timeout=1)
    try:
        cn.execute('PRAGMA query_only=ON')
        return [{'name': row[0], 'type': row[1]}
                for row in cn.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")]
    finally:
        cn.close()


def register_quick_automatically(*args, **kwargs):
    raise RegistrationUnsupported('No supported Quick connector registration interface verified. Use guided manual entry.')


def quick_copy_fields(connector):
    """Format a validated wizard connector for direct manual Quick GUI entry.

    This is a display/export helper only; it never registers a connector in Quick.
    Both SSH and native-local connectors use a single space-separated Arguments
    field in the observed Quick UI. Paths containing spaces require separate
    validation before use (native-local model rejects such paths).
    """
    if not isinstance(connector, dict):
        raise ValueError('Quick connector configuration is missing')
    command = connector.get('command')
    arguments = connector.get('arguments')
    if not isinstance(command, str) or not command.strip():
        raise ValueError('Missing Quick connector command')
    if not isinstance(arguments, list) or not arguments or any(
            not isinstance(arg, str) or not arg.strip() or any(ch in arg for ch in ('\n', '\r', '\x00'))
            for arg in arguments):
        raise ValueError('Invalid Quick connector arguments')
    if any(any(ch.isspace() for ch in arg) for arg in arguments):
        raise ValueError('Quick Arguments include spaces within an argument; validate UI parsing before copying')
    return {'command': command, 'arguments': ' '.join(arguments),
            'id': connector.get('id', ''), 'name': connector.get('name', ''),
            'timeout_seconds': connector.get('timeout_seconds', 120)}


def quick_instructions(spec):
    """Human-executable setup steps grounded in observed Quick Edit MCP UI.

    This is manual UI registration, not a DIPS mutation or import contract.
    """
    cfg=quick_connector(spec)
    args=' '.join(cfg['arguments'])
    chips='\n'.join('    {}. {}'.format(i+1, value) for i,value in enumerate(cfg['arguments']))
    return ("AMAZON QUICK — MANUAL LOCAL MCP CONNECTOR SETUP\n"
            "================================================\n"
            "Prerequisite: gateway was inspected and backend passed MCP tools/list.\n"
            "The gateway write and Quick registration are TWO separate operations.\n\n"
            "1. Open Amazon Quick Desktop. Go to Customize > Connectors.\n"
            "2. Open Create/Add MCP (exact label may vary by Quick version).\n"
            "3. Set these fields in the Edit MCP form:\n"
            "   Connection type : Local\n"
            "   ID              : {id}\n"
            "   Name            : {name}\n"
            "   Command         : {command}\n"
            "   Arguments       : {args}\n"
            "   Environment variables : EMPTY — never enter AWS credentials/PATs.\n"
            "   Timeout (seconds)     : {timeout} (adjust for the tool family)\n\n"
            "   The Arguments field is ONE input; Quick displays parsed chips.\n"
            "   Expected {count} argument chips:\n{chips}\n\n"
            "4. Click Test connection (if offered). Diagnose any failure before saving.\n"
            "5. Click Save changes. If updating a connector, Edit > Save relaunches\n"
            "   its process in the observed Quick build; a toggle alone may not.\n"
            "6. Open a NEW Quick chat so that the model sees the refreshed tool list.\n"
            "7. Request a safe read-only tool or inspect tools/list. Check it returns\n"
            "   data from the intended backend; a different tool family is a red flag.\n"
            "8. Review per-tool Quick permissions: keep mutations Ask each time\n"
            "   or Always deny unless explicitly approved. The gateway allow-list\n"
            "   is a separate permission layer.\n\n"
            "   Example prompt: Using the {name} connector, list your available\n"
            "   tools and perform one harmless read-only query. Do not modify data.\n\n"
            "NOTICE: This wizard does not modify Quick's undocumented DIPS DB,\n"
            "register a connector, grant permissions, or prove tool execution\n"
            "inside Quick. Exported JSON is a reference example, NOT a verified\n"
            "import format. Capture the test result and mark registration verified\n"
            "only after a real Quick chat call succeeds.\n").format(
                id=cfg['id'],name=cfg['name'],command=cfg['command'],args=args,
                timeout=cfg['timeout_seconds'],count=len(cfg['arguments']),chips=chips)
