# AQ-MCP Connector Wizard v0.3 — backend qualification + automatic plans

**Status:** local engineering candidate, 2026-10-19. Not yet qualified on the user's Windows host or live gateway using this revision.

## Changes

1. **Step 2 — Test / Verify Backend.** A real remote MCP metadata handshake is required before moving to Step 3. Lambda uses the SigV4 proxy; existing Git targets use `aq_git_run.py` and the guarded Docker launcher; existing local targets use `aq_registry.py run <target>`. In all cases the wizard sends `initialize`, `notifications/initialized`, and `tools/list` only. No application `tools/call`. A successful Git config check alone no longer qualifies the backend.
2. **Step 3 — informed tool policy.** The discovered tool set is bound to the backend input fingerprint. A name-based review list warns about potentially mutating tools (not a permission or safety verdict). A specific EPG-versus-RTR Alerts mismatch hint detects the pattern shown in the user's screenshots. Selected risky tools require another explicit acknowledgment before mutation.
3. **Step 4 — plan automatically.** Entering Step 4 generates the plan asynchronously from the verified backend and selected tools. Plan details include the live registry SHA, exact allow-list, installation steps, possible risks, verification evidence, and a manual Quick registration step. Changing backend/connector identity or the tool selection invalidates deployment of the old plan.
4. **Existing Lambda registrations.** An existing Lambda target may be verified if its URL matches exactly, and can produce a registration-only plan when the selected tool names equal the installed allow-list. No gateway mutation is performed. Differing URL/allow-list refuses; no edit-in-place behavior.
5. **Step 5 — manual Quick walkthrough.** Provides Local, ID, name, `ssh` command, one-line Arguments input, numbered expected chips, empty environment variables, connection test, Save changes, NEW chat verification, and permission review. Export is advisory; DIPS remains read-only.
6. Retains create-only bootstrap, explicit permission repair, strict host-key trust, guarded registry transactions, health verification, and byte-checksummed rollback from v0.2.

## Verification evidence

- `xvfb-run -a python -m unittest discover -s tests -q`: **41 passed**, including real Tkinter UI navigation in an X virtual display and synthetic MCP subprocess tests.
- POSIX/Linux-only filesystem tests are deliberately skipped on Windows, not imported through a top-level `fcntl` dependency.
- **Not tested:** live Windows Quick UI registration, credentials/SSH to the user's hosts, GHES/GitLab live containers or token validity with v0.3.

## Known limitations

- A backend metadata handshake validates the configured MCP endpoint's ability to list tools. It **does not** verify tool semantics, read-only status, intended service identity beyond limited heuristics, credential lifetime, or actual tool execution.
- Configured existing Git/local targets can be verified and registered in Quick but cannot be newly provisioned by v0.3. A fresh gateway only includes the Lambda adapter.
- Unknown Quick registration API: **never write the DIPS SQLite store**. Manual GUI registration is required.
- The gateway bootstrap doesn't provision AWS credentials, Git PATs, Docker images, corporate CAs, or Quick permissions.
- Generated plan risk classification is name-based and advisory; all chosen tools should be reviewed against their actual descriptions and schemas.
- Bootstrapped Python dependencies are pinned by version, not wheel hashes.
