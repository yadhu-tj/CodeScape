# CodeScape — Spatial Codebase Intelligence & Resilience Platform

CodeScape is a local-first project for exploring Python repositories, understanding dependencies, and investigating potential defects. Its planned 3D workspace brings static code analysis, search, impact tracing, isolated testing, and human-reviewed patch proposals together.

As codebases grow, routes, services, and callbacks make it difficult to understand who depends on a function. CodeScape aims to help developers explore those relationships, trace potential impact, and examine test evidence before reviewing a fix. Static analysis supplies the structural graph, while AI assists with explanations and draft patches.

## Development status

| Capability | Status |
|---|---|
| Showcase repository, reviewed contract, and sandbox image | Implemented and verified |
| Async PostgreSQL schema, FastAPI health endpoint, and persistent event broker | Implemented |
| Gemini provider and 768-dimensional embeddings | In progress. Live reasoning, summary, and embedding checks passed with the locally configured models. Test generation remains pending. |
| Python repository ingestion, graph API, and local symbol search | Implemented |
| Hybrid graph search, blast-radius analysis, triage, and patch verification | Planned |
| 3D explorer, UI telemetry, and offline demo playback | Planned |

The [task tracker](task_tracker.md) records acceptance evidence and outstanding work.

## Capabilities

The five engines describe the intended v1 design. The development status table tracks implementation.


### 1. Engine 1: Two-Pass Ingestion & Static Modeling
- Filters out virtual environments, caches, and secret files before parsing `.py` files with `tree-sitter-python`.
- **Pass 1 (Definitions):** Extracts files, classes, functions and HTTP route decorators (`@app.post`, `@router.get`). It computes a deterministic CodeScape McCabe-style score: start at `M = 1`; add one for each `if`, `elif`, `for`, `async for`, `while`, `except` handler, each additional Boolean operand (`and`/`or`), each conditional expression and each comprehension filter. Count `elif` once; explicitly test the parser rules. `match`/`case` remains excluded until separately specified and tested.
- **Pass 2 (References):** Re-walks syntax trees against Pass 1's symbol table to bulk-insert `confirmed`, `probable`, and `unresolved` call edges.
- Scales 3D node sphere radius with the cube root of complexity ($R \propto \sqrt[3]{M}$) using shared geometry (`SphereGeometry(1, 16, 16)`) to save geometry allocation and buffer memory. Separate meshes still generally incur separate draw calls; instancing/batching is a measured optimization if needed. Actual frame rate depends on graph size and hardware and must be benchmarked; 60 FPS is a target, not a guarantee.

### 2. Engine 2: Hybrid Graph-RAG & 3D Camera Flight
- **Stage 1 (Semantic Anchor):** In live mode, embeds a natural-language query using the configured embedding provider and searches repository vectors with `pgvector` HNSW cosine similarity. The configured vector dimension and provider output dimension must be verified during setup and validated at runtime.
- **Stage 2 (1-Hop Expansion):** Deterministically joins direct incoming callers and outgoing callees from the `edges` table.
- **Stage 3 (Synthesis):** Generates a grounded architectural explanation using the configured summary model when available; otherwise returns the deterministic graph context without an AI summary.
- **Stage 4 (Camera Flight):** Glides the 3D camera to a standoff position $P_{\text{camera}} = N + \vec{u} \times D$ with a degenerate-case guard ($\|C - N\| < 10^{-4} \implies \vec{u} = (0, 0, 1)$) so repeated searches never inject `NaN` coordinates into Three.js.

### 3. Engine 3: Deterministic Blast-Radius Traversal
- Executes a cycle-safe PostgreSQL `WITH RECURSIVE` CTE walking backward from callee to caller using a `visited_path INTEGER[]` guard to prevent infinite loops on circular imports or mutual recursion.
- Highlights impacted callers by hop depth, identifies explicitly detected route/framework entrypoints, and reports unresolved call sites touching the subgraph. Nodes with no known callers are labelled inferred roots, not automatically confirmed public entrypoints.

### 4. Engine 4: Isolated Containerized Chaos Sandbox
- Runs generated `pytest` suites inside an ephemeral Docker container (`codescape-sandbox:latest`) using a dual-volume mount:
  - Host repository mounted **Read-Only** at `/workspace/repo:ro` (`PYTHONDONTWRITEBYTECODE=1`).
  - Disposable run workspace mounted **Read-Write** at `/workspace/test_run:rw`.
- Uses defence-in-depth controls: `--network none`, resource limits, non-root user `1000:1000`, dropped capabilities, `no-new-privileges`, read-only repository mount and host watchdog. The implementation should additionally apply a read-only root filesystem, bounded writable tmpfs, file/disk limits and seccomp/AppArmor where supported. When using `user=1000:1000`, mount `/tmp` with `uid=1000,gid=1000,mode=1777` (for example `rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=1777`) so Python temporary files and pytest cache are writable. Docker is not an absolute security boundary.
- Provides narrow fakes for required external interfaces and captures collection plus setup/call/teardown reports in structured JSON. The reporting module `codescape_pytest_reporter.py` is placed in `/workspace/test_run` and loaded globally with `-p codescape_pytest_reporter`; set `PYTHONPATH=/workspace/repo:/workspace/test_run` and run `python -m pytest -p codescape_pytest_reporter -o cache_dir=/tmp/.pytest_cache /workspace/test_run/test_chaos.py /workspace/repo/tests/`. This makes both test locations contribute to the same `/workspace/test_run/report.json` and keeps pytest cache writes off the read-only repository mount. It does not rely on blanket generic module mocks; network isolation remains the primary egress control.

