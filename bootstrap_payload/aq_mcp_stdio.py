"""
aq-mcp-stdio — local stdio MCP proxy that SigV4-signs and forwards to an IAM-protected
MCP server (AWS Lambda Function URL). Signs with the LOCAL AWS credential chain.

Config env vars:
    AQ_TARGET_URL     (required)
    AQ_SIGV4_SERVICE  (default "lambda")
    AQ_REGION         (default "us-west-2")
    AQ_TOOL_ALLOWLIST (optional, comma-separated)

Run:
    python aq_mcp_stdio.py            -> MCP stdio server (what Quick launches)
    python aq_mcp_stdio.py --selftest -> connect, list tools, print them, exit

NOTE: this SDK build vendors httpx as `httpx2`. The auth object MUST subclass the SAME
httpx flavor the SDK's client uses, or httpx rejects it ("Invalid auth argument"). We
build the client via the SDK's own create_mcp_http_client, so we base our auth on the
httpx module THAT factory uses — httpx2 when present, else stock httpx.
"""
from __future__ import annotations
import os, sys, asyncio, logging, json, re

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import Session as BotoSession

_FMT = "%(asctime)s pid=%(process)d %(levelname)s %(message)s"
logging.basicConfig(stream=sys.stderr, level=os.environ.get("AQ_LOG_LEVEL", "INFO"), format=_FMT)
log = logging.getLogger("aq-mcp-stdio")
# Also append to a file so LIVE Quick invocations (whose stderr the UI may not surface)
# leave a readable trace. Override path with AQ_LOG_FILE; default ~/aq-mcp/aq-mcp.log.
try:
    _logfile = os.environ.get("AQ_LOG_FILE") or os.path.expanduser("~/aq-mcp/aq-mcp.log")
    _fh = logging.FileHandler(_logfile)
    _fh.setFormatter(logging.Formatter(_FMT))
    logging.getLogger().addHandler(_fh)
except Exception as _e:  # never fail startup over logging
    log.warning("could not open AQ_LOG_FILE: %s", _e)

TARGET_URL = os.environ.get("AQ_TARGET_URL")
SERVICE = os.environ.get("AQ_SIGV4_SERVICE", "lambda")
REGION = os.environ.get("AQ_REGION", "us-west-2")
ALLOW = [t.strip() for t in os.environ.get("AQ_TOOL_ALLOWLIST", "").split(",") if t.strip()]


def _load_extra_headers():
    raw = os.environ.get("AQ_EXTRA_HEADERS", "").strip()
    if not raw:
        return {}
    try:
        d = json.loads(raw)
    except ValueError:
        sys.exit("AQ_EXTRA_HEADERS must be a JSON object")
    out = {}
    for k, v in (d or {}).items():
        if not re.fullmatch(r"X-[A-Za-z0-9-]{1,64}", k) or k.lower().startswith("x-amz"):
            sys.exit("AQ_EXTRA_HEADERS: header name not allowed: %r" % (k,))
        v = str(v)
        if not v or len(v) > 200 or re.search(r"[\r\n\x00]", v):
            sys.exit("AQ_EXTRA_HEADERS: bad value for %s" % k)
        out[k] = v
    return out

EXTRA_HEADERS = _load_extra_headers()
log.info("extra request headers: %s", sorted(EXTRA_HEADERS) or "none")

