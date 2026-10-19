# Quick-Wrapper — AQ-MCP Connector Wizard

**Start here: deploy and verify an MCP connector from Windows.** The wizard connects to a trusted Linux SSH gateway, verifies an MCP backend, discovers offered tools, generates a guarded deployment plan, deploys approved Lambda registry targets, and supplies the exact **Amazon Quick Desktop** connector settings.

> **Version check (important):** The repository currently tracks the **v0.1** wizard source. The updated five-step workflow documented first below applies to the separately supplied **v0.3** distribution (`AQ_MCP_Connector_Wizard_v0_3.zip`), which has been exercised on a Windows test workstation and gateway. **v0.3 source has not yet been promoted into this GitHub repository.** Cloning this repo alone does **not** install v0.3. Do not use the v0.1 checkout to qualify a fresh Windows install: it has a known POSIX `fcntl` test-import problem and lacks the newer gateway bootstrap and backend-verification flow.

## Clone or update the repository (Windows PowerShell)

Use an **isolated project-local virtual environment** (`.venv`) to avoid modifying another Python installation or its Paramiko version. These examples assume you want the checkout under `Documents`; choose a different local folder if needed. Run the commands in **PowerShell**, not CMD.

**First-time clone (SSH):**

```powershell
cd "$HOME\Documents"
git clone git@github.com:askjake/Quick-Wrapper.git
cd .\Quick-Wrapper

py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Launch the code actually checked into this branch/repository.
.\.venv\Scripts\python.exe wizard.py
```

The repository is public; if you have not configured GitHub SSH keys, substitute `git clone https://github.com/askjake/Quick-Wrapper.git`. SSH login to GitHub is unrelated to the gateway's own `known_hosts` trust verification.

**Update an existing checkout (fast-forward only):**

```powershell
cd "$HOME\Documents\Quick-Wrapper"
git status --short
# Review and resolve local edits before pulling. Do not discard changes.
git switch main
git pull --ff-only origin main

# Reuse the venv; create it only if missing.
if (-not (Test-Path .\.venv\Scripts\python.exe)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe wizard.py
```

**Run the newer v0.3 ZIP:** Until v0.3 source is merged into `main`, the clone/update commands above run the **checked-in v0.1 code**, not v0.3. For the separately provided v0.3 package, extract it to its own folder and run the following **from the directory containing its `wizard.py`**:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe wizard.py
```

A v0.1 Windows test run is known to fail when Linux-only `fcntl` is imported. **Use the v0.3 package for the tested backend-verification, bootstrap and automatic-plan workflow.** The commands above intentionally use `.venv\Scripts\python.exe` directly; no shell activation is required. If you prefer to activate it in PowerShell, use `.\.venv\Scripts\Activate.ps1` where permitted by your organization's script policy (do not weaken execution policy just to run the wizard).

## 1. Install and launch the wizard on Windows (v0.3)

1. Obtain the reviewed **`AQ_MCP_Connector_Wizard_v0_3.zip`** package from the project handoff. Until the v0.3 source is published to this repository or a verified GitHub release, use that package—not the current repository checkout.
2. Extract to a **new** directory. Open PowerShell or Command Prompt **in the directory containing `wizard.py` and `requirements.txt`**. Do not overwrite an open v0.1/v0.2 installation.
3. Install the local dependency, run tests, then launch:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   .\.venv\Scripts\python.exe wizard.py
   ```

   Python with tkinter/Tcl-Tk is required; Paramiko is installed from `requirements.txt`. POSIX-only integration fixtures may be skipped on Windows. Stop if tests fail. A historical successful Linux test run is **41/41**, not proof that every Windows/gateway combination is qualified.

The wizard uses `paramiko.RejectPolicy()` and **key/agent-based SSH**, not password fallback. Verify the jump server's host key out of band and put it in the local `known_hosts` file before connecting.

## 2. Inspect or bootstrap the jump-server gateway

On **Step 1 — SSH Gateway**, enter the host, SSH username and known-hosts path, then select **Inspect gateway (read only)**.

| Inspect state | Next action |
| --- | --- |
| `READY` | Existing gateway is usable; continue to backend verification. |
| `MISSING` | On a **new, approved Linux host only**, select **Install missing gateway** and explicitly confirm. |
| `PERMISSIONS_NEED_REPAIR` | Review the exact owned file list and shared-workflow implications before using **Repair core permissions**. Re-inspect afterward. |
| `INCOMPLETE`, `FOREIGN`, or `SYMLINK` | Stop. Do not overwrite, recursively chmod or silently replace the installation. |

