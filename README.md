# Quick-Wrapper — AQ-MCP Connector Wizard v0.4 (engineering candidate)

**No administrator rights or WSL2 required for native localhost.** v0.4 introduces a user-owned gateway on the **same computer running Amazon Quick**, using direct Python/stdin/stdout MCP instead of SSH. Its new Lambda targets keep exact tool allow-lists, backend discovery, SHA-256 registry checks, rollback receipts, and manual Quick connector registration. **Existing Linux SSH gateways are unchanged.** Windows native-local execution has not yet passed a live workstation acceptance run.

**[Native-local operator MOP](NATIVE_LOCAL_MOP.md)** · **[v0.4 release notes](RELEASE_NOTES_v0_4.md)**

## Run v0.4 on Windows — test this feature branch

Use **one entire PowerShell block** from an existing clone (do not paste `else`/`elseif` lines separately). The commands never create a venv in your home directory by accident.

```powershell
$repo = Join-Path $HOME 'Quick-Wrapper'
if (-not (Test-Path (Join-Path $repo '.git'))) { throw "Checkout missing: $repo; clone it first." }
Set-Location -LiteralPath $repo -ErrorAction Stop
if (git status --porcelain) { throw 'Uncommitted changes: review or commit before switching branches.' }

git fetch origin feature/native-local-gateway-v04-20261019
if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed' }
git switch -C feature/native-local-gateway-v04-20261019 --track origin/feature/native-local-gateway-v04-20261019
if ($LASTEXITCODE -ne 0) { throw 'Git branch switch failed' }

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed; do not deploy' }
& .\.venv\Scripts\python.exe wizard.py
```

For a first-time clone, `git clone https://github.com/askjake/Quick-Wrapper.git "$HOME\Quick-Wrapper"`, then run the block above. After this branch is merged, switch to `main` and `git pull --ff-only origin main` instead of tracking the feature branch.

## v0.4 workflow — no SSH server needed

1. **Gateway:** On Step 1 select **Native gateway on THIS computer (no SSH/admin)**; inspect and approve **Install missing gateway** only when state is `MISSING`. This creates `$HOME\AQ-MCP-Gateway` with a separate gateway venv and reviewed Lambda proxy sources. Package downloads require access to your approved Python index. An existing or incomplete gateway is **never** overwritten.
2. **Backend:** Enter an AWS_IAM Lambda Function URL, click **Test / Verify Backend**, and require `BACKEND_VERIFIED` (`initialize` + `tools/list`, no application calls). AWS/Okta credentials must already be available to the local Windows account; the wizard does not provision or copy credentials.
3. **Policy:** Select an explicit **nonempty** tool allow-list, reviewing mutators and unexpected backend tool identities.
4. **Plan/deploy:** Review the generated plan, approve only the expected target, require `GATEWAY_VERIFIED`, and save its private rollback receipt. Checksum conflicts stop safely.
5. **Quick registration:** Add a new **Local** MCP connector in Amazon Quick Desktop and copy the wizard's native settings. Example: `Command = C:\Users\engineer\AQ-MCP-Gateway\venv\Scripts\python.exe`; `Arguments = C:\Users\engineer\AQ-MCP-Gateway\aq_registry.py run rtr-demo`; **Environment variables = EMPTY**. Click **Test connection**, save, open a **new Quick chat**, and verify a harmless read. Quick's undocumented DIPS database is **not** modified.

**Loopback with SSH:** `127.0.0.1` already works in the *Linux SSH* mode when the computer running Quick itself has a working Linux SSH server. Native localhost uses direct Python and therefore needs **neither `ssh` nor a listener**.

**Remote native Windows jump server:** **not yet provisioned by v0.4.** A different Windows host requires an already-authorized incoming transport (such as an administrator-provisioned OpenSSH server). The wizard does not open firewall ports, install SSH services, run WSL2, or elevate privileges. Git/Docker target provisioning remains restricted to the existing Linux SSH adapters.

---

## v0.3 Linux SSH and Windows installation documentation (retained)

