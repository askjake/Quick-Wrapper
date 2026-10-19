# Method of Procedure — AQ-MCP Wizard v0.1

## 0. Scope and change classification
- **Plan/Discovery**: SSH and MCP `initialize` + `tools/list` only; existing proxy may write operational logs. No registry changes.
- **Apply**: only `~/aq-mcp/targets.json` and a backup/lock under `~/aq-mcp`; only a **new Lambda target**.
- **Existing Git/Local**: checks and Quick registration instructions only. Does not change any registry entry or token.
- **Quick desktop**: manual registration; no writes to DIPS.

## 1. Preflight
1. Confirm host identity and verify server's SSH host-key fingerprint from an independent approved channel; populate local `known_hosts`. Do not disable host-key checking.
2. Check the gateway already works: `~/aq-mcp/venv/bin/python ~/aq-mcp/aq_registry.py list`. Do not expose tokens.
3. Refresh AWS credentials on the gateway if the existing Okta-backed credential chain has expired.
4. Make sure the Lambda URL is exact and belongs to the intended AWS account/region (account ownership is an operator decision; URL syntax alone cannot verify ownership).
5. Identify tools that are read-only vs. potentially mutating by inspecting descriptions/schemas with their owners. Do not trust names/annotations alone.
6. Do not operate concurrently with another editor of the same registry target. The wizard uses a CAS hash to refuse stale updates, but external writers not using its lock can still race at the file level.

## 2. Deploy a Lambda target (GUI)
1. Launch `py -3 wizard.py`.
2. **Gateway**: supply SSH host, user, known_hosts; click `Test SSH / inspect gateway`. Verify existing target list and checksum.
3. **Backend**: Lambda URL, an unused lowercase target name, and a Quick display name.
4. **Tools**: click `Discover`, select a reviewed subset. No tool call is executed, and all selected names are re-discovered before apply.
5. **Review**: generate plan, verify SHA and target entry, click Deploy and approve. The wizard atomically adds the entry and runs `aq_check.py` to verify initialization and filtered tool list.
6. **Quick**: copy suggested arguments, create a Local MCP connector, leave Environment Variables empty, save, open a fresh Quick chat, test a read-only MCP call.
7. **Evidence**: capture target name, registry before/after SHA, backup filename, read-only health outcome, and a screenshot of Quick tool discovery (sanitize personal connection details).

## 3. Failure and rollback
- SSH unknown/changed key: **STOP** and verify out-of-band. Never AutoAdd.
- Invalid Lambda URL or zero selected tools: **STOP**; no remote change.
- Stale registry hash / duplicate target: **STOP**; re-inspect and replan.
- MCP discovery failure: **STOP**; look for expired AWS credentials or upstream service issue.
- Health check failure after write: wizard attempts immediate CAS-protected rollback. If registry changed again, it refuses rollback; operator must reconcile current state manually.
- Quick registration did not appear: check connector's saved command and arguments; edit and save to relaunch and start a new chat. Do not edit Quick's SQLite store manually.
- Manual rollback: use latest receipt with the exact target; it restores only if the installed registry SHA still matches the deployment receipt.

## 4. Acceptance checklist
- 21+ local unit tests pass.
- Windows UI launches without import errors; Paramiko from Python environment is present.
- Authorized SSH key and host-key verification pass; unknown host is refused.
- Target discovery returns exact names and selected subset filters correctly.
- Dry-run makes **no registry writes**.
- Apply to a sandbox Lambda and observe `GATEWAY_VERIFIED`.
- Simulated tool/credential failure triggers correct rollback; parallel registry edit triggers conflict and does not overwrite.
- Quick connector is added **manually**, a fresh chat lists the selected tools, and one benign read call succeeds.
- Verify no secrets were written to Quick, files, logs or export.

## 5. Phase 2 (design only)
A versioned gateway bootstrap installer and automated Quick registration require separate qualification. Never write directly to live undocumented DIPS tables simply because a schema could be inspected. Obtain provider-supported API/import/CLI behavior, connector lifecycle checks and an end-to-end rollback first.

**Rollback receipt:** The GUI can save a deployment receipt on the Review screen. Retain it privately. The CLI can use it after the wizard closes. If the registry changed in parallel, rollback stops rather than reverting someone else's work.
