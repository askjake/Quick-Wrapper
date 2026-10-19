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


def quick_instructions(spec):
    cfg=quick_connector(spec)
    return ('Open Quick > Customize > Connectors > Create/Add MCP (UI label may vary).\n'
            'Connection type: Local\nID: {id}\nName: {name}\nCommand: ssh\n'
            'Arguments (single field, shown as chips):\n{args}\n'
            'Environment variables: EMPTY (never paste secrets)\n'
            'Save, then open a NEW Quick chat and verify one safe read.\n'
            'Review every action permission. Quick auto-registration has NOT occurred.').format(
                id=cfg['id'],name=cfg['name'],args=' '.join(cfg['arguments']))
