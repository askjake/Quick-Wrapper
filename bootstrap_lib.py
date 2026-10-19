"""Curated, secrets-free gateway runtime bundle for create-only installs."""
import base64
import hashlib
import io
import pathlib
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
PAYLOAD = HERE / 'bootstrap_payload'
FILES = ('aq_registry.py', 'aq-run.sh', 'aq_mcp_stdio.py', 'aq_check.py', 'requirements-gateway.txt')
MAX_SOURCE_BYTES = 100000


def make_bundle():
    """Deterministic in-memory ZIP: no venv, credentials, log files or backups."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            src = PAYLOAD / name
            if src.is_symlink() or not src.is_file():
                raise ValueError('Missing/unsafe gateway source: ' + name)
            blob = src.read_bytes()
            if not blob or len(blob) > MAX_SOURCE_BYTES:
                raise ValueError('Invalid gateway source size: ' + name)
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100600 << 16)
            zf.writestr(info, blob)
    blob = buffer.getvalue()
    if len(blob) > 100000:
        raise ValueError('Installer exceeds size limit')
    return {'bundle_b64': base64.b64encode(blob).decode('ascii'),
            'bundle_sha256': hashlib.sha256(blob).hexdigest()}
