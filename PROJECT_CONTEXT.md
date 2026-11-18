

### Technical source of truth: `PROJECT_CONTEXT.md` (five-document set)

# CodeScape – Project Context

> **Purpose:** This document defines the architecture, technology stack, five core engines, database schema, container isolation rules, state management invariants, and implementation guardrails for **CodeScape: Spatial Codebase Intelligence & Resilience Platform**. All human and AI-assisted development must follow this exact specification. Read this fully before writing any code.

---

## What This Project Is

**CodeScape: Spatial Codebase Intelligence & Resilience Platform** is a local-first architectural intelligence, impact analysis, and automated resilience testing platform that transforms a Python repository into an interactive, force-directed **3D dependency graph** and layers five deterministic and AI-assisted engineering capabilities on top of it:

1. **Spatial Comprehension:** Files, classes, and functions are rendered as 3D bodies in a WebGL force-directed scene where node sphere volume scales with McCabe cyclomatic complexity ($R \propto \sqrt[3]{M}$) and spatial clustering reflects structural coupling.
2. **Hybrid Graph-RAG & Spatial Navigation:** Developers query the codebase in plain English; the engine anchors on the most semantically similar symbol via `pgvector` cosine similarity, deterministically expands its 1-hop structural callers and callees, synthesizes an explanation, and smoothly flies the 3D camera to a calculated standoff position in front of the target node.
3. **Deterministic Blast-Radius Tracing:** Reverse graph traversal via a cycle-safe PostgreSQL `WITH RECURSIVE` CTE traces how a failure or contract change in one function propagates upstream through multi-hop callers to public API routes and entrypoints—using static syntax facts rather than LLM guesswork.
4. **Sandboxed Chaos Testing:** Generates targeted boundary-condition and malformed-input `pytest` suites for a selected function and executes them inside an ephemeral, network-isolated (`--network none`) Docker container with a read-only repository mount, bounded writable run workspace, narrow external-interface fakes and structured pytest phase/traceback reporting.
5. **Evidence-Based Failure Triage & Closed-Loop Patch Verification:** Separates invalid generated tests, setup failures, likely repository failures, timeouts, and reproducible defects using pytest phase reports, traceback locations, input-contract checks, and repeatable evidence. A traceback frame is an attribution clue, not proof by itself. A complete replacement function is drafted, validated and converted into a deterministic `difflib.unified_diff`; the candidate is then tested in a fresh isolated container against the failing chaos test and the repository regression suite. A passing verification means the candidate passed those specified tests; it does not establish production correctness or replace human review.

---

## Core Design Principles (Non-Negotiable)

1. **Deterministic Analysis First, Generative AI Second:** Tree-sitter syntax trees and PostgreSQL graph queries build the dependency map and trace impact. The LLM is limited to natural-language summarization, chaos-test input ideation, and replacement function drafting; it does not establish graph facts or independently certify defects.
2. **Explicit Confidence Tagging Over Hidden Limits:** Because Python supports dynamic dispatch, every extracted call edge is explicitly tagged `confirmed`, `probable`, or `unresolved`. Unresolved call sites are stored with `dst_node_id = NULL` and `raw_callee_expr`, rendered as dashed lines in 3D, and counted in completeness notes on every query.
3. **Local-First, Minimal Egress:** Parsing, graph/vector storage (`PostgreSQL + pgvector`), and chaos execution (`Docker`) run locally on the host. When an external AI provider is enabled, only redacted, function-scoped excerpts (target symbol, 1-hop context, and relevant failure evidence) are sent through the abstract `AIProvider` interface. The product is local-first, not fully air-gapped by default.
4. **Evidence-Based Verification Over Speculation:** A non-zero pytest exit code or a traceback frame alone never proves a repository defect. Triage combines collection/phase information, generated-test validity, source attribution, input-contract checks, and reproducibility. Every patch candidate is verified in a fresh container without mutating the host repository. Verification is evidence that the candidate passed the configured tests, not a guarantee of correctness in every environment.

---

## Cross-Engine Correctness Contracts

These contracts resolve implementation details that must remain consistent across the architecture, implementation plan, tracker, API and UI.

### Revision and document precedence (2026-11-18)

This consistency revision preserves the five engines, technology choices, original phases, task IDs and future-work scope. It corrects conflicting instructions and adds implementation acceptance criteria; it does not mark any feature implemented. `PROJECT_CONTEXT.md` governs technical contracts, followed by `implementation_plan (1).md` and `task_tracker.md`; `README (3).md` and the concept document explain the same design. The five design files retain their existing filenames. A new root `README.md` supplies the GitHub landing page and links to `README (3).md` for the detailed design; other canonical renames in the proposed tree remain future work. Repository collaboration conventions are in `CONTRIBUTING.md`.

### Call relationships and unresolved visualization

- Caller/callee expansion, inferred-root detection and reverse blast-radius traversal use only `edges.kind = 'calls'` within the active repository. Imports and inheritance remain stored and available as separate architectural relationships; they are not call-propagation paths.
- Traverse only resolved `confirmed` or `probable` calls with a non-null destination. These are potential static impact paths, not proof that a runtime failure propagates through every caller; callers may catch exceptions or tolerate changed results.
- Keep the existing `include_unresolved: bool = False` parameter for compatibility. It controls whether the response includes the detailed `unresolved_calls` list, never whether unknown destinations can be traversed. Always return `unresolved_touch_count` and `completeness_note`. Count distinct unresolved call-edge IDs whose source is the target or any impacted node; the count is unchanged by the toggle and does not measure unknown incoming callers.
- Render each null-destination call as a short dashed stub attached to its source, ending at a deterministic local display coordinate with a tooltip for `raw_callee_expr` and call-site line. The endpoint is display geometry only: no database node, graph-library target ID, selectable symbol or traversal target is invented. Do not pass null targets to the force-graph link resolver. The visibility toggle hides these stubs without changing stored edges or completeness counts.
- Initialize traversal paths with both target and first caller IDs, reject direct self-calls as new impacted nodes, deduplicate output by minimum hop, and bound depth. Include fixtures for self-recursion, mutual recursion, diamond paths, mixed edge kinds and both toggle values.

### Supported repository and dependency contract

- Static inspection supports bounded Python source snapshots without importing or installing the target on the host. The initial live sandbox supports Python 3.11-compatible, pytest-based, Linux-compatible projects with explicit import roots, a selected non-empty baseline suite and a prepared dependency image. The showcase uses the repository root and `tests/`; a `src/` layout needs an explicit `/workspace/repo/src` import root and a fixture proving collection. Unsupported layouts may still be inspected; live execution reports the compatibility limitation rather than a code defect.
- Record compatibility and preparation evidence in `chaos_runs.report`: Python version, import roots, selected baseline test IDs/count, source content hash (also for non-git input), commit when present, dependency manifest hash, image digest, preparation result and any external-interface fakes. Recheck the source hash before patching or verification. Tags alone do not identify an immutable environment.
- The common packages in `Dockerfile.sandbox` are a showcase convenience, not a guarantee of arbitrary-repository compatibility. Use pinned, reviewed dependency manifests and an explicit preparation step. Do not automatically execute repository `setup.py`, build hooks, custom Dockerfiles, pytest plugins or installation commands on the host. Network-enabled dependency preparation runs in a separate disposable restricted builder without host credentials or Docker-socket mounts; repository-supplied build instructions require explicit review. Runtime containers remain network-disabled. Missing/incompatible dependencies are setup failures.
- Before generated-test attribution, run the selected baseline alone on the unpatched snapshot in a fresh sandbox. Preserve existing failures separately and do not attribute them to generated tests. A missing, empty, wholly skipped or failing baseline cannot support a verified patch under this v1 contract. For the showcase the baseline is exactly four passing tests.
- Resolve host paths with `pathlib` and configured storage roots. `/tmp/codescape/runs` is a Linux/WSL example; native Windows uses a configured writable temporary root and verified Docker Desktop bind paths. Keep `/workspace/repo` and `/workspace/test_run` as Linux-container paths. Verify non-root mount access, writable-storage limits and cleanup on the documented host.

