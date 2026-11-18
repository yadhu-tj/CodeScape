# Phase 0 verification — 2026-11-18

Phase 0 tasks **0.1–0.11 are complete**. This report covers the showcase, contract
and image preparation; it does not claim the later CodeScape engines exist.

| Check | Observed result |
|---|---|
| Source inventory | 18 Python files, 54 explicit functions/methods including four baseline tests |
| Route inventory | 11 application routes |
| Host-safe tooling tests | 6 passed; no target/oracle imports on host |
| Container baseline | 4 passed, 0 failed/errors/skips |
| Container integration smoke | Signed webhook chain, quote, user profile, refund, dispatcher and bounded cycle pass |
| Contract reproduction 1 | 3 intended seeded failures, 4 controls pass |
| Contract reproduction 2 | Same 3 intended failures, 4 controls pass in a new container |
| Runtime controls checked | UID/GID 1000, repo/root read-only, temporary files writable |
| Repository source after execution | Hash unchanged |

The empty signature raises `IndexError`; `v1=not-hex` and `v1=0` raise `ValueError`
at `services/auth.py:32`. These are deliberate fixture defects. The failing oracle
is kept outside the clean baseline suite. No patch has been applied.

- Host: Windows with Ubuntu-24.04 WSL and Docker Engine 29.1.3.
- Container Python: Python 3.11.18; pytest 8.3.5.
- Image: `sha256:100fb74231d50e7858b705878207a02c0fac8c4024e21ac16ae8549fbff00468`.
- Source SHA256: `df9107c7da06cd0ef06573ec578ff69a13c1a72983b6aa7726795996aa8fc93e`.
- Dependency manifest SHA256: `6485a42e22706d8df62b193aa9e6c21db13a3af055b46540ef7618c49a8c523a`.
- Oracle SHA256: `95746f3033e3771371a4b3b72e16fe2ad8c3be95ec76d495ef7a4213b98a3dbd`.
- Contract: `payflow.verify_signature.v1`, version 1.
- Full local machine-generated evidence and JUnit XML: `data/evidence/phase0-baseline.json`.

The recorded commands use network-disabled, capability-dropped, non-root containers,
read-only root/repository, PID/CPU/memory/file limits and bounded tmpfs. This is not
the full adversarial-isolation verification planned in Phase 4. WSL reports no swap
limit support; no swap-isolation guarantee is made. The image's top-level packages
are pinned; transitive dependencies and the base tag are not fully locked.

Reproduce from Windows PowerShell (Docker runs inside WSL, not Windows PATH):

```powershell
wsl -d Ubuntu-24.04 --user root -- python3 /mnt/d/CodeScape/backend/utils/build_sandbox.py --skip-build
python backend/utils/validate_harness.py
python -m unittest discover -s backend/tests -v
```

Remove `--skip-build` to rebuild the reviewed image. This WSL distribution does not
use systemd. If the daemon is not running, keep the following command in a separate
terminal, then execute the verification command above:

```powershell
wsl -d Ubuntu-24.04 --user root -- dockerd --host=unix:///var/run/docker.sock
```

The daemon is privileged infrastructure; actual target tests run as UID 1000 inside
the sandbox. No Docker socket is mounted into those containers. At the original verification, Git was not initialized and no commit was created.
Repository history is now imported in focused commits on a feature branch, with
PR/CI/revert conventions in `CONTRIBUTING.md`. PostgreSQL/provider setup and the
full backend/frontend skeleton remain separate pre-coding/later-phase work.
