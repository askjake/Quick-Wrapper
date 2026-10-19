# Acceptance MOP — AQ-MCP Connector Wizard v0.3

## Scope and authorization

This checklist qualifies **v0.3 wizard behavior**. Begin read-only. Do not test against an unrelated production target or paste secrets into Quick fields, commands, screenshots, or tickets. The wizard preserves the v0.2 rules for mutations: create-only Lambda targets, explicit review, remote preflight, per-target allow-list, backup, health check and checksum-bound rollback.

## Workstation installation

Extract into a NEW folder rather than overwriting an open v0.2 installation. In Windows Command Prompt in the extracted folder:

```cmd
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -v
py -3 wizard.py
```

Expect POSIX-only integration tests to say SKIP on Windows. No import error for `fcntl` should occur. If a test fails, stop before applying a registry change.

## Test A — existing ready gateway (read-only)

1. Step 1: choose trusted jump host, SSH user, verified known_hosts; click **Inspect gateway**. Expect `READY` or an actionable non-ready state.
2. Step 2: choose Lambda, enter a NEW target name such as `test-readonly-20261019` and the actual, separately confirmed IAM-protected Function URL. Click **Test / Verify Backend**. Expect `BACKEND_VERIFIED`, `initialize/tools/list`, a positive tool count, and visible tool names. This requires working AWS credentials on the gateway.
3. Change the Lambda URL to a different URL and click Continue. Expect **Backend verification required**. Restore the proper URL and retest.
4. Confirm the displayed tool names match the intended service. **An EPG-labeled backend that lists RTR Alerts/export tools is a mismatch; recheck the URL before proceeding.** The matching heuristic is a warning, not authoritative identity proof.
5. Step 3: select only approved, harmless read tools, not export, upload, plan, trigger or study actions. Continue.
6. Step 4: observe the **automatically generated plan**—without pressing Refresh. Confirm the target, gateway, registry base hash, exact selected allow-list and manual Quick instructions are correct.
7. Stop here for a no-write acceptance run. Saving/exporting does not install a Quick connector.

## Test B — existing installed Lambda target (read-only)

1. Choose an existing Lambda target and its exact deployed URL.
2. Click Test / Verify Backend. Expect `existing_target: true`, read-back installed allow-list, and successful MCP metadata probe.
3. Step 3 should preselect the tool names currently allowed by that installed target (if offered). Continue; Step 4 should generate `existing-target-registration-only`.
4. An installed URL or allow-list mismatch must fail closed; no registry mutation may occur. The target remains unchanged.

## Test C — Git/Local backend (metadata only)

1. Choose an existing `github-ghes` or `gitlab` Git target. Click **Test / Verify Backend**. It must start the approved guarded launcher and receive MCP `tools/list`. The presence of `git_targets.json` alone does not qualify. If the token/guard/Docker/server isn't ready, expect failure.
2. Choose the existing `build-artifacts` local target (if installed). Test again. The local MCP process must respond to `tools/list`.
3. Continue to Step 4. Plan must say registration-only: **no Docker, Git guard, PAT, local server, or registry mutation**.

## Test D — approved Lambda creation (optional write)

Only on a new, disposable target name with safe selected tools and your explicit authorization:

1. Read Step 4 plan and approve deployment. If selected names appear potentially mutating, explicitly review that extra warning.
2. Expect `GATEWAY_VERIFIED` and an exact deployment receipt (before/after SHA-256 and backup name). Verify that one new target is present, previous targets unchanged.
3. Save the receipt privately. If desired, test rollback before other registry writes; rollback refuses if registry bytes have changed in the meantime.
4. If the target already exists and matches installed config, expect `EXISTING_TARGET_VERIFIED` and **no registry backup or mutation**.

## Test E — manual Amazon Quick connector registration

1. In Step 5 read the exact field-by-field instructions. In Quick Desktop open **Customize > Connectors > Create/Add MCP**.
2. **Connection type:** Local. **ID:** generated `aq-<target>`. **Name:** as selected. **Command:** `ssh`.
3. **Arguments** (ONE space-separated field, shown as chips): `-T -q <ssh-user>@<jump-server> /home/<ssh-user>/aq-mcp/aq-run.sh <target>` for Lambda/local, or the generated six-part Python + `aq_git_run.py` form for existing Git.
4. **Environment variables:** empty; never put AWS credentials, PATs or tokens in Quick configuration.
5. Click **Test connection**, then **Save changes**. Open a **new Quick chat** to refresh its tool inventory. Verify a harmless read and per-action permissions.
6. This is **manual**, not a Quick SQLite database change. Exported JSON is an example only, not a verified import contract.

## Evidence to return

The Step 1 inspection state, Step 2 sanitized verification summary and warnings, Step 4 redacted plan or receipt, and the Quick `Test connection`/safe-read result. Remove personal login, host/IP, Function URL identifiers, token values and client directories from externally shared captures.

## Fail-safe

Do not bypass host-key verification, mutate the DIPS database, downgrade write restrictions, or overwrite existing registry entries to make a test pass. When a plan is stale, regenerate it; when the endpoint is wrong, correct it and reverify. Live AWS credential expiry and actual Quick registration are independent of a successful offline test suite.
