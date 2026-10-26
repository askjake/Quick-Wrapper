#!/usr/bin/env bash
# Synthetic-only AQ MCP Wizard macOS Tk preview R3E. Does not install software.
# Default (no argument) and --verify-only: verification only; nothing from the ZIP
# is executed. --run-gui: repeats the verification, then asks for an explicit
# acknowledgement, then runs the self-test and ONE GUI launch. This script CANNOT
# verify any employer or managed-device approval; the acknowledgement is only the
# operator's own statement.
set -Eeuo pipefail
umask 077
export LC_ALL=C

readonly DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly ZIP="$DIR/preview-p1-mac-viewer-only-r3e.zip"
readonly SIDE="$DIR/preview-p1-mac-viewer-only-r3e.manifest.sha256"
readonly EXPECTED_ZIP_SHA256="a386352b68f02f927aea8701b233d20985bc0e1514b0594ed4b837ee82ed7c17"
readonly EXPECTED_MANIFEST_SHA256="11cc80e9c89c21f63a6d38a9273cbfd611b43c1b5c6a11eabc6bb98230d3f857"
readonly EXPECTED_ENTRY_SHA256="5e6551cdc312796df007e0fa99a5040fb3c063add4396cb480479072176dce27"
readonly EXPECTED_README_SHA256="8752ec55f8c1f2307d58d827883ce7c067a131b1b6f4c806e63e2d914bbf4483"
readonly PYTHON="/opt/homebrew/bin/python3.13"
readonly OUT="$HOME/aq-viewer-preview-r3e"
readonly SELFLOG="$HOME/aq-viewer-r3e-selftest.txt"
readonly GUILOG="$HOME/aq-viewer-r3e-output.txt"
readonly SUMMARY="$HOME/aq-viewer-r3e-summary.txt"

die() { printf 'STOP: %s\n' "$*" >&2; exit 1; }

usage='Usage: bash run_r3e.sh [--verify-only | --run-gui]'
mode=verify
case $# in
  0) ;;
  1)
    case "$1" in
      --verify-only) mode=verify ;;
      --run-gui) mode=run ;;
      *) die "Unknown argument. $usage" ;;
    esac
    ;;
  *) die "Too many arguments. $usage" ;;
esac

[[ "$(uname -s)" == Darwin ]] || die 'macOS only'
[[ "$(uname -m)" == arm64 ]] || die 'This package was prepared for the reported Apple Silicon Mac; report architecture mismatch'
[[ -f "$ZIP" && -f "$SIDE" ]] || die 'R3E ZIP and side manifest must be in the same directory as this script'

# Part A: All checks below use system tools. Nothing from the ZIP is executed.
cd "$DIR"
printf 'Checking ZIP size, hash, side manifest, archive integrity and inventory...\n'
[[ "$(stat -f %z "$ZIP")" == 459418 ]] || die 'Unexpected ZIP size'
printf '%s  %s\n' "$EXPECTED_ZIP_SHA256" "$(basename "$ZIP")" | shasum -a 256 -c - || die 'ZIP hash mismatch'
shasum -a 256 -c "$(basename "$SIDE")" || die 'Side manifest mismatch'
unzip -tqq "$ZIP" || die 'Archive integrity failure'
expected_inventory=$(printf '%s\n' PREVIEW_MANIFEST.sha256 README_VIEWER_ONLY_MAC.md bootstrap_lib.py deploy_lib.py model.py native_gateway.py preview_viewer.py quick_reg.py view_preview_mac.py wizard.py | sort)
actual_inventory=$(unzip -Z -1 "$ZIP" | sort)
[[ "$actual_inventory" == "$expected_inventory" ]] || die 'Unexpected package member inventory'
embedded_manifest_sha256="$(unzip -p "$ZIP" PREVIEW_MANIFEST.sha256 | shasum -a 256 | awk '{print $1}')"
[[ "$embedded_manifest_sha256" == "$EXPECTED_MANIFEST_SHA256" ]] || die 'Embedded manifest digest mismatch'
readme_sha256="$(unzip -p "$ZIP" README_VIEWER_ONLY_MAC.md | shasum -a 256 | awk '{print $1}')"
[[ "$readme_sha256" == "$EXPECTED_README_SHA256" ]] || die 'README mismatch'
printf 'Package PASS - 10 members, ZIP SHA-256 %s\n' "$EXPECTED_ZIP_SHA256"

if [[ "$mode" == verify ]]; then
  printf 'Verification complete. No package code was executed and nothing was written.\n'
  printf 'Running the GUI is a separate, deliberate step (--run-gui) that needs the written approvals described in the README. This script cannot check them.\n'
  exit 0
fi

printf '\n--run-gui will run unsigned Python (the packaged preview) on this Mac.\n'
printf 'THIS SCRIPT CANNOT VERIFY ANY APPROVAL. Your answer below is only your own statement.\n'
printf 'On an employer-managed Mac, continue only with (1) written approval from the employer-authorized party AND (2) an exact-byte managed-machine Security decision for the SHA-256 above. Otherwise stop now.\n'
[[ -t 0 ]] || die 'Run interactively; no noninteractive execution'
read -r -p 'Type I-ACKNOWLEDGE to run the GUI test, anything else stops: ' confirmation
[[ "$confirmation" == I-ACKNOWLEDGE ]] || die 'No acknowledgement; nothing was run'