A fresh install creates an owner-private `~/aq-mcp`, stages the reviewed Lambda gateway sources, sets up the pinned Python environment, validates imports, and refuses to overwrite any existing installation. The host requires **Python 3.10+**, `venv`/`pip`, and access to an approved package index. **Gateway installation is not AWS identity provisioning:** configure authorized AWS/Okta credentials for the SSH user separately; they may expire. The fresh installer does not install Git Docker images, PATs, corporate certificates or Quick connectors.

## 3. Select and verify the MCP backend

On **Step 2 — Backend**, choose one of these supported flows:

| Backend | What v0.3 verifies | Install scope |
| --- | --- | --- |
| **AWS Lambda Function URL (SigV4)** | Actual IAM-signed MCP `initialize` + `tools/list` through the gateway; verifies the supplied HTTPS Lambda Function URL and region. | Can create **one new** Lambda registry target. |
| **Guarded Git MCP** | Metadata handshake through a **pre-existing** `aq_git_run.py`/guard/Docker target. | Existing target **registration only**; no Git runtime or PAT provisioning. |
| **Approved local MCP** | Metadata handshake through an **existing** allowlisted local target. | Existing target **registration only**; no arbitrary script installation. |

Click **Test / Verify Backend** before continuing. A successful `BACKEND_VERIFIED` means protocol connectivity and offered-tool discovery, **not** that those tools are safe or that any application tool was exercised. Confirm the offered tool names actually match the intended service: an EPG-named connector that discovers RTR Alerts export tools is a wrong-endpoint warning, not successful EPG identification.

## 4. Select tools, review the automatic plan, deploy

On **Step 3 — Tool Policy**, choose the **exact tools** to expose. For Lambda targets an **explicit nonempty allow-list** is mandatory: the underlying gateway can interpret an empty list as “allow all.” The wizard flags potentially mutating names, but that is a **heuristic, not a security verdict**. Inspect names, descriptions and schemas; be especially deliberate with export, submit, upload, trigger and study operations.

Continue to **Step 4 — Review & Deploy**. The wizard **automatically generates a plan** containing the backend identity fingerprint, discovered tools, selected allow-list, live `targets.json` SHA-256, proposed new entry, warnings, and Quick connector command. Verify that the target name, region, URL and selected tools are correct.

For a **new Lambda target only**, select **Deploy approved plan** and explicitly confirm. The gateway rechecks tool discovery and the registry hash, backs up the original registry, adds only the approved target, then runs MCP `initialize`/`tools/list` on that target. If verification fails, it attempts checksum-bound rollback. Save the deployment **receipt** privately for later rollback. Concurrent/unrelated registry changes cause a conflict rather than being overwritten.

For a **matching existing target**, the wizard produces an **existing-target registration-only** plan; a mismatched URL or allow-list must not be silently replaced. Git and local flows remain registration-only.

## 5. Register the connector in Amazon Quick Desktop

**Quick registration is currently manual.** The wizard deliberately does not modify the undocumented `DIPS` SQLite database and has not established a supported Quick registration API.

Open **Amazon Quick Desktop → Customize → Connectors → Create/Add MCP** (labels may vary slightly), then enter the values generated on **Step 5 — Quick Registration**:

| Quick field | Lambda / approved local target |
| --- | --- |
| Connection type | **Local** |
| ID | Generated connector ID, e.g. `aq-my-target` |
| Name | Chosen display name |
| Command | `ssh` |
| Arguments | **One space-separated field**, shown as SSH argument chips |
| Environment variables | **EMPTY** (never paste AWS credentials, PATs or tokens) |
| Timeout | Use the generated setting, typically 120 seconds |

**Lambda/local SSH arguments (example with placeholders):**

```text
-T -q <ssh-user>@<jump-host> /home/<ssh-user>/aq-mcp/aq-run.sh <target>
```

The UI may show **five chips**: `-T`, `-q`, `user@host`, `aq-run.sh`, `target`. Do not paste the literal placeholder brackets; use the gateway and target reported by the wizard. For an **existing guarded Git** connector the generated command instead runs the approved venv Python plus `aq_git_run.py` and the Git target (six chips). The wrapper is a **local stdio MCP connection tunneled through SSH**, not a Quick-hosted network listener.