# Quick-Wrapper — AQ-MCP Connector Wizard v0.3

**Windows desktop wizard for deploying and verifying MCP connectors through a trusted Linux SSH gateway.** v0.3 is now the version intended to live in this repository; the sections below describe the code in this checkout. It supports gateway inspection / create-only bootstrap, real Lambda/Git/local MCP backend verification, tool selection, automatic deployment plans, guarded Lambda registry changes and a manual Amazon Quick registration walkthrough.

> **Release scope:** Engineering candidate, not production-certified. It was tested against a Windows workstation / Linux gateway workflow, but clean-host bootstrap, Quick UI registration and every downstream MCP tool have not been independently certified. Registration is still manual, and the wizard does **not** write Quick's DIPS database. Git and local backends are **existing-target registration only**.

## 1. First-time clone and install on Windows (PowerShell)

Use **one complete pasted block**. PowerShell does not accept a separately executed `elseif` after an earlier `if` statement; the flow below avoids that entirely. This example places the checkout at `C:\Users\<you>\Quick-Wrapper` (under `$HOME`), not under Documents or the accidental `$HOME\.venv`.

```powershell
$repo = Join-Path $HOME 'Quick-Wrapper'
if (Test-Path $repo) { throw "Checkout already exists: $repo. Use the update instructions below instead." }
git clone git@github.com:askjake/Quick-Wrapper.git $repo
if ($LASTEXITCODE -ne 0) { throw 'Git clone failed; check GitHub SSH access.' }
Set-Location -LiteralPath $repo -ErrorAction Stop
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python virtualenv creation failed.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; do not deploy.' }
& .\.venv\Scripts\python.exe wizard.py
```

If GitHub SSH keys are not configured, replace the `git clone` URL with `https://github.com/askjake/Quick-Wrapper.git`. That GitHub authentication is separate from the SSH host-key verification used by the wizard to connect to the gateway.

## 2. Update an existing checkout (PowerShell)

Use **one complete pasted block** from any PowerShell directory. It fails if the expected repository is missing and does not create a virtual environment in your user home by mistake.

```powershell
$repo = Join-Path $HOME 'Quick-Wrapper'
if (-not (Test-Path (Join-Path $repo '.git'))) { throw "Git checkout missing: $repo. Run the first-time clone block above." }
Set-Location -LiteralPath $repo -ErrorAction Stop
git status --short
# Review any local edits shown above before continuing; do not discard them.
git switch main
if ($LASTEXITCODE -ne 0) { throw 'Could not switch to main; review local changes.' }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Fast-forward pull failed; do not continue.' }
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; do not deploy.' }
& .\.venv\Scripts\python.exe wizard.py
```

The commands deliberately call the interpreter in `.venv` rather than changing PowerShell execution policy to activate it. They do not use your unrelated `C:\Users\<you>\.venv`. To run again later, open PowerShell, `Set-Location "$HOME\Quick-Wrapper"`, and run `& .\.venv\Scripts\python.exe wizard.py`. Alternatively, double-click `start_wizard.bat` once `.venv` exists.

### Windows Command Prompt (CMD)

From CMD, use `%USERPROFILE%` rather than PowerShell `$HOME`. First-time clone:

```cmd
git clone git@github.com:askjake/Quick-Wrapper.git "%USERPROFILE%\Quick-Wrapper"
cd /d "%USERPROFILE%\Quick-Wrapper"
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe wizard.py
```

Existing checkout update:

```cmd
cd /d "%USERPROFILE%\Quick-Wrapper"
git status --short
git switch main
git pull --ff-only origin main
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe wizard.py
```

**CMD note:** execute stepwise and stop if any command fails; unlike the PowerShell blocks above, these reference commands do not automatically abort on failure. Do not run the commands from `C:\Users\<you>` before changing into the repository.

## 3. Five-step wizard workflow

