# Phase 0 showcase and reviewed contract

`payflow-core/` is synthetic evaluation material, not a real payment service. Its
signature verifier deliberately violates its documented malformed-input contract.
Do not deploy it or silently fix that defect. The public fixture HMAC key is not
a credential. All behavior is local/in-memory; no external services are needed.

The source inventory is exactly **18 Python files and 54 explicit functions or
methods, including four baseline test functions**. Namespace packages are used
without `__init__.py`; set the repository root on `PYTHONPATH`. The oracle and
ground truth live outside the target snapshot and are excluded from these counts.

Host-safe structural check (does not import/execute the target or oracle):

```powershell
python backend/utils/validate_harness.py
```

Build and run the baseline **inside Docker** from the project root:

```powershell
python backend/utils/build_sandbox.py
```

This builds only the reviewed `backend/Dockerfile.sandbox` with the reviewed
dependency list, then runs the four tests with network disabled, non-root user,
read-only repository/root, bounded tmpfs, capability/process/resource limits and
a host deadline. It checks the JUnit test identities, no skips/errors and source
immutability; evidence goes to `data/evidence/phase0-baseline.json`. Run from WSL
using the Linux checkout path if Docker is available there. The host CLI and Docker
daemon must agree on bind paths. Docker Desktop must use Linux containers.

The build requires network access; test execution does not. Top-level package
versions are pinned; transitive wheels and the base tag are not fully locked.
Record the resolved image ID/digests and manifest hash in evidence. The 30-second
smoke deadline accommodates cold startup; the later live chaos watchdog remains
8 seconds. The Phase 4 global JSON reporter and triage engine are not implemented.

`contracts/verify_signature.v1.json` binds the reviewed contract to the exact
source snapshot and oracle SHA256. `test_verify_signature_contract.py` provides
the valid-input predicate, three known malformed inputs and passing negative
controls. Its malformed-input cases are expected to fail on the seeded source.
Never place them in `payflow-core/tests/`, run them on the host, or count this
intentional failure as a failed clean baseline. Later sandbox runs copy the oracle
to the disposable run directory and retain contract/version, input, baseline and
two-reproduction evidence before confirming a defect.

`ground_truth.json` records the complete symbol inventory and selected reviewed
call sites, routes, cycle, unresolved dispatcher and two-hop impact expectations.
Selected calls are a fixture subset, not exhaustive call-edge precision/recall
ground truth. Phase 2 must test real Tree-sitter resolution against this evidence;
the static validator is not the implementation of that engine.

Review any fixture changes before updating snapshot hashes. This project does not
automatically rebind contracts to changed source. Runtime results must be measured;
source parsing alone does not establish four passing tests or a confirmed defect.

The build helper also runs the reviewed oracle in two fresh hardened containers:
exactly three expected seeded exception failures and four passing controls per
run are required. This intentional red suite is stored separately from the clean
baseline; it does not mark the future Phase 4 triage engine implemented.

On this machine the verified engine is in Ubuntu-24.04 WSL. See
[PHASE0_VERIFICATION.md](PHASE0_VERIFICATION.md) for the measured image/source
identities, results and exact Windows-to-WSL invocation. The helper also performs
a sandbox-only HTTP/dispatcher/cycle smoke check outside the four-test baseline.

## Phase 2 CLI fixture

`report-cli/` is a small standard-library command-line project that summarizes
labels and prints text or JSON. Its [reviewed call expectations](report_cli_ground_truth.json)
were recorded before running ingestion. The checks cover the module entry
call, local functions, relative imports, two same-named functions reached
through different bindings, and a runtime formatter lookup.

With the backend running and the default repository import directory, send
`{"source":"backend/test_harness/report-cli"}` to `POST /api/v1/repos` and retrieve
`GET /api/v1/repos/{id}/graph`.

The first check on PostgreSQL 16 with pgvector matched all seven selected
call sites. Six had the expected confirmed target, and the runtime formatter
call had no target and was marked unresolved. The graph contained six files,
eight functions and zero HTTP routes. The check covers the selected sites.