Hosted embedding at initial ingestion processes all included function/class chunks and may cumulatively disclose much of the included source. Function-scoped redaction limits individual requests, not total disclosure. No repository archive or whole-repository generation prompt is required; a local embedding provider remains future work.

### Contract oracle and confirmation policy

- Automatic `CONFIRMED_DEFECT` in v1 is limited to targets with a reviewed executable contract fixture. Store fixtures outside the ingested repository under `backend/test_harness/contracts/`, keyed by repository content hash and qualified symbol. Each fixture records a contract ID/version, reviewed documentation reference, valid-input predicate, expected outcome/assertion and negative controls. Fixture code executes only in the sandbox.
- Store the fixture identity, exact inputs, invocation compatibility, assertion checks, two fresh-container reproduction results on the same source/image, passing baseline evidence and setup/fake controls in `chaos_runs.report`. Every confirmation gate must pass; an LLM assessment, type annotation or source-frame match cannot satisfy a gate independently.
- For a general repository without such a fixture, generated or docstring-derived assertions remain advisory. Use `LOW_CONFIDENCE_DEFECT` when repository behavior is implicated and `BEHAVIORAL_ANOMALY` when only an unsupported expectation fails. Preserve findings for human review; do not silently promote them or unlock automatic patch drafting. Reviewed fixture support can be added without claiming universal contract inference.
- The UI term “chaos experiment” is retained. Its v1 scope is generated boundary-condition and malformed-input testing; distributed-system fault injection, dependency latency and service outages are future work, not implemented capabilities.

### Reporting and verification evidence boundary

- `conftest.py` supplies narrow explicit fakes only. All collection and setup/call/teardown reporting hooks live once in the globally loaded `codescape_pytest_reporter.py`, including final JSON persistence; do not duplicate those hooks in `conftest.py`. Its sibling conftest does not automatically apply fixtures to repository tests: shared fakes needed by both suites must be explicitly registered through a globally loaded fixture plugin, with fixture-scope tests.
- Generated tests and repository code share the sandbox process, so their report is execution evidence, not a tamper-proof attestation. Preserve hashes of generated tests, reporter and contract fixture before/after execution, validate the report schema and expected test IDs/counts, and corroborate with host-observed container exit/timeout and logs. These checks detect inconsistencies but do not prove safety against deliberately deceptive code. Suspected tampering prevents confirmation and verification.
- A missing/malformed/partial report, OOM, daemon failure or abnormal exit without adequate evidence sets `chaos_runs.status='failed'`, leaves `classification=NULL` and records `report.infrastructure_error`; do not fabricate a ninth classification or infer `PASSED`. A host watchdog kill is `TIMEOUT`. Verification requires exit zero, valid complete phase reports, an executed passing chaos case, a non-empty passing selected baseline and no unresolved teardown/error/integrity failures. Skips alone never count as successful execution.

### Rendering and early integration contract

Shared `SphereGeometry(1, 16, 16)` saves geometry allocation and buffer memory. Scaling one existing mesh changes neither its triangle count nor its draw-call count, but separate meshes still generally produce separate draw calls. Instancing/batching is a measured optimization if needed, not a benefit automatically supplied by geometry sharing. Report graph size, draw calls, frame-time distribution and hardware/browser; evaluate navigation tasks before claiming 3D is superior to 2D.

Retain all phases and deliverables, but execute the early integration gate **IG1** before completing the broad Phase 4 work: local showcase ingestion, basic 3D source inspection, call-only blast radius, one reviewed contract case, Docker classification, patch review and fresh-container verification through the API/UI. Pull the minimum portions of Phases 3–6 forward; use a deterministic authored test/candidate initially and mark AI generation pending. This gate does not complete the later feature tasks or replace final evaluation. Semantic search, animation polish, caching and full replay follow the working core path.

### Failure classifications

Use the following canonical `chaos_runs.classification` values throughout the database, API, WebSocket events and frontend:

| Classification | Meaning |
|---|---|
| `INVALID_GENERATION` | Generated test source fails syntax validation before Docker starts. |
| `SETUP_FAILURE` | Pytest collection, import or fixture setup fails before the target behaviour is meaningfully exercised. |
| `SIGNATURE_MISMATCH` | The generated test invokes the target with an incompatible call shape or arguments. |
| `CONFIRMED_DEFECT` | Reproducible evidence shows an in-contract input triggers a defect attributable to repository code and not to the generated test or environment. |
| `LOW_CONFIDENCE_DEFECT` | A repository frame is implicated, but contract validity, causality or reproducibility is not sufficiently established. |
| `BEHAVIORAL_ANOMALY` | A generated assertion or postcondition detects unexpected behaviour, but a specific implementation defect is not yet established. |
| `TIMEOUT` | The container exceeded its configured execution deadline. |
| `PASSED` | The generated test suite completed successfully. |

Classification precedence: syntax validation first; then established pytest collection/setup failures; then timeout and pass outcomes; then failure attribution. A timeout without a complete report remains `TIMEOUT`; infrastructure faults without classifiable test evidence use failed status/null classification as specified above. Teardown errors prevent `PASSED` and verification; retain them as `SETUP_FAILURE` with teardown phase evidence unless a reviewed contract and all attribution gates establish a repository defect. The classifier must preserve the full evidence and may return an inconclusive/low-confidence result rather than forcing a `CONFIRMED_DEFECT`.

### Defect attribution and evidence

- Capture collection, setup, call and teardown outcomes. Implement pytest hooks that cover collection reports as well as `pytest_runtest_makereport`; do not assume the latter captures collection failures.
- Store traceback frames with normalized container paths, line numbers, function names and source snippets. Confirm frame ordering with tests instead of relying on an assumed list direction.
- A frame under `/workspace/repo/` identifies a candidate source location only. It does not independently establish fault.
- Before `CONFIRMED_DEFECT`, verify that the generated test is valid, its call signature is compatible, its input satisfies the declared/documented contract, the failure is reproducible, and the failure is not a setup, mock, dependency or environment artifact. Type annotations alone are not runtime contracts.
- If any of these checks is inconclusive, use `LOW_CONFIDENCE_DEFECT` or `BEHAVIORAL_ANOMALY` and require review. Preserve `blamed_node_id` as a best-effort attribution, not a proof label.

### Offline search behaviour

