# AQ-MCP P1 viewer-only macOS preview, R3E (UNQUALIFIED ENGINEERING PREVIEW, candidate)

**Status: NOT A QUALIFIED RELEASE. Unqualified engineering preview.** This folder is published for inspection only. Publication does not authorise anyone to run it. No licence is granted (all rights reserved). Do not run Part B (the GUI run) on any employer-managed Mac. That requires (1) the employer's written approval and (2) a Security decision for that exact managed machine and these exact bytes. Neither is recorded here. Use only the commit SHA you received out-of-band and stop if `git rev-parse HEAD` differs.

## What this is

A synthetic-only Tk preview built from the real pinned wizard source, for a first look at whether the actual GUI draws on macOS. It is not a connector installation. It needs no pip, no venv, no gateway, no SSH service and no administrator credentials, and it contacts no real service. The ZIP is the exact, unmodified R3E candidate. It has never been run on macOS to a working window; the checks it has had are listed in the README inside the ZIP. Its self-test must print `SELFTEST PASS`; the number of checks it prints is diagnostic.

| File | Size (bytes) | SHA-256 |
|---|---|---|
| `preview-p1-mac-viewer-only-r3e.zip` | 459418 | `a386352b68f02f927aea8701b233d20985bc0e1514b0594ed4b837ee82ed7c17` |
| `preview-p1-mac-viewer-only-r3e.manifest.sha256` | 101 | `85994e4e66645846ed41fa35cbed298dfe08e03632a8e6e97a30c6b57df18a2c` |
| `run_r3e.sh` | 8269 | `f02b08003a13cc8e8c1d1de512108ff0fb96392be6537999c603fe5c80229798` |

The launcher checks the ZIP hash itself. It is the reader's anchor if this README is altered. The default command does nothing but check files.

## One command, verification only (the default)

From a checkout of the commit you were given:

```bash
bash mac-preview/r3e/run_r3e.sh
```

With no argument (or with `--verify-only`, which does the same thing) the launcher only verifies. It checks the ZIP size and hash (the pinned anchor), the side manifest (a consistency check only), archive integrity, the exact ten-file inventory, the embedded manifest digest and the packaged README's hash, using system tools, prints the result and exits. Nothing from the package is executed and nothing is written. Any argument other than `--verify-only` or `--run-gui` stops it. A passing check proves the bytes are correct only if your own shell environment has not been tampered with.

## Running the GUI is a separate, deliberate step

```bash
bash mac-preview/r3e/run_r3e.sh --run-gui
```

`--run-gui` repeats the verification, then asks you to type `I-ACKNOWLEDGE`, then checks the environment, runs the synthetic self-test and opens the GUI once. **The launcher cannot verify any employer or managed-device approval.** Typing the acknowledgement is only your own statement; it does not create an approval. Use `--run-gui` only on a Mac that is not employer-managed and only if the person who sent you this package has asked you to. Never use it on an employer-managed Mac unless both of these exist in writing: (1) the employer's approval and (2) a Security decision for that exact machine and these exact bytes.

It refuses unexpected `PYTHON*`, `DYLD_*`, `TCL_LIBRARY`, `TK_LIBRARY` and `TCLLIBPATH` variables; it checks that the macOS admin group has its standard ID (80); it requires macOS on Apple Silicon (a native Terminal, not Rosetta) and the Homebrew Python 3.13 at its standard path; and it re-verifies the package hash, its ten-file inventory, its embedded manifest digest and its README before extracting it to a new folder, then re-checks the entry point's hash after extraction. It never overwrites an earlier test's files, installs nothing, changes no settings or permissions, uses no sudo and cleans nothing up automatically. On any refusal, stop and send the printed lines and the exit code; do not retry with relaxed flags.

## Results

Once the extraction folder has been created, the launcher writes `~/aq-viewer-r3e-summary.txt` on success or failure: a sanitised summary with fixed-form result lines only and home paths replaced. Send that file, not the raw logs. Refusals before that point (package checks, environment, admin group, interpreter) are shown on screen only: copy the printed lines.

## Notes

This folder contains product source code inside the ZIP. Whether it may be published depends on the code owner's and the employer's decision. This README does not record or imply that permission. It is not a release, a licence or a support commitment. This preview lives only on branch `feature/native-local-gateway-v04-20261019` and must not be merged into `main`.
