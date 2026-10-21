# AQ-MCP Connector Wizard — continuation handoff (2026-10-21)

**Internal engineering coordination, not a release.** This public-repository document contains no private scan terms, credentials, internal hosts or unpublished source code. It records unfinished work so a successor agent can recover the real local source. Do **not** give these artifacts to an end user as a qualified release.

## Repository and authoritative source

- The existing v0.4 feature branch `feature/native-local-gateway-v04-20261019` was checked at commit `165a4beb1d7cc085c4d898fbb6ea16dee8bbf43a`. It is **not** the latest source.
- The 53-file developed work copy is **uncommitted** in the local folder `Quick-Wrapper-v04-work`. Two additional local tooling folders, `aq-preview-p1` and `aq-preview-p1-mac`, contain preview work in progress. The public repo does not contain this work. An agent cloning GitHub alone cannot reconstruct it.
- A private identity-terms file is held separately. The raw conversation snapshot archive contains that private file, old revisions and partial files: **NEVER push or distribute the raw archive.** A separate identity-screened internal transfer bundle is only an unqualified snapshot. Reconcile all supplied bytes against the authoritative latest local work before acting.
- This handoff branch exists for continuity only, not permission to publish code, merge to `main`, create a production release or contact real gateways. Code publication requires a dedicated explicit decision plus the unresolved repository-history/credential audit.

## Primary objective: safe macOS engineering preview

Provide a **synthetic-only** command/argument and Quick-registration viewer, guarded smoke checks and reviewed test execution to a macOS evaluator. The evaluator's environment is Apple Silicon `arm64`, macOS 27.0.1, CPython 3.13.16 and Tcl/Tk 9.1.0. Direct `Tk()` initialization succeeded on Aqua under the normal interactive environment; scrubbed `-S` Tk initialization, actual preview rendering, clipboard and callback behavior remain **unverified**. No version downgrade without evidence.

The normal wizard, real Quick profile, CLI deploy/apply, bootstrap, SSH/AWS/MCP, credentials, network and backend connections are **excluded** from the preview. A **known product HIGH** remains: `native_gateway.py` qualifies its supported interpreter only under `os.name == 'nt'`; on macOS native bootstrap can run an **unhashed network pip install**. Do not expose this route to the evaluator. Product remediation is a separate gated change; never silently alter the pinned product source in the preview.

### Current Mac preview state

- Final planned ZIP is **47 members**: 40 pinned product files plus the synthetic viewer, smoke script, Mac runner, Mac enforcement check, Mac README, Mac expected-behavior table and manifest.
- Candidate local Mac tools: `build_preview_package_mac.py`, `mac_enforcement_check.py`, `run_preview_mac.py`; the common `smoke_preview.py` and `preview_viewer.py` must match the final independently verified Windows bytes.
- Mac builder initial 200-check self-test reportedly passed in Linux/cloud, **not** a real Mac or final candidate build. Mac Tester previously PASS-WITH-NOTES, Security/Reviewer safe-with-conditions, **not cleared for user distribution**.
- **Critical incomplete repair:** Mac enforcement check Rev 2 (historical 59,144 B) allowed a partially armed tripwire set to PASS. Rev 3 was in progress at handoff. Require **every** required tripwire armed (no optional target or minimum floor); missing/unpatchable is FAIL. Emit `TRIPWIRE-SET: required=N armed=N missing=0` before `ENFORCEMENT RESULT: PASS`. Arm before relevant product imports/Tk creation and maintain coverage through timer/callback windows. Cover subprocess, fork/exec/spawn, sockets/sendto/urlopen/http client, threads/pools/multiprocessing, gateway entry points and filesystem mutations outside the throwaway area. Independent adversarial Tester/Security gate required. These are accidental-action tripwires, **not a security sandbox**.
- The Mac runner follow-up should pin the complete N2 required set, exact manifest header position/UTF-8/LF/CR/BOM/NUL checks, forbidden Mac archive metadata names, Tk/Tcl patch levels and provider classification, scrubbed `-S` Tk-root probe, strict test counting and real member hashes. No in-progress file is presumed accepted.
- Test-suite containment inventory (~493 unittest methods) was in flight. Determine which tests can install, reach network, read credentials or write outside the scratch area before running them. Linux/POSIX model checks and inferred skips are **not Mac acceptance**.
- Before any handoff to the evaluator, final Mac Tester/Security/Reviewer gates **on the exact final bytes**, full scan `--require-scanned`, verified 47-member archive and out-of-band full SHA-256, and a successful isolated first Mac run **by a separate qualified person** were planned. No physical Mac was identified. Cloud Mac would need a separately reviewed network exception and cost/transfer approval; no automatic bypass.

