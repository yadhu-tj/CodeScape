# CodeScape

Spatial codebase intelligence and resilience testing for Python repositories.

Phase 0 provides a verified synthetic Python showcase, reviewed contract fixtures,
and an isolated Docker test environment. The ingestion, search, graph visualization,
triage and patch engines remain planned.

The showcase contains 18 Python files and 54 functions/methods, including four
passing baseline tests. Its signature verifier deliberately mishandles malformed
signatures so later engines have a known defect to discover. Do not deploy the
synthetic service or silently fix that seeded defect.

## Verify the foundation

These checks inspect source and orchestration without executing target code:

```bash
python backend/utils/validate_harness.py
python -m unittest discover -s backend/tests -v
```

With a running Linux-container Docker engine, build the reviewed image and execute
the target tests only inside hardened containers:

```bash
python backend/utils/build_sandbox.py
```

The helper requires four clean baseline passes, an integration smoke check, and
two fresh contract runs with three expected seeded failures and four passing
controls each. An expected contract failure is distinct from a failed baseline.
Machine-specific evidence is stored under ignored `data/evidence/`.

On the verified Windows/Ubuntu WSL setup, use the exact invocation in the
[Phase 0 verification report](backend/test_harness/PHASE0_VERIFICATION.md).

## Documentation

| Document | Purpose |
|---|---|
| [Project context](PROJECT_CONTEXT.md) | Authoritative technical contracts |
| [Implementation plan](implementation_plan%20%281%29.md) | Phases, dependencies and integration gate |
| [Task tracker](task_tracker.md) | Task status and acceptance evidence |
| [Detailed design README](README%20%283%29.md) | Full planned architecture and setup |
| [Concept and architecture](CodeScape%20Spatial%20Codebase%20Intelligence%20%26%20Resilience%20Platform%20Final%281%29.md) | Project rationale and evaluation |
| [Harness guide](backend/test_harness/README.md) | Fixture layout and execution boundaries |

## Development workflow

Use short-lived feature/fix branches and pull requests into `main`. Keep related
changes in descriptive commits and preserve those commits when merging the PR.
CI checks host tools on Windows and Linux and runs the Docker baseline/contract.
See [CONTRIBUTING.md](CONTRIBUTING.md) for commit messages, useful code comments,
review requirements and revert-based rollback. Annotated milestone tags are made
after reviewed changes are merged and verified on `main`.
