# AQ-MCP Connector Wizard · v0.1 (engineering MVP)

A runnable **Windows desktop wizard** for onboarding MCP targets to the **existing** registry-driven 3090-style gateway. It has a five-step tkinter GUI, strict SSH host-key verification, live Lambda MCP tool discovery, preview+CAS registry deployment, real `tools/list` health checks, automatic failure rollback, and guided Quick Desktop registration.

**Status:** 21 automated tests passing locally (Linux). **No live Windows Quick or 3090 acceptance run yet.** It is not a production-ready or fully automatic Quick connector installer. Requires an existing reviewed `~/aq-mcp` gateway with Python/venv and credentials; does not bootstrap a new gateway, deploy a new Docker image or patch your existing production wrapper code.

## Start on Windows

1. Install Python 3.8+ from python.org with tkinter/Tcl/Tk. Recommended Python 3.11 or 3.12.
2. In **PowerShell or CMD**, unzip this package to your chosen folder and run:

   ```cmd
   py -3 -m pip install -r requirements.txt
   py -3 -m unittest discover -s tests -v
   py -3 wizard.py
   ```

   Or double-click `start_wizard.bat` after installing the dependency. No admin rights are required.
3. Connect to your approved SSH server using OpenSSH **after verifying its host fingerprint out of band**. Ensure that its verified key is in your own `~/.ssh/known_hosts`. The wizard uses `paramiko.RejectPolicy()`, refuses unknown/changed host keys and accepts SSH public-key/agent authentication only.
4. Your Linux host should already have `~/aq-mcp/targets.json`, `aq_registry.py`, `aq-run.sh`, `aq_mcp_stdio.py`, `aq_check.py`, and `venv/bin/python` from your reviewed gateway install. No `sudo`, no modifying JakeBot, no generic remote commands.

## Create a new Lambda connector

Fill in server/user, target name, HTTPS Lambda Function URL, then **Discover offered tools**. Explicitly select the exact tool names to allow. Only tools returned from the backend can pass the deploy gate. No `tools/call` occurs during discovery or health check. If discovery fails, the wizard fails closed rather than exposing all tools.

Click **Generate deployment plan**; it reads the installed registry hash and refuses duplicate targets. Review the plan, click **Deploy approved plan** and explicitly confirm. The gateway saves a mode-600 backup, writes the new registry atomically under an advisory lock, and runs `aq_check.py <target>` (MCP initialize + tools/list). On failure it attempts SHA-guarded rollback. If any intervening registry update makes rollback unsafe, rollback refuses and requires manual reconciliation. No unrelated gateway processes are restarted.

The UI then shows exact local Quick connector values. Enter them in **Customize → Connectors → Create/Add MCP** (actual labels may vary): connection type **Local**, command `ssh`, and the shown arguments in the single chip-accepting Arguments field. Keep Environment Variables empty. Save and open a **new** Quick chat to refresh tool discovery. Edit+Save is used to relaunch existing long-lived connectors where needed.

## Git and local connectors

The first release safely **registers an existing** `github-ghes` or `gitlab` Git target from the gateway, using `aq_git_run.py` over SSH, and existing local registry targets such as `build-artifacts` via `aq-run.sh`. It **does not** create new Git Docker targets, change image digests, create PAT files, edit branch guards, or install arbitrary local server scripts. For Git it runs `aq_git_run.py --check` but this does not authenticate a live tool call. For local targets it checks MCP `tools/list` before generating registration instructions.

The current `set_secret.py` supports a hidden **interactive getpass twice** workflow. It does **not** implement a noninteractive PAT-via-stdin API. Place tokens separately with its approved SSH terminal command, never in this wizard or a JSON manifest. GitLab API auth uses a PAT, even though Quick launches the connector over SSH.

## No direct Quick SQLite writes

The installed Quick Desktop's `DIPS` database is **not a supported, verified registration API**. Merely discovering a SQLite schema while Quick is closed is insufficient to prove its connector lifecycle, cross-table transactions, caches, signatures, or Electron synchronization. `quick_reg.py` exposes only a read-only `sqlite_master` inspector, a safe example JSON exporter, and explicit `MANUAL_REQUIRED` status. It **never inserts, updates or deletes any DIPS rows**. Fully automatic local Quick registration remains a separately gated future milestone, conditional on a supported provider interface and real readback tests.

## CLI for reproducible operator runs

```cmd
py -3 cli.py export templates/example_lambda_manifest.json --output-file connector-example.json
py -3 cli.py inspect templates/example_lambda_manifest.json
py -3 cli.py discover templates/example_lambda_manifest.json
py -3 cli.py plan templates/example_lambda_manifest.json --plan-file approved-plan.json
py -3 cli.py apply templates/example_lambda_manifest.json --plan-file approved-plan.json --approve-target demo-epg --receipt-file applied-receipt.json
```

The manifest, plan and receipt have **no secret tokens** but contain internal hostnames and URLs: handle them as internal-only files. Plan and receipt exports refuse to overwrite existing files. Never run `apply` until you have inspected your plan. A known-good rollback command after approval is:

```cmd
py -3 cli.py rollback --receipt-file applied-receipt.json --host trusted-jump.example.internal --user engineer --approve-target demo-epg
```

Rollback works only if no other registry edit has occurred since that deployment. It restores the exact saved bytes and does not touch Quick's manually registered connector (remove it yourself if rolling back).

## Limitations and next milestones

- No new gateway bootstrap, Docker installation, role provisioning, Okta refresh or unattended PAT injection. The target host must already be prepared.
- Only IAM-authenticated AWS Lambda Function URLs are accepted for new remote targets. Generic HTTP MCP is **not** silently routed through SigV4.
- The strict allow-list enforcer in the **current upstream wrapper** uses an empty list to mean *allow everything*. Therefore the wizard bans empty allow-lists and rejects unknown tool names.
- The remote SSH Python helper is transferred as **base64-encoded fixed source in a command**, with request values over stdin. It does not pass tokens/URLs in command arguments. The helper does not need to be installed persistently.
- Existing unrelated Quick connectors are not edited or relaunched. Verify per-tool permissions and the selected repo before approving any Git write; the current branch guard is not a repository allow-list.
- Future: signed/version-pinned gateway bootstrap, broader local/Git target provisioning with individual security gates, approved automatic Quick registration if available, and multi-user identities/credential renewal.

## Source accuracy corrections

The source snapshot supplied for the 3090 shows **`~/aq-mcp/targets.json`**, not `~/aq-mcp/registries/registry.json`. Its `aq_registry.py` supports `remote` (Lambda) and a whitelisted `local` server; Git uses **`git_targets.json`** with a separate launcher. The actual `set_secret.py` uses `getpass` rather than a piped-stdin PAT interface. The claimed `AQ_MCP_WIZARD_MOP.md` file was not attached or retrievable in this session, so this implementation is grounded in the supplied project outline, prior source snapshot and MOP, not a line-by-line audit of that named file.

**Receipt retention:** After a GUI deployment, select **Save receipt** on the Review page. Its JSON receipt makes checksum-bound rollback possible from the CLI after the GUI exits. Save it in an access-controlled workspace, not a shared/public folder.