### Isolation and leak control

Dedicated nonprivileged account if credentials exist, no networking, sanitized environment/HOME/TMPDIR and no real profile, no iCloud-synced staging, strict read-only package inputs, no arbitrary clipboard. Never run the ordinary wizard or invoke gateway-reaching CLI. Every missing tripwire or manifest discrepancy stops. A `SCANNED` marker is a bounded leak check, not proof of absence of secrets; keep private terms and raw scan hits off GitHub, reports and ZIPs. Never use skip/override flags to manufacture acceptance.

## Windows P1 (parallel but not blocking macOS)

Local folder `aq-preview-p1` with 40 product pins and a planned **46-member** Windows P1 ZIP. Shared prior readbacks: `preview_viewer.py` 35,325 B (SHA prefix `4f5b20a58ded`), `smoke_preview.py` 34,135 B (SHA prefix `f7a662449873`). Latest reported Windows runner `run_preview.py` 62,656 B (prefix `71b7de774667`). Treat these as historical evidence, not substitutes for full-hash/current-byte checks. Windows Tester delta had PASS-WITH-NOTES and the independent Windows Reviewer was **running** on verified staged bytes at handoff. The final real ZIP, first Windows Sandbox run and colleague delivery were **not done**. Windows Sandbox on the available managed workstation remained uncertain/likely unavailable; Windows VM is **not a prerequisite** for the Mac evaluator. Host-side Quick Import S6 is held.

The private terms file was reported as 40 distinct terms and later unexpectedly 43 nonempty lines. Reconcile privately, without logging contents. Do not distribute an old `PREVIEW_README.zip` or any stale backups.

## Frozen D-2 design — separate workstream

Piece 2b contract Draft 8 **design-only** freeze: 86,684 B, SHA-256 prefix `d1d2295fcc77`, Security SAFE-TO-FREEZE and Tester PASS-WITH-NOTES. The original contract is held in private local artifacts, **not present in GitHub**. Interpretation notes: (1) serve only if every check completes successfully; otherwise refuse; (2) no in-request grant-file *read* retry, independently of allowed idempotent revocation/rollback retries. This freeze authorizes **no implementation**. B2 gateway-ID marker amendment is a mandatory separately gated dependency before grant issuance. Piece 2c still **release-blocking** for revocation-record deletion and marker/policy double-deletion. Linux-only durability, Windows daily-driver qualification blocked. Do not confuse design gates with implementation acceptance.

## Immediate action queue for a successor agent

1. **Read-only source recovery:** fetch branch and verify commit; inventory current local 53-file product work copy, both tooling trees, active tasks and backup candidates. Check all 40 pinned full SHA-256 values. Do not overwrite, stage, commit, push, merge or deploy before reconciling local authority and receiving separate approval.
2. **Finish Mac N2 Rev 3**, validate AST/byte scope against its real backup, full tripwire set and early arming, then independently adversarial-test and Security-review final bytes.
3. **Close Mac N1** after N2 is frozen: exact required-tripwire equality, secure manifest/parser, scrubbed-Tk check, environment/provenance observations, containment review of the full suite. Test **actual builder-generated** manifest with the runner and viewer; fabricated fixtures are insufficient.
4. **Verify Windows shared files and gates** separately; only mark shared-bytes record approved when actual final full hashes match.
5. **Build/test Mac-only docs and package** with independent Tester/Security/Reviewer and local private-term `--require-scanned` execution. Check 47 exact members, archive/manifest hashes, no private backups/terms, deterministic ZIP and user-facing limits. Handoff sits **beside** the acceptance-tested ZIP.
6. **First isolated Mac qualification run**, actual GUI/temporal callbacks and no network/credential accesses; record pass/skip/exception evidence. Request fresh user approval **before** sending anything to evaluator, publishing product code or touching gateways.

For every step, label evidence as **EXECUTED**, **STATIC/MODELED**, **INFERRED**, **SKIPPED**, or **NOT RUN**. Report exactly which gates read which bytes, test counts and skip reasons, current SHA-256s, remaining blockers and one safe next step. Never claim the source is complete just because a developer reports it, or that public GitHub reflects uncommitted laptop files.