1. **SSH Gateway:** enter host, user and trusted `known_hosts`; inspect an existing gateway or explicitly bootstrap a missing approved Linux gateway. Never overwrite an existing `~/aq-mcp`.
2. **MCP Backend:** select Lambda Function URL (SigV4), existing guarded Git target, or approved local server. Click **Test / Verify Backend** and require `BACKEND_VERIFIED` before continuing.
3. **Tool policy:** discover offered tools, inspect their descriptions/schemas, select an explicit **nonempty allow-list**. Name-based mutator warnings are advisory only.
4. **Review & Deploy:** the plan is generated automatically with the backend fingerprint, live registry hash, selected tools and approval requirements. For a *new Lambda target only*, deploy and save the receipt; verification failures trigger checksum-bound rollback where safe.
5. **Amazon Quick registration:** copy the generated Local connector configuration into **Customize → Connectors → Create/Add MCP**, click **Test connection**, save, then use a **new Quick chat** to verify a harmless read. Quick database writes are intentionally unsupported.

**Manual Quick connector example** (replace placeholders with the values printed by Step 5):

| Field | Value |
| --- | --- |
| Connection type | Local |
| Command | `ssh` |
| Arguments | `-T -q <ssh-user>@<jump-host> /home/<ssh-user>/aq-mcp/aq-run.sh <target>` |
| Environment variables | **EMPTY** (never paste tokens) |
| Timeout | Wizard-generated value (commonly 120 seconds) |

**Do not treat `BACKEND_VERIFIED` or `GATEWAY_VERIFIED` as proof of Quick-side registration.** Verification completes only after a real Quick read. Existing guarded Git uses its separate launcher and is not provisioned from scratch by v0.3.

## Security and operational limits

- Python with tkinter/Tcl-Tk is required on Windows; Paramiko 3.x is installed in the local `.venv`.
- Unknown/changed SSH keys are refused (`paramiko.RejectPolicy()`); do not disable host-key checks.
- Bootstrap installs the reviewed **Lambda gateway core** on a missing Linux host with Python 3.10+, an approved package index and separately configured AWS credentials. It does not provision AWS roles, Okta credentials, Docker images, PATs, or server certificates.
- The gateway's historical proxy treats an empty allow-list as **allow all**. The wizard therefore refuses empty allow-lists for new targets. Do not enable ambiguous export/submit/upload/trigger operations without an explicit review.
- Tool discovery/health verification uses only MCP metadata (`initialize` and `tools/list`), not application tool calls.
- Deployment protects concurrent edits with a registry SHA-256 check and maintains an exact backup/receipt for safe rollback. Review a plan before approving it.
- Auto-registration into the undocumented Quick Desktop `DIPS` store is **not implemented or supported**. Use Step 5's manual instructions.

For technical detail, see [BUILD_AND_DEPLOY_MOP.md](BUILD_AND_DEPLOY_MOP.md), [ACCEPTANCE_MOP_v0_3.md](ACCEPTANCE_MOP_v0_3.md), and [RELEASE_NOTES_v0_3.md](RELEASE_NOTES_v0_3.md).

---

## Detailed v0.3 implementation notes

# AQ-MCP Connector Wizard v0.3 — verified backends + automatic plans + guarded Linux gateway installer

## Status and scope

This is a **runnable engineering candidate**, not yet a live-tested Windows/3090 release. This v0.3 version retains the v0.2 fixes for Windows imports, historical gateway permissions, create-only gateway bootstrap and optional repair. It additionally verifies the selected Lambda/Git/local backend with a real MCP initialize/tools/list handshake, requires verification before Step 3, and generates the plan automatically when entering Step 4. Existing Lambda registry deployment, MCP `tools/list` discovery, fail-closed allow-list selection, checksum-bound rollback, and manual Amazon Quick registration remain available.

The gateway runtime bundled here was curated from the supplied `aq-mcp-backup-20261019.tar.gz` with exactly these source files: `aq_registry.py`, `aq-run.sh`, `aq_mcp_stdio.py`, `aq_check.py`. No secrets, venv, runtime logs, certs, machine-specific targets, or private Git configurations are bundled. Dependencies mirror the examined environment: `mcp==2.3.0`, `botocore==1.43.113`, `httpx2==2.13.1`. These are version pins, **not hash-locked dependency wheels**; a package-index availability and supply-chain review is needed before broader rollout.