- Live semantic search requires a query embedding from a configured embedding provider. Stored repository vectors cannot embed a new query by themselves.
- Offline demo search must use either (a) precomputed benchmark-query/result pairs for replay, or (b) a deterministic lexical fallback over stored symbol metadata and `body_text`.
- Label replayed/cached results and lexical fallback distinctly in the API/UI. Do not describe these as fresh live semantic Graph-RAG.
- Live embedding and LLM synthesis remain optional enhancements when the provider is available. A future local provider can enable live offline semantic search.

### Entrypoint semantics

- Explicit HTTP routes and known `main`, CLI, scheduled-job or framework entrypoints are `confirmed` entrypoints when detected by supported syntax/configuration.
- A node with no known in-repository callers may be shown as an `inferred root`, but must not automatically be presented as a public entrypoint. Static analysis may miss dynamic callers.
- Blast-radius output must distinguish confirmed entrypoints from inferred roots and include unresolved-edge completeness information.

### Complexity metric definition

CodeScape uses a deterministic McCabe-style metric. For each function, start at `M = 1` and add one for each supported decision point: `if`, `elif`, `for`, `async for`, `while`, each `except` handler, each additional Boolean operand introduced by `and`/`or`, each conditional expression, and each comprehension filter. `match`/`case` handling must be specified and tested separately before being included. Count syntax-tree constructs once; do not double-count an `elif` as both a nested `if` and an `elif`. Document this as CodeScape's defined metric and do not claim exact parity with another tool unless benchmarked.

### Repository and sandbox safety

- Treat imported repositories and generated tests as untrusted input. Enforce repository size/file-count limits, reject path traversal, validate symlinks, and prevent writes outside managed storage.
- Keep the repository read-only in the sandbox and keep generated tests/reports in a disposable writable run directory.
- In addition to network isolation, use a read-only container root filesystem where practical, bounded writable `tmpfs`, seccomp/AppArmor policy, file-descriptor and disk limits, non-root execution, dropped capabilities and `no-new-privileges`.
- Docker isolation is a defence-in-depth boundary, not a claim of perfect isolation from a hostile host or Docker daemon. Do not expose the Docker socket to the sandbox container.
- Avoid blanket `sys.modules` replacement with generic `MagicMock` objects. Mock only required external interfaces with narrow, explicit fakes; network isolation remains the primary egress control.
- When the sandbox combines `read_only=True` with `user="1000:1000"`, mount `/tmp` as a bounded tmpfs explicitly owned by that user, for example Docker tmpfs options `rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=1777`. Verify the non-root process can create temporary files and pytest cache files. Do not assume a default root-owned tmpfs is writable by UID 1000.
- Load the reporting plugin globally for both the generated chaos test and repository regression tests. Place `codescape_pytest_reporter.py` in `/workspace/test_run`, expose both paths with `PYTHONPATH=/workspace/repo:/workspace/test_run`, and invoke pytest with `-p codescape_pytest_reporter -o cache_dir=/tmp/.pytest_cache /workspace/test_run/test_chaos.py /workspace/repo/tests/`. The plugin writes one combined `/workspace/test_run/report.json`; verify collection and test-phase reports from both locations are present. The reporter module must be importable before collection begins.

### Patch safety and verification semantics

- Validate the replacement as exactly one function or method matching the target symbol and compatible signature. Handle decorators, `async def`, class-method indentation, decorators and source boundaries explicitly.
- Verify the original source span and qualified symbol before splicing; reject ambiguous or stale line ranges. Parse/compile the complete patched module, not only the isolated replacement snippet.
- Apply candidate files through a separate read-only overlay in the verification container. Never modify the persistent repository checkout.
- A patch is `verified` only when the targeted chaos test and the selected regression suite pass in the fresh container. Keep the report, test list and environment metadata. Passing tests is not a proof of general correctness; human review is required before adoption.

### Operational reliability

- Add an Alembic initial baseline immediately after SQLAlchemy models are defined and before verifying PostgreSQL tables/indexes. Apply the migration to a fresh database; Alembic is the schema source of truth, not `create_all()`.
- The in-memory `asyncio.Queue` fallback is for single-process local development only. Redis pub/sub is also not a durable job queue; document job-loss/restart behaviour or add durable job state in PostgreSQL.
- Treat model IDs, SDK versions, embedding dimensions and provider quotas as configuration to verify during setup, not immutable guarantees. Keep the configured embedding dimension consistent with the database vector column and validate it at startup. During Phase 1/P2 integration setup, run a `google-genai` smoke test against the configured reasoning model (`gemini-3.8-flash`), summary model (`gemini-3.5-flash-lite`) and embedding model (`gemini-embedding-2`): verify authentication, model access, SDK compatibility and minimal generation/embedding calls. These IDs are proposed defaults and must be changed if unavailable to the account or SDK. Assert `len(vector) == 768` for every returned embedding before any insert into `nodes.embedding vector(768)`. Do not make normal application startup depend on a live provider call; startup validates configuration/schema dimension, while the explicit setup smoke test validates live access.
- Use one canonical WebSocket event envelope across `queue_service.py`, `routes/runs.py` and `frontend/src/services/ws.ts`: `{"run_id": int, "seq": int, "event": str, "ts": ISO-8601 UTC string, "payload": object}`. `seq` is strictly increasing per run; the frontend resumes with `?after_seq=<last_seen_seq>`. Persist events in PostgreSQL `run_events` so reconnect/replay works even when Redis pub/sub or the process is unavailable. Redis pub/sub and the in-memory queue are live fan-out transports, not the source of replay history.
- Treat the `payflow-core` four-test baseline and generated chaos case as separate suites. `payflow-core/tests/test_payflow.py` contains exactly the four passing baseline regression tests and must pass on the unpatched repository. The malformed-signature defect case belongs only in the generated `/workspace/test_run/test_chaos.py`; patch verification runs that chaos test plus `/workspace/repo/tests/`.
- `seed_demo.py` must be idempotent and safe to rerun after any `payflow-core` re-ingestion. Because deleting/recreating `nodes` cascades to `chaos_runs` and `patches`, the supported recovery sequence after re-ingestion is to resolve the newly created node IDs and rerun `seed_demo.py` in a transaction; use unique `seed_key` values on `chaos_runs` and `patches` with transactional upserts so repeated runs leave one current demo run and patch rather than duplicates. The demo is not considered ready until this reseed and integrity check pass.
- Support both demo startup paths. `python main.py --demo` explicitly enables demo mode; `uvicorn main:app` reads `DEMO_MODE` from the environment/settings. Build the FastAPI app through a shared `create_app(demo_mode: bool | None = None)` path so CLI and ASGI startup use the same lifespan/configuration. The CLI `--demo` flag overrides the environment setting to `True`; without the flag, the environment setting controls the mode.

---

## Technology Stack

