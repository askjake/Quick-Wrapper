#!/usr/bin/env python3
"""Registry-driven launcher for stdio MCP servers (runs on the 3090).

  aq_registry.py run <target>    exec the stdio MCP server for one target (stdout stays clean: MCP only)
  aq_registry.py list            show all targets

Two target kinds are supported:

  remote (default; any target with no "kind" field)
      SigV4-signs and forwards to an IAM-protected Lambda Function URL via aq_mcp_stdio.py.
      Only https://<id>.lambda-url.<region>.on.aws hosts are ever signed for.

  "kind": "local"
      exec a LOCAL read-only stdio MCP server from this directory. The script must be named
      in LOCAL_SERVERS, so a registry edit can never point a target at an arbitrary program.
      Local targets must not define "url", are never signed, and make no network calls.
"""
import json, os, re, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.environ.get("AQ_REGISTRY", os.path.join(HERE, "targets.json"))
STDIO = os.environ.get("AQ_STDIO_SCRIPT", os.path.join(HERE, "aq_mcp_stdio.py"))
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
URL_RE = re.compile(r"^https://[a-z0-9]+\.lambda-url\.([a-z0-9-]+)\.on\.aws(/.*)?$")

# Local stdio servers a "kind":"local" target is allowed to exec (basenames in HERE).
LOCAL_SERVERS = {"aq_build_artifacts_mcp.py"}

def load():
    with open(REG) as f:
        return json.load(f)

def _target(name):
    if not NAME_RE.match(name or ""):
        raise SystemExit(f"invalid target name: {name!r}")
    reg = load()
    t = reg["targets"].get(name)
    if t is None:
        raise SystemExit(f"unknown target {name!r}; known: {', '.join(sorted(reg['targets']))}")
    return t

def _remote_env(name, t):
    url = t["url"].rstrip("/")
    m = URL_RE.match(url)
    if not m:
        raise SystemExit(f"refusing non-Lambda-URL target for {name!r}: {url}")
    if not url.endswith("/mcp"):
        url += "/mcp"
    return {"AQ_TARGET_URL": url,
            "AQ_REGION": t.get("region") or m.group(1),
            "AQ_TOOL_ALLOWLIST": ",".join(t.get("allow") or []),
            "AQ_EXTRA_HEADERS": json.dumps(t.get("headers") or {}),
            "AQ_FORCED_ARGS": json.dumps(t.get("forced_args") or {}),
            "AQ_SECRET_ARGS": json.dumps(t.get("secret_args") or {}),
            "AQ_LOG_FILE": os.path.join(HERE, "aq-mcp.log")}   # always set -> inherited env can't leak in

def _local_env(name, t):
    server = t.get("server")
    if not isinstance(server, str) or server not in LOCAL_SERVERS:
        raise SystemExit(f"local target {name!r}: server must be one of "
                         f"{', '.join(sorted(LOCAL_SERVERS))}, got {server!r}")
    if t.get("url"):
        raise SystemExit(f"local target {name!r} must not define a url")
    cfg = t.get("config") or {}
    if not isinstance(cfg, dict):
        raise SystemExit(f"local target {name!r}: config must be a JSON object")
    # Every variable is always set so inherited environment can never widen a local target.
    return {"AQ_TARGET_URL": "",
            "AQ_TOOL_ALLOWLIST": ",".join(t.get("allow") or []),
            "AQ_EXTRA_HEADERS": "{}",
            "AQ_FORCED_ARGS": "{}",
            "AQ_BA_CONFIG_JSON": json.dumps(cfg)}

def target_kind(name):
    return (_target(name).get("kind") or "remote").strip().lower()

def target_env(name):
    t = _target(name)
    kind = (t.get("kind") or "remote").strip().lower()
    if kind == "local":
        return _local_env(name, t)
    if kind != "remote":
        raise SystemExit(f"target {name!r}: unknown kind {kind!r} (expected remote or local)")
    return _remote_env(name, t)

def target_script(name):
    """Absolute path of the stdio script that `run <target>` will exec."""
    t = _target(name)
    kind = (t.get("kind") or "remote").strip().lower()
    if kind == "local":
        server = t.get("server")
        if not isinstance(server, str) or server not in LOCAL_SERVERS:
            raise SystemExit(f"local target {name!r}: server must be one of "
                             f"{', '.join(sorted(LOCAL_SERVERS))}, got {server!r}")
        return os.path.join(HERE, server)
    return STDIO

def main(argv):
    if len(argv) >= 2 and argv[0] == "run":
        env = {**os.environ, **target_env(argv[1])}
        if os.name == 'nt':
            # Windows lacks Unix exec replacement semantics; retain the stdio
            # pipe and exit with the child MCP server's status.
            raise SystemExit(subprocess.call([sys.executable, target_script(argv[1])], env=env))
        os.execve(sys.executable, [sys.executable, target_script(argv[1])], env)
    elif argv[:1] == ["list"]:
        for n, t in sorted(load()["targets"].items()):
            print(f"{n:24} {t.get('env','?'):11} allow={len(t.get('allow') or [])} {t.get('note','')}")
    else:
        raise SystemExit(__doc__)

if __name__ == "__main__":
    main(sys.argv[1:])