# --- forced arguments (begin)
def _load_forced_args():
    raw = os.environ.get("AQ_FORCED_ARGS", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        sys.exit("AQ_FORCED_ARGS must be a JSON object")
    if not isinstance(data, dict):
        sys.exit("AQ_FORCED_ARGS must be a JSON object")
    out = {}
    for tool, args in data.items():
        if not re.fullmatch(r"[A-Za-z0-9_]{1,100}", str(tool)) or not isinstance(args, dict) or not args:
            sys.exit("AQ_FORCED_ARGS: bad entry for tool %r" % (tool,))
        clean = {}
        for key, value in args.items():
            scalar = value is None or isinstance(value, (bool, int, float, str))
            if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", str(key)) or not scalar:
                sys.exit("AQ_FORCED_ARGS: bad argument %r for %s" % (key, tool))
            clean[key] = value
        out[tool] = clean
    return out


FORCED_ARGS = _load_forced_args()
log.info("forced arguments for tools: %s", sorted(FORCED_ARGS) or "none")


def _apply_forced(name, arguments):
    # returns (arguments with this tool's forced values written over whatever the caller sent, names overridden)
    forced = FORCED_ARGS.get(name)
    if not forced:
        return arguments, []
    merged = dict(arguments or {})
    overridden = [k for k, v in forced.items() if k in merged and merged[k] != v]
    merged.update(forced)
    return merged, overridden
# --- forced arguments (end)

# --- secret arguments (begin)
# AQ_SECRET_ARGS = {"tool": {"arg": "/path/to/file"}}. The env holds only PATHS. The value is read from the file on
# every call, written over whatever the caller sent, never logged and never put in an error message.
import stat as _stat


def _load_secret_args():
    raw = os.environ.get("AQ_SECRET_ARGS", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        sys.exit("AQ_SECRET_ARGS must be a JSON object")
    if not isinstance(data, dict):
        sys.exit("AQ_SECRET_ARGS must be a JSON object")
    out = {}
    for tool, args in data.items():
        if not re.fullmatch(r"[A-Za-z0-9_]{1,100}", str(tool)) or not isinstance(args, dict) or not args:
            sys.exit("AQ_SECRET_ARGS: bad entry for tool %r" % (tool,))
        clean = {}
        for key, path in args.items():
            if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", str(key)) or not isinstance(path, str) or not path.strip():
                sys.exit("AQ_SECRET_ARGS: bad argument %r for %s" % (key, tool))
            clean[key] = os.path.abspath(os.path.expanduser(path))
        out[tool] = clean
    return out


SECRET_ARGS = _load_secret_args()
log.info("secret arguments (names only): %s", {t: sorted(a) for t, a in SECRET_ARGS.items()} or "none")


def _read_secret_file(path):
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise ValueError("secret file is missing, unreadable or a symlink") from None
    try:
        st = os.fstat(fd)
        if not _stat.S_ISREG(st.st_mode):
            raise ValueError("secret file is not a regular file")
        if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
            raise ValueError("secret file is not owned by the user running the proxy")
        if st.st_mode & 0o077:
            raise ValueError("secret file permissions are too open (chmod 600)")
        if st.st_size < 1 or st.st_size > 4096:
            raise ValueError("secret file is empty or larger than 4096 bytes")
        data = os.read(fd, 4097)
    finally:
        os.close(fd)
    try:
        value = data.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise ValueError("secret file is not valid UTF-8") from None
    if not value or re.search(r"\s", value) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("secret file must hold one token with no whitespace or control characters")
    return value


def _apply_secrets(name, arguments):
    # returns (arguments with this tool's secret values written over whatever the caller sent, names supplied)
    wanted = SECRET_ARGS.get(name)
    if not wanted:
        return arguments, []
    merged = dict(arguments or {})
    for key, path in wanted.items():
        try:
            merged[key] = _read_secret_file(path)
        except ValueError as e:
            raise ValueError("%s: cannot supply %r: %s" % (name, key, e)) from None
    return merged, sorted(wanted)
# --- secret arguments (end)

# --- error surfacing (begin)
# Convert ANY upstream failure into a well-formed CallToolResult(isError=True) whose text is
# never empty, carries the HTTP status when discoverable, and a short SCRUBBED body snippet.
# The snippet is built only from the upstream response/exception, never the request arguments.
# The secret value(s) injected for THIS call are passed in and removed by exact match first,
# so the token cannot survive regardless of charset/newlines/delimiters; pattern scrub then
# redacts any other long opaque runs or sensitive key=value material a server might echo.
import re as _re_es

_ES_PREFIX = "upstream call failed"
_ES_OKTA = ("AWS credentials look expired or unauthorized (HTTP 403). Refresh Okta on the 3090 "
            "(re-run your AWS/Okta login), then relaunch the connector.")
_ES_SNIPPET_CAP = 200
_ES_TEXT_CAP = 1000
# A maximal run of >=24 opaque chars (heavy token ~64; AWS v4 signatures 64 hex). \S so a
# token containing punctuation outside base64 is still caught by the secondary pattern.
_ES_OPAQUE = _re_es.compile(r"\S{24,}")
# Sensitive "key=value" / "key: value" (incl. JSON "key":"value"), value redacted wholesale.
_ES_SENSITIVE_KW = _re_es.compile(
    r'(?i)\b(authorization|x-amz[a-z0-9-]*|heavy_auth_token|aws_session_token|security_token|'
    r'signature|credential)\b["\']?\s*[=:]\s*["\']?[^\s,;&"\']+')
_ES_AUTH_SIG = _re_es.compile(r"(?i)expired|unauthorized|forbidden|not\s+authorized|access\s*denied|security\s+token")


def _es_discover_status(exc):
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    if isinstance(code, int):
        return code
    r = repr(exc)
    # Anchored patterns only -- avoid matching ':443' (https port) or ids like 'R456'.
    for _pat in (r"status_code[=:\s]+(\d{3})", r"HTTP/?\s*(\d{3})", r"['\"](4\d\d|5\d\d)\b"):
        m = _re_es.search(_pat, r)
        if m:
            return int(m.group(1))
    return None


def _es_scrub(text):
    text = _ES_SENSITIVE_KW.sub(lambda m: m.group(1) + "=[REDACTED]", text)
    text = _ES_OPAQUE.sub("[REDACTED]", text)
    return text.replace("\n", " ").replace("\r", " ").strip()


def _es_safe_snippet(exc, secrets=()):
    resp = getattr(exc, "response", None)
    body = None
    if resp is not None:
        body = getattr(resp, "text", None)
        if not isinstance(body, str):
            raw = getattr(resp, "content", None)
            if isinstance(raw, (bytes, bytearray)):
                body = raw.decode("utf-8", "replace")
    if not body:
        body = str(exc) or repr(exc)
    # PRIMARY defense: remove the exact injected secret value(s) first, before any pattern
    # scrub and before truncation -- airtight regardless of charset/newlines/delimiters.
    for s in secrets:
        if s:
            body = body.replace(s, "[REDACTED]")
    return _es_scrub(body)[:_ES_SNIPPET_CAP]


def _es_describe(exc):
    # for the log line ONLY: status or type, never body/arguments/token
    status = _es_discover_status(exc)
    return ("HTTP %d" % status) if status else ("exc " + str(type(exc)))


def _error_result(exc, types, secrets=()):
    status = _es_discover_status(exc)
    snippet = _es_safe_snippet(exc, secrets)
    head = _ES_PREFIX + ((" (HTTP %d)" % status) if status else "")
    parts = [head]
    if status == 403 or _ES_AUTH_SIG.search(snippet):
        parts.append(_ES_OKTA)
    parts.append(snippet)
    text = "\n".join(p for p in parts if p)[:_ES_TEXT_CAP] or _ES_PREFIX
    # belt-and-suspenders: exact-remove any injected secret from the final text too
    for s in secrets:
        if s:
            text = text.replace(s, "[REDACTED]")
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], isError=True)
# --- error surfacing (end)