### 5. Engine 5: 3-Tier Triage & Closed-Loop Patch Verification
- **Tier 1:** Pre-execution `ast.parse()` check discards syntactically broken tests as `INVALID_GENERATION` without starting Docker.
- **Tier 2:** Flags collection, import and fixture setup errors as `SETUP_FAILURE`.
- **Tier 3:** Uses normalized traceback frames to identify candidate source locations. A repository frame is not proof of a defect. `CONFIRMED_DEFECT` additionally requires a valid test, compatible invocation, in-contract input based on documented behaviour, reproducibility and exclusion of setup/mock/environment causes. Uncertain cases remain `LOW_CONFIDENCE_DEFECT` or `BEHAVIORAL_ANOMALY`.
- **Closed-Loop Verification:** Drafts a complete replacement function block, validates its target name/signature/decorators/sync-or-async form and the complete patched module, then computes a deterministic unified diff. A fresh container tests the candidate against the chaos test and selected regression suite without modifying host files. Passing those tests is not a universal correctness guarantee; human review remains required.

---

## Architecture

| Layer | Technology and role |
|---|---|
| Backend | Python, FastAPI, async SQLAlchemy, and Alembic |
| Storage | PostgreSQL 16 with pgvector, graph tables, and durable run events |
| AI provider | Configurable Google GenAI models for embeddings, summaries, and patch drafts |
| Event delivery | Redis pub/sub or single-process in-memory wakeups, backed by PostgreSQL replay |
| Static analysis | Tree-sitter Python for repository ingestion |
| Sandbox | Docker and pytest for the showcase, with the general testing engine planned |
| Frontend | React, TypeScript, Three.js, and Monaco, planned |

The database baseline defines `repos`, `nodes`, `edges`, `chaos_runs`, `patches`, and `run_events`. Node embeddings use `vector(768)` with an HNSW cosine index. Run events have per-run sequence numbers for ordered replay.

## Showcase and evaluation

The `payflow-core` showcase contains 18 Python files and 54 functions and methods, including four passing baseline tests. A dynamic dispatcher and bounded call cycle provide material for evaluating the planned graph engines. Its signature verifier deliberately mishandles malformed signatures, and a reviewed contract fixture provides the expected behavior. Keep the seeded defect in place for evaluation.

The initial target is single-user analysis of Python repositories. Hosted embedding and AI calls send redacted excerpts to the configured provider. Embedding all included symbols can cumulatively disclose substantial source content.

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

## Start the backend API

Create a local PostgreSQL 16 database and configure `backend/.env` from
[`backend/.env.example`](backend/.env.example). Install the server-side pgvector
extension package. If the application role cannot install extensions, have the
database administrator run `CREATE EXTENSION IF NOT EXISTS vector;` in the
CodeScape database before migrating.

From the repository root, with the project's Python virtual environment active:

```bash
python -m pip install -r backend/requirements.txt
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini check
python -m uvicorn backend.main:app --port 8000
```

Check `GET /api/v1/health`. Start with `python backend/main.py --demo` to verify
the demo flag. Demo data and playback are scheduled for Phase 7.

An unset or unavailable Redis uses local wakeups for single-process development.
PostgreSQL holds the replay history. Run `python -m backend.utils.smoke_test_genai`
after configuring `GEMINI_API_KEY` and the model IDs in the ignored `.env`.

Gemini requests use one short, randomized retry for HTTP 503. If you choose a
different reasoning model, you can set
`GEMINI_REASONING_FALLBACK_MODEL=gemini-3.5-flash-lite` to allow one fallback for
patch drafting. All draft attempts share a 30-second deadline. The application
logs the model that produced a valid draft at INFO level. Embedding retries use
the configured embedding model.

## Ingest and inspect a repository

Send an empty JSON object to ingest the bundled showcase. Use the returned
repository ID to retrieve its graph or search stored symbols.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/repos -H "Content-Type: application/json" -d '{}'
curl http://127.0.0.1:8000/api/v1/repos
curl http://127.0.0.1:8000/api/v1/repos/1/graph
curl -X POST http://127.0.0.1:8000/api/v1/repos/1/search -H "Content-Type: application/json" -d '{"query":"verify_signature"}'
```

Set `source` to a directory inside `REPOS_IMPORT_ROOT` or a credential-free HTTPS
Git URL on a host listed in `REPOS_GIT_HOSTS`. The defaults are the CodeScape
checkout and `github.com`. Snapshots are stored under `REPOS_STORAGE_PATH`.
Ingestion skips common generated directories and secret file patterns, rejects
included links and submodules, and limits snapshots to 2,000 files and 32 MiB.
Syntax errors in included Python files produce a diagnostic for the affected file.

For a `src/` layout, send `{"source":"my-project","import_root":"src"}`. The
static import root defaults to `.` and is relative to the repository. It
controls how Python files are named for import resolution, so
`src/pkg/auth.py` is importable as `pkg.auth`. The graph still includes other
Python files and keeps repository-relative file paths.

The graph includes symbol spans and confidence-tagged calls, imports, and
inheritance. Unresolved calls retain their source expression and line.
The search endpoint reports `lexical_fallback` and searches symbol names,
signatures, docstrings, and route paths locally.

To enable hosted enrichment for an import, send `"embed": true`. This sends
redacted function and class excerpts to the configured Gemini service. The
structural graph remains available when enrichment is disabled, unavailable, or
fails. Demo mode keeps enrichment disabled.

To run the PostgreSQL API tests, set `CODESCAPE_PHASE2_TEST_DATABASE_URL` to a
disposable database migrated to `head` and run
`python -m unittest backend.tests.test_phase2_ingestion -v`.

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