| Layer | Technology | Role & Version Guidance |
|---|---|---|
| **Frontend Framework** | React 18 + TypeScript + Vite | HUD layout, collapsible rails, control panels |
| **3D Rendering** | Three.js + `react-force-graph-3d` | WebGL force-directed graph, shared `SphereGeometry(1, 16, 16)`, custom shaders/particles |
| **Frontend State** | Zustand | Decoupled HUD state & throttled WebSocket telemetry store |
| **Code & Diff Viewer** | Monaco Editor (`@monaco-editor/react`) | Read-only source inspection and side-by-side unified diff review |
| **Client Snapshot Cache** | Dexie.js (IndexedDB) | Caches the last loaded graph snapshot for instant reload |
| **Styling & Icons** | Tailwind CSS + Lucide React | Dark-mode high-contrast engineering HUD |
| **Backend Framework** | Python 3.11+ & FastAPI | Async REST endpoints + WebSocket live telemetry streaming |
| **ASGI Server** | Uvicorn (`uvicorn[standard]`) | High-concurrency async server |
| **Static Parsing** | Tree-sitter (`tree-sitter`, `tree-sitter-python`) | Two-pass AST symbol extraction, call resolution, McCabe complexity |
| **Database & Vector Store** | PostgreSQL 16 + `pgvector` | Relational adjacency graph (`nodes`, `edges`), `VECTOR(768)` embeddings, runs, patches and durable run events |
| **ORM & Async Driver** | SQLAlchemy 2.0 (Async) + `asyncpg` | Non-blocking DB queries, bulk inserts, and `WITH RECURSIVE` CTE execution |
| **Queue & Pub/Sub** | Redis (`redis.asyncio`) + `asyncio.Queue` Fallback | Chaos job dispatch and live container log fan-out to WebSockets (zero-daemon local fallback) |
| **Container Sandbox** | Docker Engine + Python `docker` SDK | Ephemeral, `--network none`, resource-capped `pytest` execution |
| **AI SDK (Official)** | Google GenAI SDK (`google-genai`) | Unified client behind `AIProvider` interface (DO NOT use deprecated `google-generativeai`) |
| **LLM (Reasoning/Code)** | Configurable provider model (proposed default: `gemini-3.8-flash`) | Chaos test generation and replacement function patch drafting; verify availability before use |
| **LLM (Fast Summary)** | Configurable provider model (proposed default: `gemini-3.5-flash-lite`) | Graph-RAG structural context synthesis; verify availability before use |
| **Embedding Model** | Configurable provider model (proposed default: `gemini-embedding-2`) | Code embeddings stored as `vector(768)` in v1; verify the selected model supports 768 dimensions before implementation freeze |

---

## System Architecture

```text
React + TypeScript HUD (Port 5173)
  ├── Canvas Track: Three.js / react-force-graph-3d (Direct mutable ref updates; performance target measured under a defined workload)
  ├── HUD Track:    Zustand Store + Monaco Diff Editor + Dexie.js IndexedDB Cache
         │
         │  HTTP REST (/api/v1/*) + WebSocket (/api/v1/runs/{id}/stream)
         ▼
FastAPI Async Backend (Port 8000)
  ├── Engine 1: Tree-sitter Two-Pass Ingestion & McCabe Complexity Engine
  ├── Engine 2: Hybrid Graph-RAG & 3D Camera Standoff Vector Calculator
  ├── Engine 3: Recursive CTE Blast-Radius Reverse Traversal Engine
  ├── Engine 4: Docker Chaos Sandbox Orchestrator + Injected conftest.py Generator
  ├── Engine 5: 3-Tier Traceback Classifier & difflib Closed-Loop Patch Verifier
         │
    ┌────┴─────────────────────────┬────────────────────────────┐
    ▼                              ▼                            ▼
PostgreSQL + pgvector        Docker Daemon               AIProvider Interface
(Single unified DB:          (Ephemeral Chaos Worker:    (Redacted Excerpts Only:
 nodes, edges, vectors,       --network none,             configured reasoning model (proposed default: gemini-3.8-flash),
 chaos_runs, patches)         /workspace/repo :ro,        configured summary model (proposed default: gemini-3.5-flash-lite),
                              /workspace/test_run :rw)    configured embedding model (proposed default: gemini-embedding-2) @ 768d)

```

### Architectural Separation Responsibilities

* **Single Unified Database (`PostgreSQL + pgvector`):** Unlike dual-DB setups, CodeScape stores both relational graph adjacency (`nodes`, `edges`) and 768-dimensional embeddings (`nodes.embedding`) inside PostgreSQL so semantic search and 1-hop structural joins happen in a single transactional store.
* **Dual-Track Frontend State:** Never push high-frequency WebSocket log lines into React state that wraps the 3D ForceGraph component. Visual node transitions (idle, focused, analyzing, testing, defect, verified) mutate Three.js materials/refs directly on the Canvas Track, while terminal logs and inspector data flow through a throttled Zustand store on the HUD Track.

---

## The Five Core Engines (Exact Execution Specifications)

### Engine 1: Two-Pass Ingestion & Static Modeling (`ingestion_service.py`)

Always execute repository ingestion in this exact sequence:

1. **Filter & Redact:** Walk target repository directory (`./data/repos/<repo_name>`). Skip `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `build`, `dist`, `.env*`, and files matching secret patterns (`*.pem`, `*.key`, `*credentials*`).
2. **Pass 1 — Definitions & Complexity:**
* Parse every `.py` file with Tree-sitter (`tree-sitter-python`).
* Extract `file`, `class`, and `function` symbols (`qualified_name`, `file_path`, `start_line`, `end_line`, `signature`, `docstring`, `body_text`).
* Extract route decorator metadata (e.g., `@app.post("/api/v1/stripe")`, `@router.get(...)`) so entrypoint nodes retain their exposed HTTP route path.
* Compute McCabe Cyclomatic Complexity for each function:

$$M = 1 + \text{supported decision points}$$

Use the exact CodeScape counting rules in **Complexity metric definition** above. In particular, count each additional Boolean operand, include `async for`, conditional expressions and comprehension filters, and avoid double-counting `elif`.


* Bulk-insert rows into `nodes` and construct an in-memory symbol lookup table: `dict[qualified_name, node_id]`.


3. **Pass 2 — References & Confidence-Tagged Edges:**
* Re-walk the cached syntax trees to resolve imports, inheritance, and call sites against the Pass 1 symbol map.
* Assign confidence to every call edge:
* `confirmed`: Callee resolves unambiguously to a single in-repo definition via explicit import or local scope.
* `probable`: Resolved via structural heuristic (e.g., `self.method()` within a class hierarchy or unique method name in repo).
* `unresolved`: Dynamic dispatch (`getattr`, dictionary callbacks like `EVENT_REGISTRY[evt](payload)`, unresolvable external/dynamic calls). Set `dst_node_id = NULL` and store the source expression in `raw_callee_expr`.


* Bulk-insert all edges into `edges`.


4. **Vector Embedding Generation (optional enrichment after structural persistence):**
* Persist and serve the structural graph even when the provider is unconfigured/unavailable; leave embeddings null, report enrichment status, and use labelled lexical search. Live semantic search requires successful task 2.7 enrichment. Do not roll back a valid structural graph because embedding or image preparation failed.
* For each `function` and `class` node, sanitize and redact secrets from `f"{qualified_name}\n{signature or ''}\n{docstring or ''}\n{body_text}"`.
* Generate embeddings via the canonical `AIProvider.embed_texts(texts)` batch interface using the configured embedding model and dimension; validate every returned vector length against `EMBEDDING_DIMENSIONS` before updating `nodes.embedding`.


5. **Sandbox Image Preparation:** Separately prepare the supported repository image (`codescape-sandbox:<repo_slug>`) under the reviewed dependency/builder contract above, with network available only during preparation. Record the immutable image digest and manifest hash; never install or execute target build code on the host. Runtime chaos containers require zero network access. Static ingestion can finish even when live execution preparation is unsupported.

---

### Engine 2: Hybrid Graph-RAG & Camera Flight (`graph_rag_service.py`)

1. **Stage 1 (Semantic Anchor):** In live semantic mode, embed the user's natural-language query (`output_dimensionality=EMBEDDING_DIMENSIONS`) and run a `pgvector` cosine distance (`<=>`) search over `nodes` for the active `repo_id`. In offline demo mode, use a precomputed query/result replay or deterministic lexical fallback; do not attempt a live vector query with an unembedded query.
2. **Stage 2 (1-Hop Structural Expansion):** Deterministically query `edges` for all direct incoming callers (`dst_node_id = anchor.id`) and direct outgoing callees (`src_node_id = anchor.id`) where `repo_id` matches the active repository, `kind='calls'`, the destination is non-null and confidence is `confirmed` or `probable`, plus count/list unresolved outgoing calls from the anchor.
3. **Stage 3 (Context Synthesis):** Package the anchor's `body_text`, signature, complexity score, and 1-hop caller/callee signatures into a prompt for the configured summary model via `AIProvider.summarize_graph_context()`. If the provider is unavailable or the call fails, return the deterministic graph payload with `ai_summary: null` (graceful degradation).
4. **Stage 4 (Camera Flight & Degenerate-Case Guard):**
* On the frontend, read the target node's live 3D coordinates $N = (x_n, y_n, z_n)$ and current camera position $C = (x_c, y_c, z_c)$.
* Compute norm $d = \Vert{}C - N\Vert{}$.
* **Critical Guard:** If $d < 10^{-4}$ (camera is already centered on $N$), fallback to unit vector $\vec{u} = (0, 0, 1)$ to prevent division-by-zero `NaN` injection into Three.js. Otherwise $\vec{u} = \frac{C - N}{d}$.
* Glide camera along an ease-out curve to $P_{\text{camera}} = N + \vec{u} \times D$ (where standoff distance $D = 40$).



---

### Engine 3: Deterministic Blast-Radius Traversal (`blast_radius_service.py`)

1. Execute a cycle-safe PostgreSQL `WITH RECURSIVE` query starting at `target_node_id` and walking **backward** (`edges.dst_node_id -> edges.src_node_id`):
* Maintain `visited_path INTEGER[]`, initialized as `ARRAY[target_node_id, src_node_id]`; reject a direct self-call in the base case so the target is not returned as its own impacted caller.
* Stop branch expansion whenever `e.src_node_id = ANY(visited_path)` or `depth >= max_depth` (default `max_depth = 6`).
* In both base and recursive steps, filter by active `repo_id`, `kind = 'calls'`, non-null destination and `confidence IN ('confirmed', 'probable')`. `include_unresolved=true` adds unresolved-call details to the response; it never adds traversal paths.


2. Deduplicate impacted upstream callers by minimum hop `depth`; these are potential static impact relationships, not guaranteed runtime failure propagation.
3. Identify **Impacted Entrypoints**: prioritize explicitly detected HTTP routes and supported `main`/CLI/framework entrypoints. Nodes with zero known in-repository callers may be returned separately as `inferred_roots`; do not label them confirmed public entrypoints because dynamic callers may be missing.
4. Always count distinct unresolved `kind='calls'` edges originating from the target or any impacted node as `unresolved_touch_count`, with a completeness note. Include `unresolved_calls` details only when `include_unresolved=true`; both toggle values return the same impacted nodes, depths and count. Unknown incoming callers cannot be counted from null destinations.

---

### Engine 4: Isolated Containerized Chaos Sandbox (`sandbox_service.py`)

Every chaos run and patch verification run must obey this strict container isolation contract:

1. **Persistent vs. Ephemeral Paths:**
* Cloned target repositories live persistently in `./data/repos/<repo_slug>/`.
* Each chaos execution creates a fresh disposable host directory at `/tmp/codescape/runs/<run_id>/`.


2. **Dual-Volume Mounts:**
* Mount `./data/repos/<repo_slug>` $\rightarrow$ `/workspace/repo:ro` (**READ-ONLY**).
* Mount `/tmp/codescape/runs/<run_id>` $\rightarrow$ `/workspace/test_run:rw` (**READ-WRITE**).


3. **Hardened Container Flags (baseline plus defence in depth):**
* `network_mode="none"`; do not mount the Docker socket or host credentials.
* `read_only=True` for the container root filesystem; provide only bounded writable `tmpfs` locations required by Python/pytest.
* `mem_limit="256m"`, `nano_cpus=1_000_000_000`, `pids_limit=64`, plus file-descriptor and writable-storage limits. Make limits configurable and test them against the harness.
* `user="1000:1000"`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, and an appropriate seccomp/AppArmor profile where supported.
* Environment: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=/workspace/repo:/workspace/test_run` for the showcase; append explicit supported import roots when configured. Keep secrets out of the container.
* Working directory: `/workspace/test_run`; repository mount remains read-only.
* Host-side async watchdog timer: default **8.0 seconds**, configurable and enforced by the host.
* Document that Docker provides defence in depth and is not an absolute boundary against a hostile kernel/daemon.


4. **Auto-Injected `/workspace/test_run/conftest.py`:**
* Automatically written by the backend prior to container start.
* **Job 1 (External Interface Mocking):** Provide narrow, explicit fakes/adapters for the external interfaces used by `payflow-core`. Avoid replacing entire third-party modules with unconstrained generic `MagicMock` objects, which can hide import and behaviour errors. Network isolation is still the primary egress control.
* **Companion global reporter:** Write `codescape_pytest_reporter.py` beside the generated conftest and load it using `-p codescape_pytest_reporter`. This module alone captures collection outcomes with `pytest_collectreport`, setup/call/teardown with `pytest_runtest_makereport`, and final JSON with `pytest_sessionfinish`. Record phase, outcome, exception and normalized frames; test frame ordering and the event schema. `conftest.py` contains no duplicate reporting hooks. Shared fakes for both test locations require an explicitly registered global fixture plugin.



---

### Engine 5: Evidence-Based Triage & Closed-Loop Patch Verification (`triage_service.py` & `patch_service.py`)

Never trust `pytest` exit codes directly. Classify every chaos experiment through three sequential tiers:

* **Tier 1 — Pre-Execution Syntax Check:** Parse the LLM-generated `test_chaos.py` on the host using `ast.parse()` (or Tree-sitter) before starting Docker. If a syntax error exists $\rightarrow$ mark run `INVALID_GENERATION` and discard without spinning up a container.
* **Tier 2 — Pytest Collection & Import Lifecycle:** Inspect `report.json` / container exit phase. If `pytest` fails during collection or module import $\rightarrow$ classify as `SETUP_FAILURE`.
* **Tier 3 — Failure Attribution and Evidence Assessment:**
* If killed by the configured host watchdog $\rightarrow$ classify as `TIMEOUT`; if all selected tests pass $\rightarrow$ `PASSED`.
* Classify collection/import/fixture setup failures as `SETUP_FAILURE` using collection and test-phase reports.
* Validate the generated test's syntax, target call shape and assertions. A wrong call shape attributable to the generated test is `SIGNATURE_MISMATCH`; an unsupported assertion or unexpected result without proven source causality is `BEHAVIORAL_ANOMALY`.
* Use normalized traceback frames to identify candidate repository symbols and populate `blamed_node_id`, but do not infer defect confirmation from frame location or frame order alone.
* `CONFIRMED_DEFECT` requires reproducible failure, an in-contract input based on documented preconditions/behaviour (type hints alone are insufficient), a valid test, and evidence that the failure is attributable to repository behaviour rather than setup, mocks or environment.
* If causality or contract validity is uncertain, classify as `LOW_CONFIDENCE_DEFECT` and require human review. Preserve the evidence and confidence rationale in `report`.
* Treat `pytest_runtest_makereport` frame order as an implementation detail to verify with tests; normalize frames and explicitly select the relevant application frame.