# Use the SAME httpx flavor the MCP SDK's client factory uses. This build vendors it as
# httpx2; fall back to stock httpx on a standard SDK.
try:
    import httpx2 as _httpx
except ImportError:  # pragma: no cover
    import httpx as _httpx


class SigV4HttpxAuth(_httpx.Auth):
    """Sign every outgoing request with SigV4 from the local credential chain."""
    requires_request_body = True
    def __init__(self):
        creds = BotoSession().get_credentials()
        if creds is None:
            raise RuntimeError("no AWS credentials — SigV4 signing impossible")
        self._creds = creds
    def auth_flow(self, request):
        aws = AWSRequest(method=request.method, url=str(request.url),
                         data=request.content or b"",
                         headers={**dict(request.headers), **EXTRA_HEADERS})
        if "connection" in aws.headers:
            del aws.headers["connection"]
        SigV4Auth(self._creds, SERVICE, REGION).add_auth(aws)
        request.headers.update(dict(aws.headers))
        yield request



# --- sse event size (begin)
# Optional override of the MCP client's per-SSE-event byte cap (SDK default 1,048,576).
# UNSET => pass nothing (zero behavior change). An int in [1048576, 67108864] => raise to that
# many bytes. Disabling (None) is NOT allowed on this shared single-process proxy (OOM footgun).
# Anything else (none/0/negative/decimal/underscored/signed/out-of-range) => refuse at startup.
_AQ_SSE_MIN = 1048576       # the SDK default; never LOWER the cap (that only breaks more results)
_AQ_SSE_MAX = 67108864      # 64 MiB hard ceiling -> bounds the in-memory SSE buffer on the shared proxy
def _load_sse_kwargs():
    raw = os.environ.get("AQ_MAX_SSE_EVENT_SIZE", "").strip()
    if not raw:
        return {}
    if not raw.isdigit():
        sys.exit("AQ_MAX_SSE_EVENT_SIZE must be a plain positive integer number of bytes "
                 "(no sign, decimal point, underscores, or 'none'); disabling the cap is not allowed")
    n = int(raw)
    if n < _AQ_SSE_MIN or n > _AQ_SSE_MAX:
        sys.exit("AQ_MAX_SSE_EVENT_SIZE must be between %d and %d bytes (got %d)"
                 % (_AQ_SSE_MIN, _AQ_SSE_MAX, n))
    return {"max_sse_event_size": n}


