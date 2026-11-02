# AQ-MCP Windows team evaluation — frozen B4g

This directory contains a Windows-only **engineering evaluation** of the frozen B4g source. It is not a production-certified release.

- Frozen source archive SHA-256: `e8413e60d535e6961947627fa44b25121df474000fc9d57f2f5113e612b27935`
- Frozen 67-file tree SHA-256: `bbce64f8deda1ea078a8715d6813476a333110284afcdefb5c3db1f47a4620d0`
- B4G_FROZEN_TREE.zip SHA-256: `d0ece5261244f23b886e0cb1cc446e6911734cd702aeb152bfde8e510e675a29`
- Embedded B4G_FROZEN_TREE_MANIFEST.json SHA-256: `dec25425872676b0eba42b3600dfb7070a7881305749575b24e0ad899ab49d35`

The frozen files are packaged into one **binary ZIP**. This avoids `.gitattributes` line-ending normalization that otherwise changes source hashes on Git checkout. The original v0.4 feature branch and its Mac-preview artifacts are preserved; no tracked files in the parent are deleted or overwritten.

## Status

Windows CPython 3.13.15 targeted test-only overlay: **46/46 PASS**, with zero skips or blocks. The **historical full Windows suite is NOT OK**, five subprocess cases remain blocked, and the real Tk typed-authorization event loop is not yet accepted. No live connector registration, SSH gateway change, or Amazon Quick operation is included in this installer.

## Teammate prerequisites

Windows x64, organization-approved CPython 3.13 x64 including `tkinter`, Git, and access to a permitted Python package index. The install command creates a new user-owned `Quick-Wrapper-B4g` checkout and local `.venv`, installs `requirements.txt`, verifies all 67 source hashes, and launches `wizard.py`. The requirement file is not a hash-locked wheel mirror; package index policy must be reviewed separately.

## Installation

1. Obtain the **exact 40-character Git release commit SHA** and the installer SHA-256 through a separate trusted channel.
2. Download `install_windows_b4g.ps1` from that commit and verify its SHA-256 before executing. Respect managed PowerShell execution policy.
3. Run `install_windows_b4g.ps1 -ExpectedCommit <commit>`.
4. The installer refuses an existing destination; it never overwrites a coworker's checkout.

This does not configure Amazon Quick, provision credentials, or contact a gateway; those need explicit separate operator approval.

This is a public source disclosure if published to `askjake/Quick-Wrapper`. Do not push until that disclosure is approved.