## On Windows

Extract the ZIP into its own folder. In CMD or PowerShell, from the repository root or extracted v0.3 folder:

Use the project-local `.venv` commands from Sections 1–2 above. Do not install dependencies into the global interpreter.

Windows is expected to **skip POSIX-only remote filesystem integration fixtures**; failures are not expected. The Linux/Xvfb test run for this version is **41/41 passing**, including a Tkinter navigation test. The Windows GUI and live 3090 path must still be tested on your workstation.

The Windows app requires Python with tkinter and Paramiko 3.4–3.x. SSH is key/agent-based and uses `paramiko.RejectPolicy()`. Verify the server's host fingerprint out of band and place the confirmed key in the provided `known_hosts` path. No password fallback, automatic host-key trust, Quick-DIPS mutation or PAT collection is implemented.

## First screen: inspect, bootstrap or repair

1. Supply SSH host, SSH username and `known_hosts` path.
2. Click **Inspect gateway (read only)**. It reports one of:
   - `MISSING` — fresh Linux host has no `~/aq-mcp` and can be bootstrapped.
   - `READY` — installed core files have no group/world write access; add targets normally.
   - `PERMISSIONS_NEED_REPAIR` — historical owner-owned core files are group/world writable; inspection is allowed, **deploy/apply is blocked** pending explicit repair.
   - `INCOMPLETE`, `FOREIGN`, or `SYMLINK` — cannot be bootstrapped over or silently repaired; stop and investigate.
3. If `MISSING`, click **Install missing gateway** and confirm the creation and dependency downloads. The host needs Python **3.10+**, `venv` with pip, and access to an approved pip index containing the three pins and transitive dependencies. Installer stages source/venv in an owner-private temporary directory, tests Python imports, exclusively creates `~/aq-mcp` (mode `0700`), and moves the validated files. A collision refuses to overwrite. If file activation unexpectedly fails after creation, the root is left **private but incomplete** for manual reconciliation.
4. If `PERMISSIONS_NEED_REPAIR`, click **Repair core permissions**, read the exact list and approve deliberately. Only the SSH-user-owned directory and **five core files** (`targets.json`, `aq_registry.py`, `aq-run.sh`, `aq_mcp_stdio.py`, `aq_check.py`) with excess write permissions are changed, removing `g+w`/`o+w`. This can affect workflows expecting shared group writes; do not approve without checking. No other configuration, Git targets, secrets or running services are modified. **Important:** the historical venv also contained group-writable directories/packages. The wizard reports writable venv-directory warnings but does not recursively chmod or rebuild that shared virtual environment; this core-file repair is not a complete security hardening certificate. Re-inspect until `READY`.
5. **Never click Bootstrap on the existing 3090 gateway**. The historical backup shows `aq-mcp/` mode `0775` and registry/core sources `0664`; the existing installation needs an operator-reviewed permission decision, not a replacement.

### Equivalent headless commands (optional)

```cmd
py -3 cli.py bootstrap --host approved-jump.example.internal --user engineer --approve-bootstrap
py -3 cli.py repair-permissions --host approved-jump.example.internal --user engineer --approve-repair
```

The CLI immediately checks the live state; neither command overwrites an existing gateway. Avoid putting internal addresses and usernames into externally shared scripts or screenshots.

## Configure a Lambda target

The new runtime contains an initially empty `~/aq-mcp/targets.json`. For either newly installed or existing ready gateways:

- Choose **AWS Lambda Function URL** (IAM/SigV4) and a lowercase target name, then enter the **HTTPS Lambda Function URL** with the correct region. URLs outside the exact Lambda Function URL shape are rejected.
- Click **Discover offered tools**. This uses the gateway's AWS identity and MCP `initialize` + `tools/list` only. It does **not** call application tools.
- Select an explicit **nonempty** allow-list. The underlying proxy currently treats an empty allow-list as exposing every tool; v0.2 refuses it.
- Generate a deployment plan. Review the exact proposed target entry and live registry hash.
- Deploy with explicit confirmation. It re-discovers the exact tools, checks the registry SHA, takes a protected byte-exact backup, writes only the new target, runs `aq_check.py` for `tools/list`, and on failure requests checksum-guarded rollback.
- On the **Quick registration** screen, copy the Local SSH connector arguments into Amazon Quick Desktop; save and open a new chat to refresh the tool list.

**Fresh host credentials:** the installer **does not create or copy AWS/Okta credentials, IAM roles, Git PATs or corporate certificates**. For Lambda tool discovery, the host must already have valid authorized AWS credentials available to the SSH user's normal botocore credential chain. Installing the gateway and authenticating it are distinct tasks. Corporate Okta credentials can expire.

## Git and local modes

These modes remain **existing-target registration only** in this version. Git requires a preconfigured `aq_git_run.py`, Docker images, `git_targets.json`, an operator-installed PAT and `aq_git_guard.py`. Local requires an existing whitelisted `local` registry entry. A freshly installed Lambda-only gateway cannot automatically configure GHES, GitLab or Build Artifacts without a separate reviewed adapter installer. Neither backend accepts arbitrary local script paths.

## Amazon Quick auto-registration

DIPS SQLite is not a validated writable connector-registration API. We intentionally **do not modify it**. Generate the exact Quick connector name, `ssh` command and chips (Lambda/local: launcher + target, Git: venv Python + Git launcher + target). The user finishes registration in Quick's UI. The code can inspect only DIPS schema names read-only; it cannot insert connectors or grant tool permissions. Fully automatic Quick registration awaits a supported interface and a full lifecycle test.

## Recovery and limitations

After a successful deployment, save the private receipt on the Review page. Rollback is allowed only while the registry bytes still have the exact post-deployment SHA; parallel edits cause a conflict rather than being overwritten. No running services are restarted and unrelated checkout files are untouched.

The bootstrap is a **new-host source/package installer**, not identity provisioning. The staged venv is relocated; use `~/aq-mcp/venv/bin/python -m pip` (not the installed `pip` console-script shebang) for any later package operations. The runtime itself launches via the Python executable. This relocation path has not yet been accepted on a clean Linux host; live qualification must confirm the interpreter, `mcp` imports and tool discovery after relocation.

## New v0.3 user flow

**Step 2 now includes `Test / Verify Backend (MCP handshake)`**. For Lambda it uses the SigV4 signer and configured Lambda URL. For Git it starts the existing guarded `aq_git_run.py` launcher and requests only MCP metadata. For Local it starts the existing approved target through `aq_registry.py run`. An existing target is not installed by this test. Tool listing proves only protocol connectivity, not tool safety or functionality.

**Step 3 uses the verified tool inventory**. Select explicit safe tools. The wizard warns about potentially mutating tool names and a specific EPG-vs-RTR Alerts mismatch observed in the October 19 demo. Names are merely heuristic clues; inspect descriptions and schemas to determine risk.

**Step 4 generates the plan automatically** after Step 3. Manual `Refresh deployment plan` remains available. The plan contains a backend identity fingerprint, exact selected allow-list, registry hash, action list, warnings, and Quick registration information. Changing the endpoint or tool selection invalidates the old plan. A matching existing Lambda target gets a *registration-only* plan rather than an attempted duplicate deployment.

**Step 5 is a complete manual Quick MOP**: choose `Local`, fill ID and name, enter `ssh`, paste the space-separated Arguments field, leave environment variables EMPTY, Test connection, Save changes, open a new chat and perform a safe read. Quick auto-registration has not occurred, and the DIPS database is never modified.

See `RELEASE_NOTES_v0_3.md` and `ACCEPTANCE_MOP_v0_3.md` for limits and step-by-step qualification.
