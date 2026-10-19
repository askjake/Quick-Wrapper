# AQ-MCP Connector Wizard v0.4 — Native localhost (no admin, no WSL2)

## New in this engineering candidate

- Adds **Native gateway on THIS computer** on Step 1. Unlike the original Linux SSH gateway path, this launches MCP directly from a user-owned Python virtual environment. It does not install or start an inbound SSH server or network listener.
- Native gateway files are installed at `~/AQ-MCP-Gateway` on the current host, with their own Python venv, registry, SigV4 proxy and health checker; **create-only**. A missing gateway can be installed only with explicit approval to download pinned Python packages.
- Native-local Lambda targets follow the existing exact-tool allow-list, backend metadata handshake, generated deployment plan, registry SHA conflict checks, backup receipt, health-check and rollback flow.
- Step 5 prints a **direct Python** Quick Local connector command rather than `ssh` for native localhost. There are 3 argument chips: `aq_registry.py`, `run`, and the selected target. Environment variables are EMPTY.
- Existing **Linux SSH** gateway workflows and localhost-to-Linux-over-SSH remain available and unchanged.
- CLI adds `--native-local` for user-owned native gateway bootstrap and rollback; manifests must include `"transport": "native-local"`, `"host": "127.0.0.1"`, `"user": "local"` for native mode.

## Critical limitations

- **Windows is the intended v0.4 native-local target**, but it still needs **live Windows acceptance** with user-level package index and IAM credentials. Linux CI/synthetic stdio tests are not a substitute. Python 3.10+ with tkinter and a writable user profile is needed.
- **Remote Windows-over-SSH** is **not enabled** by this candidate; another Windows PC must already have an authorized SSH daemon provisioned by its administrator. No privilege escalation, firewall openings or unreviewed remote listener is attempted.
- A Windows-native user-owned gateway is not an OS security sandbox. Files inherit Windows ACLs; review organizational endpoint policy. No secrets are stored in the wizard's registry or Quick connector fields.
- Fresh installation does **not** supply AWS/Okta credentials, corporate CA roots, Git Docker servers, PATs or server-side tools. Lambda connectivity requires the user's existing AWS credential chain on the native gateway host.
- No tool calls occur during metadata verification; only `initialize` and `tools/list`. An explicit nonempty allow-list is mandatory for new Lambda targets.
- No native Windows Git or local-server provisioning; existing Git/local adapter selection remains Linux SSH only.
- **Automatic Amazon Quick registration remains unsupported**; Step 5 guides manual Local connector registration, followed by a new Quick chat and harmless read.
- The Python dependencies are pinned by version but **not wheel-hash locked**. Production deployment needs approved package sources and package integrity review.

## Rollout gate

First validate `native-local` on an isolated Windows workstation using a disposable Lambda MCP target and the user's own IAM credentials, with no repo writes and no access to unrelated installed gateway files. Record `BACKEND_VERIFIED`, the approved tool-list fingerprint, `GATEWAY_VERIFIED`, a saved receipt and one successful read through Quick. Confirm rollback of the exact deployment hash in a separate synthetic test target.
