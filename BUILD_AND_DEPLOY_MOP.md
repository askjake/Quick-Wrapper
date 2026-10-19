# MOP: AQ-MCP Wizard v0.3 — Validate, provision, deploy, recover

**Change control:** no production runtime replacement, no Quick database edits, no tokens in manifests, no port/service restart, no write to Git `main`/`master`. No sudo. Pilot first on a disposable Linux account/host before allowing first install on any shared enterprise jump server.

## 0. Preconditions / evidence

- Windows workstation with `py -3`, tkinter, Paramiko >=3.4<4, trusted SSH host key and key/agent authentication.
- Linux jump server with SSH access for an owned home directory. Fresh install requires Linux Python >=3.10, `python3 -m venv`, pip and network access to an approved dependency repository.
- Approved Lambda Function URL and a valid AWS identity already established on gateway (credentials never shipped from installer).
- Separate review/approval for changes to existing access modes. If other engineers rely on group write to `~/aq-mcp`, coordinate before repairing permissions.

## 1. Safe inspection on existing 3090

Open v0.2 UI, enter jump host/user/known-hosts and click **Inspect**.

The supplied gateway archive recorded root directory mode `0775` and core files such as `targets.json` mode `0664`; v0.1 rejected them. v0.2 must report `PERMISSIONS_NEED_REPAIR`, show the individual problematic paths, and **not** write anything. If `INCOMPLETE` or `FOREIGN`, stop rather than bootstrap/repair.

If changing group write permissions is approved, click **Repair core permissions** and confirm the displayed paths. Expected: permission changes only for the owned gateway directory and 5 core files, then subsequent Inspect reports `READY`. If shared access is required, **do not repair**; define a separate private gateway installation design and change control instead.

## 2. Create a gateway from scratch (fresh disposable Linux host only)

On a host with no `~/aq-mcp`, Inspect must return `MISSING`. Select **Install missing gateway**; acknowledge host package downloads and explicit new-directory creation. The worker receives a curated, SHA-checked ZIP in memory via existing authenticated SSH stdin. It will:

1. Refuse an existing, symlinked, incomplete or foreign `~/aq-mcp`.
2. Verify bundle digest and exact allowed member names; stage under an owner-private home directory.
3. Write the four curated launcher/proxy/check sources and initially empty `targets.json`.
4. Build a staged `venv`; install pinned `mcp`, `botocore`, `httpx2` from the host's configured package index; import-test.
5. Exclusively create owner-private `~/aq-mcp` then move staged contents without overwriting any existing installation. Files use mode `0600`, launcher mode `0700`, directory mode `0700`.
6. Report `BOOTSTRAPPED`, then re-inspect for `READY`. It does NOT install credentials, PATs, Docker, or Quick connectors.

Stop on any error and inspect `~/aq-mcp` before retrying. If a failure happens during the final few file moves, the private folder can be `INCOMPLETE` and requires operator reconciliation; do not automatically delete files from the new path.

**Acceptance on fresh host:** `~/aq-mcp/venv/bin/python -c "import mcp,botocore,httpx2"`, `~/aq-mcp/venv/bin/python ~/aq-mcp/aq_registry.py list`, and a `tools/list` check after the first Lambda target and valid AWS identity are present.

## 3. Add a Lambda MCP target

Pick Lambda backend, enter `https://<id>.lambda-url.<region>.on.aws[/mcp]`, discover tools, select the exact allow-listed names (nonempty), review and approve. The deployed registry entry resembles:

```json
{
  "url": "https://example123.lambda-url.us-west-2.on.aws/mcp",
  "region": "us-west-2",
  "env": "wizard",
  "note": "Installed by AQ-MCP Connector Wizard",
  "allow": ["get_programs", "list_genres"]
}
```

No tools/call is sent by discovery. New target names cannot replace existing targets. A registry SHA mismatch aborts; re-plan before retrying. Post-apply `aq_check` must show `OK` and exactly the selected number of exposed tools. The target is rolled back on health failure if the registry has not changed again.

## 4. Register in Amazon Quick

Use the generated Local connector settings. For Lambda and approved existing local targets, use `ssh` with `-T`, `-q`, user@host, `/home/<user>/aq-mcp/aq-run.sh`, target-name (UI may display five chips). For guarded existing Git, use venv python, `aq_git_run.py`, target-name (six chips). Keep Quick Environment Variables blank; do not put AWS/Git tokens there. Save connector and open a new chat for current tools. Quick DIPS is read-only inspection only; no automated SQLite mutations are supported.

## 5. Rollback and audit

Save deployment receipt. Use GUI rollback or CLI after identifying exact target and approved gateway:

```cmd
py -3 cli.py rollback --receipt-file applied-receipt.json --host trusted-jump.example.internal --user engineer --approve-target demo-epg
```

If rollback reports a conflicting hash, stop and reconcile only the changed registry entry; do not force overwrite someone else's changes. No Quick connector is automatically removed by registry rollback.

## 6. Known gaps / qualification gates

1. Windows tkinter GUI and Paramiko live host-key flow not yet executed as part of this packaging session.
2. Linux fresh-host package installation and relocated venv runtime not yet validated on a real disposable host; only mocked installation tests passed.
3. Gateway bootstrap cannot issue AWS identity credentials or open corporate network access. Verify with site security owners.
4. Git and local adapter provisioning remain out of scope; only existing target registration supported.
5. Quick local registration requires manual UI until a vendor-supported registration API is verified. SQLite row injection is prohibited.
6. Version-pinned pip dependencies are not a hash-locked wheelhouse. For production, build an approved offline wheel bundle and signed provenance.
7. Unit tests: 30 passing on Linux; Windows intentionally skips POSIX-only filesystem/subprocess tests, and should have no import errors. Record exact Windows test output as acceptance evidence.


## v0.3 backend and automatic-plan acceptance

Before deploying any selected backend, use **Test / Verify Backend** on Step 2. It must return `BACKEND_VERIFIED` with a positive MCP `tools/list` count. An existing Git/local target needs a successful live metadata handshake, not merely valid configuration. After selecting tools in Step 3, Step 4 builds the plan automatically; compare target name, Lambda URL, selected allow-list and warnings before approval. For existing targets, the plan must be registration-only. Quick registration remains manual and must use the generated one-field SSH Arguments string with empty environment variables. See `ACCEPTANCE_MOP_v0_3.md`.
