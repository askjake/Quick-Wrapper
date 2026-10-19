# Native-local gateway MOP (v0.4)

This mode supports a **Windows user without admin rights or WSL2**. It is a direct local stdio MCP process, not an SSH server. It leaves an existing Linux SSH 3090/3080 gateway untouched.

## 1. Prepare the local user environment

From PowerShell inside the GitHub checkout:

```powershell
Set-Location "$HOME\Quick-Wrapper"
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe wizard.py
```

The host must have Python 3.10+ with tkinter, working HTTPS access to an **approved** PyPI mirror for pinned gateway dependencies, a writable per-user home folder and a configured AWS/Okta credential chain for the Lambda services to be signed. Do not enter secrets in the wizard.

## 2. Create the native localhost gateway

In Step 1 select **Native gateway on THIS computer (no SSH/admin)**. Click **Inspect gateway**. If and only if the state is **MISSING**, choose **Install missing gateway** and approve creating `~/AQ-MCP-Gateway` and installing pinned packages. The installer refuses an existing directory (including a partly installed one). If the state is INCOMPLETE, manually investigate; do not recursively delete it or install over it.

Step 2: choose **AWS Lambda Function URL**, target name, display name and IAM-protected Lambda HTTPS URL. Click **Test / Verify Backend**, require **BACKEND_VERIFIED**, and inspect all names/descriptions for incorrect service identity and possible mutators. This is metadata-only; no application tools are called. When IAM creds are absent/expired, repair your authorized AWS session before trying again.

Step 3: explicitly select allowed tools (nonempty). Step 4: inspect the automatically generated plan, verify target/URL/region and tool names, then approve deployment. Save the resulting private rollback receipt. Expect **GATEWAY_VERIFIED**, not Quick-side verification.

## 3. Register in Amazon Quick (manual)

In Amazon Quick Desktop > Customize > Connectors, create a **Local** MCP connector. Fill the wizard-generated values exactly. Example (actual absolute paths depend on the current user account):

```text
Connection type: Local
Command: C:\Users\engineer\AQ-MCP-Gateway\venv\Scripts\python.exe
Arguments: C:\Users\engineer\AQ-MCP-Gateway\aq_registry.py run rtr-demo
Environment variables: EMPTY
```

Quick may show three chips. If any path contains spaces, do not assume that Quick's chip parser handles it: inspect and test a quoted path manually before declaring registration successful. Click **Test connection**, save, open a **new Quick chat**, inspect the connector's tool permissions, and perform a harmless read. No DIPS/SQLite file edits or privilege changes.

## 4. Rollback / diagnostics

A user-owned gateway has independent `~/AQ-MCP-Gateway/targets.json` and `.wizard-backups/`. Only restore from the receipt if the exact after-write SHA matches. If the registry changed, the tool fails closed. Do not manually overwrite a shared registry or disturb other processes.

Headless install from the same checkout (PowerShell):

```powershell
& .\.venv\Scripts\python.exe cli.py bootstrap --native-local --approve-bootstrap
```

This is **only for a MISSING native gateway** and requires explicit permission to download dependencies. Existing Linux remote via SSH continues to use the v0.3 path and arguments, including 127.0.0.1 where Linux's own SSH server is running.

## 5. Native Windows jump server on a DIFFERENT machine

This is **not the same as localhost**. To connect from Quick on machine A to native Windows on machine B, a network transport must be authorized, authenticated and reachable. This candidate intentionally does not install an SSH daemon or open a TCP listener; those are commonly administrator-controlled. An already-approved Windows OpenSSH server is a candidate for a subsequent adapter, with Windows path/ACL/locking and host-key integration validation. Until then, use native-local on the same Windows machine or the existing Linux SSH gateway.