_AQ_SSE_KW = _load_sse_kwargs()
log.info("SSE event-size override: %s", _AQ_SSE_KW or "none (SDK default)")
# --- sse event size (end)

def _require_target():
    if not TARGET_URL:
        sys.exit("AQ_TARGET_URL is required")


def _make_client():
    """Build the httpx(2) client with SigV4 auth using the SDK's own factory."""
    from mcp.client.streamable_http import create_mcp_http_client
    return create_mcp_http_client(auth=SigV4HttpxAuth())


async def _selftest() -> int:
    _require_target()
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    log.info("selftest -> %s (service=%s region=%s)", TARGET_URL, SERVICE, REGION)
    client = _make_client()
    async with streamable_http_client(TARGET_URL, http_client=client) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            names = [t.name for t in tools]
            shown = [n for n in names if (not ALLOW or n in ALLOW)]
            print(f"OK: upstream returned {len(names)} tools; "
                  f"{len(shown)} after allow-list filter")
            for n in shown:
                print(f"  - {n}")
    return 0


async def _upstream_call(method_name: str, *args):
    """Open a FRESH upstream connection, initialize, run one call, close.
    Per-request (not a held session) so there is no long-lived idle SSE stream to be
    torn down — that teardown was exiting the whole process and making Quick retry."""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    client = _make_client()
    async with streamable_http_client(TARGET_URL, http_client=client, **_AQ_SSE_KW) as (read, write):
        async with ClientSession(read, write) as upstream:
            await upstream.initialize()
            fn = getattr(upstream, method_name)
            return await fn(*args)


async def _serve() -> None:
    _require_target()
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    app = Server("aq-mcp-stdio")

    # MCP 2.x: register handlers explicitly. Each handler does its own upstream round-trip
    # via _upstream_call (fresh connection per request).
    async def handle_list_tools(ctx, params):
        log.info("handle_list_tools: querying upstream %s", TARGET_URL)
        tools = (await _upstream_call("list_tools")).tools
        tools = [t for t in tools if (not ALLOW or t.name in ALLOW)]
        log.info("handle_list_tools: returning %d tools", len(tools))
        return types.ListToolsResult(tools=tools)

    async def handle_call_tool(ctx, params):
        name = params.name
        arguments = getattr(params, "arguments", None) or {}
        if ALLOW and name not in ALLOW:
            raise ValueError(f"tool '{name}' not permitted")
        arguments, overridden = _apply_forced(name, arguments)
        if name in FORCED_ARGS:
            log.info("call %s: forced %s%s", name, sorted(FORCED_ARGS[name]),
                     (" (overrode caller values for %s)" % overridden) if overridden else "")
        arguments, supplied = _apply_secrets(name, arguments)
        if supplied:
            log.info("call %s: supplied %s from secret file (value not logged)", name, supplied)
        try:
            return await _upstream_call("call_tool", name, arguments)
        except Exception as _exc:
            log.warning("call %s failed upstream: %s", name, _es_describe(_exc))
            _es_secrets = [arguments[k] for k in supplied if isinstance(arguments.get(k), str)]
            return _error_result(_exc, types, _es_secrets)

    app.add_request_handler("tools/list", types.PaginatedRequestParams, handle_list_tools)
    app.add_request_handler("tools/call", types.CallToolRequestParams, handle_call_tool)

    # The stdio loop owns the process lifetime — it runs until stdin closes (i.e. until
    # Quick shuts the server down), NOT until some upstream stream ends.
    log.info("serve: handlers registered; entering stdio loop (allow=%s)", ALLOW or "ALL")
    async with stdio_server() as (sr, sw):
        await app.run(sr, sw, app.create_initialization_options())
    log.info("serve: stdio loop ended (stdin closed)")


def main() -> None:
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(asyncio.run(_selftest()))
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