Click **Test connection**, then **Save changes**, open a **new Quick chat**, and run a harmless read from the named connector. Inspect Quick's per-action permission settings independently. A gateway-side `GATEWAY_VERIFIED` receipt does **not** prove Quick registered or executed the connector successfully.

Step 5 offers **Copy Quick settings**, **Export JSON example**, and **Inspect DIPS schema (read-only)**. The exported JSON is an example, **not a verified Quick import format**.

## Troubleshooting and safety

| Symptom | Check |
| --- | --- |
| SSH unknown/changed host key | Verify the fingerprint separately; update trusted `known_hosts` using your organization's procedure. Do not disable verification. |
| `PERMISSIONS_NEED_REPAIR` | Review ownership and listed core-file permissions. Do not recursively fix a shared venv. |
| Lambda `403` / expired credentials | Refresh the **gateway user's** authorized AWS/Okta session, then reverify the backend. |
| Wrong tools appear | Check the Function URL, region and service identity **before** deploying. |
| Plan hash changed / target exists | Regenerate and inspect; never force-replace someone else's concurrent change. |
| Tool list missing in Quick | Confirm connector Test connection, save/relaunch if needed, and start a **new Quick chat**. |
| Git read succeeds but write is refused | Check Quick action settings, repository permissions and the guard. Feature-branch rules are **not** repository allow-lists. |

**Security boundaries:** Secrets stay on the gateway, never in Quick's environment field or a deployment manifest. Git PATs are entered via the gateway's approved hidden interactive prompt, **not** piped to `set_secret.py` over a nonexistent stdin token API. Enforce exact tool allow-lists and retain readback/rollback receipts. Do not claim the wizard has automated Quick database registration.

## Repository status

- **Current GitHub source:** v0.1 engineering MVP, retained below for historical reference.
- **Latest validated handoff:** v0.3 ZIP distribution, with backend verification, automatic planning, create-only gateway bootstrap and manual Quick registration. Its source still needs a **separate reviewed promotion to this repo**; do not assume this README change deploys it.
- **Recommended next change:** promote the exact v0.3 source and tests to a feature branch, verify Windows + clean Linux gateway, then update the version/checkout instructions and publish a tagged release.

---

## Legacy v0.1 engineering documentation

A runnable **Windows desktop wizard** for onboarding MCP targets to the **existing** registry-driven 3090-style gateway. It has a five-step tkinter GUI, strict SSH host-key verification, live Lambda MCP tool discovery, preview+CAS registry deployment, real `tools/list` health checks, automatic failure rollback, and guided Quick Desktop registration.

**Status:** 21 automated tests passing locally (Linux). **No live Windows Quick or 3090 acceptance run yet.** It is not a production-ready or fully automatic Quick connector installer. Requires an existing reviewed `~/aq-mcp` gateway with Python/venv and credentials; does not bootstrap a new gateway, deploy a new Docker image or patch your existing production wrapper code.

## Start on Windows

1. Install Python 3.8+ from python.org with tkinter/Tcl/Tk. Recommended Python 3.11 or 3.12.
2. In **PowerShell or CMD**, unzip this package to your chosen folder and run:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   .\.venv\Scripts\python.exe wizard.py
   ```

   Or double-click `start_wizard.bat` after creating `.venv` and installing dependencies. It uses the local interpreter. No admin rights are required.
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
.\.venv\Scripts\python.exe cli.py export templates/example_lambda_manifest.json --output-file connector-example.json
.\.venv\Scripts\python.exe cli.py inspect templates/example_lambda_manifest.json
.\.venv\Scripts\python.exe cli.py discover templates/example_lambda_manifest.json
.\.venv\Scripts\python.exe cli.py plan templates/example_lambda_manifest.json --plan-file approved-plan.json
.\.venv\Scripts\python.exe cli.py apply templates/example_lambda_manifest.json --plan-file approved-plan.json --approve-target demo-epg --receipt-file applied-receipt.json
```

The manifest, plan and receipt have **no secret tokens** but contain internal hostnames and URLs: handle them as internal-only files. Plan and receipt exports refuse to overwrite existing files. Never run `apply` until you have inspected your plan. A known-good rollback command after approval is:

```cmd
.\.venv\Scripts\python.exe cli.py rollback --receipt-file applied-receipt.json --host trusted-jump.example.internal --user engineer --approve-target demo-epg
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