**Closed-Loop Patch Drafting & Verification:**

1. Pass the target function's `body_text`, signature, crashing input, and failing traceback line to `AIProvider.draft_function_patch()` (configured reasoning model).
2. **Never ask the LLM for unified diff hunks.** Require the LLM to return the **complete replacement Python function block** (validated via `ast.parse()`).
3. Confirm the source file still matches the stored symbol/span; validate the replacement is the intended function/method (including name, sync/async form, signature and decorators), preserve class indentation, and reject ambiguous or stale spans. Parse/compile the complete patched module before generating the diff.
4. Splice the candidate in memory and compute the unified diff deterministically with `difflib.unified_diff()`.
5. For verification (`POST /api/v1/patches/{id}/verify`), stage the patched file under a safe overlay path and mount it read-only at the corresponding repository path in a fresh container. Run the original failing chaos test and the selected existing regression suite. Keep the persistent checkout untouched.
6. Mark the patch `verified` only if both test groups pass; retain exact test results and environment metadata. Display `VERIFIED BY EXECUTION` as a bounded test result, not a guarantee of production correctness. Require human review before adopting/exporting the patch.

---

## Database Schema (PostgreSQL 16 + `pgvector`)

Enable `pgvector` before creating tables:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

```

### 1. `repos`

```sql
CREATE TABLE repos (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    source_url      VARCHAR(500),
    commit_sha      VARCHAR(64),
    local_path      VARCHAR(500) NOT NULL,
    image_tag       VARCHAR(150) NOT NULL DEFAULT 'codescape-sandbox:latest',
    status          VARCHAR(30) NOT NULL DEFAULT 'ready', -- 'ingesting', 'ready', 'failed'
    ingested_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

```

### 2. `nodes`

```sql
CREATE TABLE nodes (
    id              SERIAL PRIMARY KEY,
    repo_id         INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    kind            VARCHAR(20) NOT NULL, -- 'file', 'class', 'function'
    qualified_name  VARCHAR(350) NOT NULL,
    file_path       VARCHAR(350) NOT NULL,
    start_line      INTEGER NOT NULL,
    end_line        INTEGER NOT NULL,
    signature       TEXT,
    docstring       TEXT,
    route_path      VARCHAR(250),         -- Populated if function has @app/@router decorator
    complexity      INTEGER NOT NULL DEFAULT 1,
    body_text       TEXT NOT NULL,        -- Full source text for standalone --demo mode & Monaco
    embedding        vector(768)           -- fixed v1 dimension; provider model is configurable
);

CREATE INDEX idx_nodes_repo_id ON nodes(repo_id);
CREATE INDEX idx_nodes_qualified_name ON nodes(repo_id, qualified_name);
CREATE INDEX idx_nodes_embedding_hnsw ON nodes USING hnsw (embedding vector_cosine_ops);

```

### 3. `edges`

```sql
CREATE TABLE edges (
    id              SERIAL PRIMARY KEY,
    repo_id         INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    src_node_id     INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    dst_node_id     INTEGER REFERENCES nodes(id) ON DELETE CASCADE, -- NULLABLE for unresolved edges!
    kind            VARCHAR(20) NOT NULL, -- 'calls', 'imports', 'inherits'
    confidence      VARCHAR(20) NOT NULL, -- 'confirmed', 'probable', 'unresolved'
    call_site_line  INTEGER,
    raw_callee_expr TEXT                  -- Preserves raw expression (e.g. 'EVENT_REGISTRY[evt]') when dst_node_id IS NULL
);

CREATE INDEX idx_edges_repo_id ON edges(repo_id);
CREATE INDEX idx_edges_src_node_id ON edges(src_node_id);
CREATE INDEX idx_edges_dst_node_id ON edges(dst_node_id);

```

### 4. `chaos_runs`

```sql
CREATE TABLE chaos_runs (
    id                  SERIAL PRIMARY KEY,
    repo_id             INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    node_id             INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    blamed_node_id      INTEGER REFERENCES nodes(id) ON DELETE SET NULL, -- Actual callee if defect is downstream
    status              VARCHAR(30) NOT NULL DEFAULT 'queued', -- 'queued', 'running', 'completed', 'failed'
    classification      VARCHAR(40), -- 'CONFIRMED_DEFECT', 'LOW_CONFIDENCE_DEFECT', 'INVALID_GENERATION', 'SETUP_FAILURE', 'SIGNATURE_MISMATCH', 'BEHAVIORAL_ANOMALY', 'TIMEOUT', 'PASSED'
    test_code           TEXT,
    report              JSONB,       -- Structured frames, crashing input, stdout/stderr summary
    log_ref             TEXT,        -- Cached log stream lines for --demo playback
    seed_key            VARCHAR(150) UNIQUE, -- Stable idempotent demo-seed identity; NULL for live runs
    started_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at         TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_chaos_runs_node_id ON chaos_runs(node_id);

```

### 5. `patches`

```sql
CREATE TABLE patches (
    id                  SERIAL PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES chaos_runs(id) ON DELETE CASCADE,
    node_id             INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    replacement_code    TEXT NOT NULL,
    unified_diff        TEXT NOT NULL, -- Generated deterministically via difflib.unified_diff
    rationale           TEXT,
    status              VARCHAR(30) NOT NULL DEFAULT 'proposed', -- 'proposed', 'verifying', 'verified', 'failed'
    verification_report JSONB,         -- Results of re-running chaos test + existing regression suite
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    verified_at         TIMESTAMP WITH TIME ZONE,
    seed_key            VARCHAR(150) UNIQUE -- Stable idempotent demo-seed identity; NULL for live patches
);

```

### 6. `run_events` (Durable WebSocket Replay)

```sql
CREATE TABLE run_events (
    id          BIGSERIAL PRIMARY KEY,
    run_id      INTEGER NOT NULL REFERENCES chaos_runs(id) ON DELETE CASCADE,
    seq         BIGINT NOT NULL,
    event       VARCHAR(80) NOT NULL,
    ts          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (run_id, seq)
);

CREATE INDEX idx_run_events_run_seq ON run_events(run_id, seq);
```

`seq` is allocated monotonically per run in the same transaction as event persistence; lock the parent `chaos_runs` row while allocating the next sequence (or use an equivalent atomic per-run counter). For reconnect, subscribe to live fan-out first, buffer incoming events, replay rows after `?after_seq=<last_seen_seq>`, then merge and deduplicate by `seq` so no event is lost in the replay/live handoff. The frontend and backend must use the same envelope: `run_id`, `seq`, `event`, `ts`, and `payload`.

---

## Reference Test Harness (`payflow-core`) & `--demo` Mode

### 1. The Curated Showcase Repository (`backend/test_harness/payflow-core/`)

`payflow-core` is a required, purpose-built 18-file, ~54-function Python payment & webhook processing repository committed directly inside the project so every engine has deterministic ground truth:

* **All 3 Edge Confidence Levels:** Standard imports (`confirmed`), `self.method()` calls (`probable`), and a dictionary-based webhook dispatcher `handler = EVENT_REGISTRY[event_type]; handler(payload)` (`unresolved`).
* **Deliberate Call Cycle:** Mutual recursion / helper cycle between two utility functions to prove the PostgreSQL recursive CTE's `visited_path` guard terminates cleanly.
* **Seeded In-Contract Defect:** `verify_signature(payload: str, sig: str) -> bool` in `services/auth.py`. Its docstring/test contract must explicitly state that `payload` and `sig` are strings and malformed/empty signature strings are valid external inputs that should return `False` rather than crash. The seeded implementation performs unguarded hex slicing/decoding (`bytes.fromhex(...)`) and raises `ValueError` or `IndexError`, giving the triage engine a documented behavioural contract—not merely type hints—to test.
* **Existing Regression Suite:** `tests/test_payflow.py` contains exactly four passing baseline unit tests and must pass on the unpatched repository. Keep the malformed-signature chaos case out of this directory; generate it separately as `/workspace/test_run/test_chaos.py`. Patch verification runs the generated chaos case together with `/workspace/repo/tests/`. These four tests provide a limited regression check, not proof that all regressions are absent.

**Phase 0 implementation evidence (2026-11-18):** The showcase now contains exactly 18 Python files and 54 explicit functions/methods including four baseline tests. The image built in Ubuntu WSL; all four baseline tests and HTTP/dispatcher/bounded-cycle smoke checks pass in hardened network-disabled containers. Two fresh oracle runs each reproduce three intentional malformed-signature exceptions with four passing controls. Source hashes remain unchanged. See `backend/test_harness/PHASE0_VERIFICATION.md`; later engines and IG1 remain planned. Illustrative source-line references in future demo descriptions must be resolved from the actual source/traceback (the seeded decode currently occurs at `services/auth.py:32`).

### 2. Standalone `--demo` Mode (`DEMO_MODE=true`)

Starting the backend with `--demo` (or `DEMO_MODE=true` in `.env`) loads a precomputed `payflow-core` snapshot containing nodes, source text, edges, recorded chaos-run evidence/logs and a stored patch/diff verification report. In `--demo` mode:

* WebSocket `/api/v1/runs/{id}/stream` replays recorded container log events.
* 3D exploration, camera flight, deterministic blast-radius traversal, source inspection and recorded patch/diff review work without Docker or live LLM calls.
* Search uses curated benchmark-query replay and/or deterministic lexical fallback over stored symbol text. The API/UI identifies the mode. A new arbitrary semantic query still needs an embedding provider; stored repository vectors cannot embed the query.
* A replayed patch verification is historical evidence, not a fresh sandbox execution. PostgreSQL remains a local dependency in this design.

---

## Project Folder Structure

```text
codescape/
├── backend/
│   ├── main.py                         # FastAPI app entry, lifespan, CORS, --demo flag handler
│   ├── config.py                       # Pydantic BaseSettings loading from .env
│   ├── database.py                     # Async SQLAlchemy engine, AsyncSession, init_db
│   ├── .env                            # Secrets — NEVER commit to GitHub
│   ├── requirements.txt
│   ├── Dockerfile.sandbox              # Base Docker image for isolated pytest chaos workers
│   ├── models/
│   │   ├── __init__.py
│   │   ├── repo.py
│   │   ├── node.py
│   │   ├── edge.py
│   │   ├── chaos_run.py
│   │   ├── patch.py
│   │   └── run_event.py                 # Durable per-run event history
│   ├── schemas/                        # Pydantic v2 request/response envelopes
│   │   ├── __init__.py
│   │   ├── common.py                   # Standard {success, data, message} envelope
│   │   ├── graph.py
│   │   ├── search.py
│   │   ├── chaos.py
│   │   └── patch.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── repos.py                    # POST /repos, GET /repos/{id}/graph, POST /repos/{id}/search
│   │   ├── nodes.py                    # GET /nodes/{id}, GET /nodes/{id}/blast-radius, POST /nodes/{id}/chaos-runs
│   │   ├── runs.py                     # GET /runs/{id}, WS /runs/{id}/stream, POST /runs/{id}/patch
│   │   └── patches.py                  # POST /patches/{id}/verify, GET /patches/{id}/export
│   ├── services/
│   │   ├── ai_provider.py              # Abstract AIProvider + GeminiProvider (google-genai) + OllamaStub
│   │   ├── ingestion_service.py        # Engine 1: Tree-sitter 2-pass parser + McCabe complexity
│   │   ├── graph_rag_service.py        # Engine 2: pgvector anchor + 1-hop expansion + summary
│   │   ├── blast_radius_service.py     # Engine 3: PostgreSQL WITH RECURSIVE reverse traversal
│   │   ├── sandbox_service.py          # Engine 4: Docker SDK runner + conftest.py injector + watchdog
│   │   ├── triage_service.py           # Engine 5a: 3-tier frame classifier & node attribution
│   │   ├── patch_service.py            # Engine 5b: AST splice + difflib.unified_diff + verification run
│   │   └── queue_service.py            # Redis pub/sub with automatic in-memory asyncio.Queue fallback
│   ├── utils/
│   │   ├── redaction.py                # Secret scrubber before any excerpt leaves to AIProvider
│   │   ├── seed_demo.py                # Populates full payflow-core snapshot for --demo mode
│   │   └── build_sandbox.py            # Builds codescape-sandbox Docker image
│   └── test_harness/
│       ├── contracts/                  # Reviewed executable contracts keyed by source hash/symbol
│       └── payflow-core/               # 18-file curated showcase Python repository + tests/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Canvas/
│   │   │   │   ├── ForceGraphScene.tsx # Three.js 3D graph, shared SphereGeometry, camera flight
│   │   │   │   └── ParticleEngine.ts   # Imperative shockwave rings & backward blast particles
│   │   │   ├── HUD/
│   │   │   │   ├── TopBar.tsx          # Repo selector, Demo badge, Graph-RAG search bar
│   │   │   │   ├── LeftFileRail.tsx    # Collapsible directory/symbol tree + confidence filters
│   │   │   │   ├── RightInspector.tsx  # Symbol metadata, Monaco code viewer, Blast & Chaos triggers
│   │   │   │   ├── BottomTerminal.tsx  # Live WebSocket log stream, 3-tier triage badge, timeline
│   │   │   │   └── DiffReviewModal.tsx # Side-by-side Monaco Diff Editor, Verify & Export Patch
│   │   │   └── Common/
│   │   │       ├── ConfidenceBadge.tsx
│   │   │       └── StateIndicator.tsx
│   │   ├── store/
│   │   │   └── useHudStore.ts          # Zustand store (buffered logs, active node, visual mode)
│   │   ├── cache/
│   │   │   └── graphCache.ts           # Dexie.js IndexedDB snapshot persistence
│   │   ├── services/
│   │   │   ├── api.ts                  # Axios client (/api/v1)
│   │   │   └── ws.ts                   # WebSocket manager with throttled Zustand flush
│   │   ├── types/
│   │   │   └── codescape.ts            # Shared TypeScript interfaces
│   │   └── App.tsx
│   ├── index.html
│   ├── package.json
│   └── tsconfig.json
│
├── PROJECT_CONTEXT.md                  # This file
├── IMPLEMENTATION_PLAN.md
├── TASK_TRACKER.md
└── README.md

```

---

## API & WebSocket Conventions

* **Base REST URL:** `/api/v1`
* **Standard JSON Response Envelope (All REST endpoints):**

```json
{
  "success": true,
  "data": {},
  "message": "Human-readable status description"
}

```

* **Error Response Envelope:**

```json
{
  "success": false,
  "data": null,
  "message": "Clear diagnostic explanation of what failed"
}

```

* **WebSocket Stream (`/api/v1/runs/{id}/stream`):** Every event uses the same JSON envelope across `queue_service.py`, `routes/runs.py` and `frontend/src/services/ws.ts`:
```json
{
  "run_id": 42,
  "seq": 17,
  "event": "chaos_test_completed",
  "ts": "2026-11-12T08:30:00Z",
  "payload": {
    "classification": "CONFIRMED_DEFECT",
    "node_id": 123
  }
}
```
`seq` is strictly increasing per run. The client reconnects with `?after_seq=<last_seen_seq>`; the server subscribes/buffers live events, replays persisted `run_events` after that cursor, merges and deduplicates by sequence, then continues live delivery. Log text, visual-state changes and triage results belong inside `payload`; do not define alternate top-level event shapes.



---

## Environment Variables (`backend/.env`)

```env
# Database (PostgreSQL 16 + pgvector)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codescape

# AI Provider Configuration (google-genai SDK)
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
# Proposed defaults: verify model access and output dimension before use.
GEMINI_REASONING_MODEL=gemini-3.8-flash
GEMINI_SUMMARY_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_DIMENSIONS=768

# Optional Queue (Falls back to in-memory asyncio.Queue if unset or unreachable)
REDIS_URL=redis://localhost:6379/0

# Storage & Sandbox Paths
REPOS_STORAGE_PATH=./data/repos
EPHEMERAL_RUNS_PATH=/tmp/codescape/runs
SANDBOX_IMAGE_TAG=codescape-sandbox:latest
SANDBOX_TIMEOUT_SECONDS=8

# Runtime Mode
DEMO_MODE=false
CORS_ORIGINS=http://localhost:5173

```

---

## Edge Cases & Zero-Result Handling Matrix

| Scenario | Mandatory System Behaviour |
| --- | --- |
| Camera Flight triggered on already-focused node ($\|C - N\| < 10^{-4}$) | Fallback to unit vector $\vec{u} = (0, 0, 1)$ before multiplying by standoff distance $D$. Never divide by zero or pass `NaN` to Three.js. |
| Call site targets dynamic expression (`getattr`, dict registry) | Insert row in `edges` with `dst_node_id = NULL`, `confidence = 'unresolved'`, and `raw_callee_expr` populated. Render a source-attached dashed display stub, with no graph target or database node, and include in completeness count. |
| Circular import or mutual recursion during Blast Radius | PostgreSQL `WITH RECURSIVE` query checks ` NOT (e.src_node_id = ANY(visited_path))` and terminates branch cleanly. |
| LLM generates syntactically invalid Python chaos test | Tier 1 `ast.parse()` catches error pre-Docker; classify run as `INVALID_GENERATION`; do not start container. |
| Generated chaos test passes wrong arguments to target function | Validate the generated call against the target signature; classify as `SIGNATURE_MISMATCH` only when the test invocation is incompatible. Never infer this solely from a frame path. |
| Infinite loop inside target function during chaos run | Host watchdog kills container at 8.0s; classify run as `TIMEOUT`. |
| Gemini API quota/network failure during Graph-RAG search | If query embedding succeeded and only synthesis failed, return the vector anchor and call context with `ai_summary: null`. If embedding failed, explicitly return labelled lexical fallback (or a clear unavailable result when fallback is disabled); never claim a fresh vector anchor without a query vector. |
| Docker daemon not running during live presentation | Run backend with `DEMO_MODE=true` (`--demo`); serve the cached `payflow-core` graph, recorded logs and stored patch report from PostgreSQL. Use labelled query replay/lexical fallback; do not imply arbitrary live semantic search or fresh verification. |

---

## What NOT To Do (Strict Guardrails)

* **Do not** use the deprecated `google-generativeai` package; use the official `google-genai` SDK (`from google import genai`).
* Treat the configured Gemini model IDs as defaults pending verification against current provider documentation, SDK support, project access and quotas. Keep model IDs configurable rather than hard-coding them throughout the codebase.
* Keep `EMBEDDING_DIMENSIONS` identical to the database vector column and validate the returned vector length at runtime. The v1 schema is fixed at `vector(768)`. Verify the selected embedding model/API supports 768-dimensional output before schema freeze; changing dimensions later requires a matching database migration.
* **Do not** use synchronous database drivers (`psycopg2`) inside FastAPI async routes — use `sqlalchemy.ext.asyncio` + `asyncpg`.
* **Do not** ask the LLM to trace callers/callees or calculate blast radius — all graph traversal is SQL/Tree-sitter deterministic.
* **Do not** treat a missing static caller as proof that a function is unreachable; dynamic dispatch and framework wiring may be invisible to the parser.
* **Do not** assume a single-process in-memory queue is safe for multi-worker deployment or durable job processing.
* **Do not** treat a passing patch test suite as proof that a patch is universally correct; require human review and report the exact verification scope.
* **Do not** ask the LLM to output unified diff hunks (`@@ -14,7 +14,9 @@`) — always request a complete replacement function block, splice by line numbers, and compute the diff via `difflib.unified_diff`.
* **Do not** run generated chaos tests on the host OS or with Docker network enabled — always enforce `--network none`, `--read-only` repo mount, and `--cap-drop ALL`.
* **Do not** modify any file inside `./data/repos/<repo_slug>` during patch verification — mount the temporary patched file read-only over the target path inside the verification container.
* **Do not** push high-frequency WebSocket log lines into React state that re-renders `<ForceGraph3D />` — keep Canvas mutations on imperative refs and HUD telemetry in throttled Zustand slices.
* **Do not** create a fake `UNRESOLVED_TARGET` node in `nodes` — use the nullable `dst_node_id` column on `edges`.

---

## Out of Scope for v1 (Future Expansion Hooks Preserved)

The following capabilities are excluded from the v1 build to maintain engineering focus, though the schema (`repos.commit_sha`, `AIProvider` interface, modular Tree-sitter grammar loader) is designed so they can be added without refactoring if time permits:

* Multi-language parsing beyond Python (e.g., TypeScript/Go Tree-sitter grammars)
* Git snapshot architectural drift diffs between two commits
* Dynamic runtime trace overlays (eBPF / Py-Spy)
* CI/CD GitHub Actions webhook integration
* Multi-tenant user authentication / RBAC (v1 is a single-user local engineering workstation platform)
* Automatic in-place overwriting of host source files without human export

---

## Developer Metadata

* **Author & Lead Architect:** Yadhu Nandhan T.J.
* **Project Classification:** MCA Main Project


---
