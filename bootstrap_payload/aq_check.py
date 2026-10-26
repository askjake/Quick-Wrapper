#!/usr/bin/env python3
"""Health-check registry targets: sign + initialize + tools/list through the real stdio proxy.
  aq_check.py                 check every target
  aq_check.py qos-mcp sentry  check only these
Prints one row per target (OK n tools / failure + hint). Nothing is called except tools/list.
"""
import json, os, queue, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aq_registry as R

TIMEOUT = float(os.environ.get("AQ_CHECK_TIMEOUT", "30"))
INIT = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"aq-check","version":"1"}}}
NOTE = {"jsonrpc":"2.0","method":"notifications/initialized"}
LIST = {"jsonrpc":"2.0","id":2,"method":"tools/list"}

HINTS = [("ExpiredToken","creds expired - refresh Okta/AWS on the 3090"),
         ("security token","creds expired - refresh Okta/AWS on the 3090"),
         ("NoCredentials","no AWS creds found on the 3090"),
         ("403","403: role lacks lambda:InvokeFunctionUrl on this URL (or not an IAM URL)"),
         ("401","401: URL expects different auth (not AWS_IAM?)"),
         ("404","404: wrong path/URL or function gone"),
         ("Not Found","404: wrong path/URL or function gone"),
         ("timed out","network/Lambda timeout"),
         ("Name or service","DNS failure")]

def check(name):
    t0 = time.time()
    try:
        env = {**os.environ, **R.target_env(name)}
    except SystemExit as e:
        return name, "BAD-REGISTRY", str(e), 0.0
    script = getattr(R, "target_script", lambda n: R.STDIO)(name)  # local targets exec their own server
    p = subprocess.Popen([sys.executable, script], env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    q = queue.Queue(); err = []
    threading.Thread(target=lambda: [q.put(l) for l in p.stdout], daemon=True).start()
    threading.Thread(target=lambda: [err.append(l) for l in p.stderr], daemon=True).start()
    try:
        for m in (INIT, NOTE, LIST):
            p.stdin.write(json.dumps(m) + "\n"); p.stdin.flush()
        tools = None
        while time.time() - t0 < TIMEOUT:
            try:
                line = q.get(timeout=0.5)
            except queue.Empty:
                if p.poll() is not None and q.empty():
                    break
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == 2:
                if "result" in msg:
                    tools = msg["result"].get("tools", [])
                else:
                    err.append(json.dumps(msg.get("error")))
                break
    finally:
        try: p.stdin.close()
        except Exception: pass
        try: p.wait(timeout=5)
        except Exception: p.kill()
    dt = time.time() - t0
    if tools is not None:
        return name, "OK", f"{len(tools)} tools", dt
    tail = " ".join("".join(err).split())[-300:]
    hint = next((h for k, h in HINTS if k.lower() in tail.lower()), "see the gateway aq-mcp.log")
    return name, "FAIL", hint, dt

def main(names):
    reg = R.load()["targets"]
    names = names or sorted(reg)
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(check, names))
    for n, st, info, dt in rows:
        print(f"{n:24} {reg.get(n,{}).get('env','?'):11} {st:5} {dt:5.1f}s  {info}")
    bad = [r for r in rows if r[1] != "OK"]
    print(f"\n{len(rows)-len(bad)}/{len(rows)} OK")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
