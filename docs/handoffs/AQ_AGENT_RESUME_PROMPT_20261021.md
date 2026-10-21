# Successor agent start prompt — AQ-MCP P1 continuity

You are taking over the AQ-MCP Connector Wizard/Quick-Wrapper engineering work temporarily. **Read the branch handoff first**: `docs/handoffs/AQ_P1_CONTINUATION_20261021.md` on `feature/aq-p1-continuation-handoff-20261021`. Read it in full and treat it as a status handoff, **not** an authorization to publish or to run unqualified software on a credential-bearing host.

## Mission

Complete the **bounded, safe macOS synthetic-only engineering preview** for an Apple Silicon evaluator, while preserving the separate Windows preview and frozen D-2 design. Continue product work locally through evidence, focused fixes and independent gates. Do not claim it is a qualified release or share it yet.

## First work: establish authority and don't overwrite parallel work

1. Verify the connected repository, current refs and base SHA. The actual v0.4 developed source is still an **uncommitted local 53-file work copy**; the public GitHub feature branch at `165a4beb1d7cc085c4d898fbb6ea16dee8bbf43a` does **not** hold the later source. Find the authoritative local `Quick-Wrapper-v04-work`, `aq-preview-p1`, `aq-preview-p1-mac` and gate artifacts. Read-only first; do not reset, switch branches in the source tree, force-pull, delete or alter parallel tasks.
2. Recover the latest Mac N2 Rev 3 tripwire repair and actual Mac runner; the supplied scrubbed snapshot is **older and unqualified**. Use saved backups and all available receipts to map files/hashes to gates; don't assume a "completed" notification proves the final disk bytes. Prove 40 pinned full SHA-256 values. Keep original private identity terms and original ZIP **off GitHub**, other agents' cloud workspaces and any external handoff.
3. Produce a short **authority/status matrix** listing the current exact files, full hashes, gate results, gaps and concurrent editors before any mutation.

## Work autonomously within guarded scope

- Fix the Mac enforcement checker so **all required** tripwires must arm, with a check before any relevant product import/Tk callback, including gateway, process, networking, thread and out-of-scratch file paths. Missing/unpatchable means FAIL; require an exact `TRIPWIRE-SET: required=N armed=N missing=0` record and adversarial tests. Not a sandbox.
- After N2 is accepted, complete the Mac runner's matching tripwire count, exact-first-line strict manifest parsing, case/Unicode sensitive-name checks, Python/Tk provider observation and scrubbed `-S` Tk initialization. No automatic downgrade or pip install; do not open the normal wizard/bootstrap/CLI gateway routes on macOS.
- Finish the **test-suite containment audit**: determine which of ~493 tests could install dependencies, talk to the network, access credentials or write outside scratch. Limit the first execution accordingly; never equate inferred/skipped checks to executed passes.
- Independently Test + Security gate the **exact final** Mac runner/enforcement/builder/shared viewer and smoke script. Model/Linux tests do not prove Mac GUI behavior.
- Complete Mac-only README, expected-behavior table, manifest and handoff; build from the authoritative 40 locally pinned files and the validated **private terms file** with `--require-scanned`. Verify 47 exact archive members and publish full SHA-256 only as evidence, not a public product. Do not ship private terms/backups/stale archives.
- Keep Windows separate: the Windows Reviewer was still running; latest Windows Tester delta had passed with notes. Do not mix Windows and Mac gate claims. Windows real build/acceptance remains pending and is not a blocker for Mac evaluator.
- First independent real-Mac run remains mandatory before external distribution. An isolated Mac with networking disabled and no credentials is preferred. A cloud Mac demands explicit separate cost, upload and network-exception review.
- Keep the D-2 piece 2b **design-only** freeze unchanged; B2 and piece 2c remain respectively mandatory pre-grant and release-blocking; no production fixes/deployments.

## Permissions and stopping point

You may **inspect**, make narrowly scoped **local edits to isolated work copies**, prepare review reports, run safe synthetic tests only in approved isolated environments, and prepare non-published artifacts. Do **not** commit/push product code, change the public repository beyond this already-created documentation branch, create public release, install dependencies on daily drivers, change any gateway, invoke real SSH/AWS/MCP/Quick targets, or give the preview to the evaluator without a new explicit user approval.

If a precondition fails, stop that action and report the exact observed failure. Do not add override flags or silently weaken security constraints to obtain green tests.

## Return format

Supply a concise matrix of: artifact/path, SHA-256, source/branch, executed vs static/inferred checks, tests passed/skipped/errors with exact reasons, Security/Tester/Reviewer verdicts, blockers, and the next safe action. Also identify precisely which work can continue without waiting for the original coordinating agent and which approval is required next.