env_names="$(env | grep -E '^(PYTHON[A-Za-z0-9_]*|TCL_LIBRARY|TK_LIBRARY|TCLLIBPATH|DYLD_[A-Za-z0-9_]*)=' | cut -d= -f1 || true)"
if [[ -n "$env_names" ]]; then
  printf 'Environment variable names requiring review (no values):\n%s\n' "$env_names"
  die 'Unexpected environment variable(s); do not unset them to bypass policy'
fi
printf 'Environment check: PASS (0 matching names)\n'

gid_line="$(dscl . -read /Groups/admin PrimaryGroupID)" || die 'Cannot read admin GID'
printf '%s\n' "$gid_line"
[[ "$gid_line" == 'PrimaryGroupID: 80' ]] || die 'Admin GID differs from expected 80'

[[ -x "$PYTHON" ]] || die 'Expected Homebrew Python 3.13 missing; no installation will be attempted'
interpreter_line="$("$PYTHON" -I -B -S -c 'import sys; print(sys.version.split()[0],sys.platform,sys.implementation.name,type(sys.stdlib_module_names).__name__,len(sys.stdlib_module_names))')" || die 'Interpreter preflight failed'
printf 'Interpreter: %s\n' "$interpreter_line"
[[ "$interpreter_line" == 3.13.*' darwin cpython frozenset '* ]] || die 'Unexpected interpreter'

# Preserve existing artifacts, never overwrite an earlier test.
[[ ! -e "$OUT" && ! -L "$OUT" ]] || die 'Existing R3E extraction directory; inspect before any cleanup'
for f in "$SELFLOG" "$GUILOG" "$SUMMARY"; do
  [[ ! -e "$f" && ! -L "$f" ]] || die 'Existing R3E diagnostic output; preserve it rather than overwrite'
done
mkdir -- "$OUT"

# Sanitized, allow-listed summary. It is written on success AND on failure once
# the extraction folder has been created; earlier refusals (package checks,
# environment, admin GID, interpreter) are shown on screen only. It copies only
# fixed-form result lines and replaces the home path; it never copies a
# traceback or free text.
sanitize() { sed -e "s|$HOME|<home>|g" -e 's|/Users/[^/ ]*|/Users/<user>|g'; }
write_summary() {
  {
    printf 'AQ viewer-only R3E result summary (sanitized, allow-listed lines only)\n'
    printf 'Expected ZIP SHA-256: %s\n' "$EXPECTED_ZIP_SHA256"
    printf '%s\n' "${gid_line:-admin GID line: not read}"
    printf 'Interpreter: %s\n' "${interpreter_line:-not read}"
    printf 'SELF-TEST EXIT CODE: %s\n' "${self_rc:-not run}"
    if [[ -f "$SELFLOG" ]]; then grep -E '^(SELFTEST|REFUSED)' "$SELFLOG" | sanitize || true; fi
    printf 'GUI EXIT CODE: %s\n' "${gui_rc:-not run}"
    if [[ -f "$GUILOG" ]]; then grep -E '^(NOT A QUALIFIED RELEASE|PREVIEW_MANIFEST|tk-extension:|REFUSED)' "$GUILOG" | sanitize || true; fi
  } > "$SUMMARY" 2>/dev/null
}
trap 'write_summary || true' EXIT
unzip -q "$ZIP" -d "$OUT" || die 'Extraction failed'
cd "$OUT"
[[ "$(ls -A | wc -l | tr -d ' ')" == 10 ]] || die 'Extracted inventory count mismatch'
printf '%s  %s\n' "$EXPECTED_ENTRY_SHA256" view_preview_mac.py | shasum -a 256 -c - || die 'Entry point hash mismatch'

cd "$HOME"
printf '\nRunning self-test with Homebrew Python -I -B -S...\n'
set +e
"$PYTHON" -I -B -S "$OUT/view_preview_mac.py" --self-test > "$SELFLOG" 2>&1
self_rc=$?
set -e
printf 'SELF-TEST EXIT CODE: %s\n' "$self_rc"
grep -E '^(SELFTEST|SKIP|NOT RUN|REFUSED)' "$SELFLOG" || true
[[ "$self_rc" == 0 ]] || die 'Self-test returned nonzero; preserve the diagnostic output'
grep -q '^SELFTEST PASS' "$SELFLOG" || die 'Self-test did not print SELFTEST PASS'

printf '\nStarting one synthetic-only GUI test. Close the window using Quit if it opens.\n'
set +e
"$PYTHON" -I -B -S "$OUT/view_preview_mac.py" > "$GUILOG" 2>&1
gui_rc=$?
set -e
printf 'GUI EXIT CODE: %s\n' "$gui_rc"
grep -E '^(PREVIEW_MANIFEST|NOT A QUALIFIED RELEASE|tk-extension:|REFUSED)' "$GUILOG" || true
printf '\nObserved manifest digest should equal: %s\n' "$EXPECTED_MANIFEST_SHA256"
printf 'Please report whether the GUI window opened and both synthetic screens appeared.\n'
printf 'Send the sanitized summary %s. Keep %s and %s unsent for local review; clean up only these exact R3E files when instructed.\n' "$SUMMARY" "$SELFLOG" "$GUILOG"
[[ "$gui_rc" == 0 ]] || die 'GUI returned nonzero; do not retry with altered flags or configuration'
printf 'R3E test complete. Do not treat the preview as a qualified installation.\n'
