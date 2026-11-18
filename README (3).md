# CodeScape — Spatial Codebase Intelligence & Resilience Platform

> **Consistency revision — 2026-11-18:** All five engines, original phases, task IDs and future-work items are retained. Technical corrections align this document with `PROJECT_CONTEXT.md`; no capability is marked implemented by this revision. Existing filenames are retained; canonical names in the proposed folder tree are future names.

A local-first architectural intelligence, impact analysis, and resilience-testing platform that transforms a Python repository into an explorable **3D force-directed dependency graph**. CodeScape combines deterministic Tree-sitter analysis, semantic and structural code search, cycle-safe blast-radius tracing, isolated Docker chaos experiments, evidence-based failure triage and container-based patch verification. This README describes the intended v1 design; individual capabilities should be marked implemented only after they pass their documented tests.

---

## Table of Contents

- [Overview](#overview)
- [Development Status](#development-status)
- [Clarified v1 Contracts & Supported Repositories](#clarified-v1-contracts--supported-repositories)
- [Problem Statement](#problem-statement)
- [Core Design Principles](#core-design-principles)
- [Key Capabilities (The Five Engines)](#key-capabilities-the-five-engines)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Offline Presentation Mode (`--demo`)](#offline-presentation-mode---demo)
- [Environment Variables](#environment-variables)
- [API & WebSocket Contract](#api--websocket-contract)
- [Evaluation & Showcase Repository (`payflow-core`)](#evaluation--showcase-repository-payflow-core)
- [Scope & Future Work](#scope--future-work)
- [Author](#author)
- [License](#license)

---

## Overview

Modern software repositories quickly outgrow any single developer's mental model. Conventional 2D dependency diagrams collapse into unreadable "hairballs" of crossing edges on non-planar graphs, while naive "AI for code" tools paste raw files into an LLM and guess what calls a function or what a refactor might break.

**CodeScape** inverts that hierarchy. Static parsers (`Tree-sitter`) and relational graph queries (`PostgreSQL + pgvector`) construct a confidence-tagged static structural map and trace known failure-propagation paths deterministically, while generative AI (`google-genai`) is scoped to natural-language context synthesis, chaos-test parameter ideation and defensive patch drafting. Candidate defects and patches are assessed through structured evidence and bounded execution inside an isolated Docker container; static analysis and tests do not prove correctness for every runtime path.

---

## Development Status

Phase 0 is implemented and verified: the showcase repository, four-test baseline, reviewed contract fixture and sandbox image/build helper exist. The application engines below remain planned. Keep this section current as work progresses; documentation alone is not implementation evidence.

| Capability | Status | Evidence to mark implemented |
|---|---|---|
| Phase 0 showcase, contract and sandbox image | Implemented and verified (2026-11-18) | 18 Python files/54 functions, four passing baseline tests, HTTP/cycle smoke and two expected-failure contract reproductions; see `backend/test_harness/PHASE0_VERIFICATION.md`. |
| Repository ingestion and graph construction | Planned | Ingestion tests pass against `payflow-core`. |
| Graph-RAG and offline search fallback | Planned | Live semantic mode and labelled replay/lexical modes pass their respective tests. |
| Blast-radius traversal | Planned | Ground-truth paths and cycle tests pass. |
| Docker chaos sandbox | Planned | Isolation and resource-limit checks pass on the documented host. |
| Evidence-based triage | Planned | Classification fixture suite passes. |
| Patch verification | Planned | Candidate passes chaos and regression tests in a fresh container. |
| 3D frontend and telemetry | Planned | UI integration and measured rendering tests pass. |

Update the status and evidence as implementation advances.

Phase 0 evidence and repeatable commands are in [the verification report](backend/test_harness/PHASE0_VERIFICATION.md). On the current machine Docker Engine runs in Ubuntu-24.04 WSL, so use `wsl -d Ubuntu-24.04 --user root -- python3 /mnt/d/CodeScape/backend/utils/build_sandbox.py --skip-build` for the container checks. Windows host-safe checks are `python backend/utils/validate_harness.py` and `python -m unittest discover -s backend/tests -v`. Later application setup below remains a planned guide until the backend/frontend exist.

---

## Clarified v1 Contracts & Supported Repositories

- **Call-only analysis:** Caller/callee expansion, inferred roots and reverse blast radius use same-repository `kind='calls'` edges with known destinations and confirmed/probable confidence. Imports and inheritance remain separate stored relationships. Impact paths indicate potential dependencies, not guaranteed runtime failure propagation.
- **Unresolved calls:** `include_unresolved` controls detailed reporting only. Always return `unresolved_touch_count` and `completeness_note`, counting distinct unresolved calls sourced at the target or impacted callers. Toggling details never changes the impacted set. Render null-destination calls as source-attached dashed display stubs with expression/line tooltips; no sentinel database nodes or null graph-library targets.
- **Supported execution:** Initial live testing supports Python 3.11-compatible, Linux-compatible pytest projects with configured import roots, a prepared pinned dependency image and a non-empty passing baseline. Static inspection does not import target code. A `src/` layout requires an explicit import root and collection fixture. Common preinstalled packages support the showcase rather than every repository.
- **Preparation and portability:** Dependency installation/build hooks run only in a separate restricted disposable builder using reviewed manifests; never execute them on the host or expose host credentials/Docker sockets. Record source/manifest hashes, image digest, Python version, import roots and baseline IDs/counts in run evidence. Resolve native Windows host paths through configured roots and verify Docker Desktop mounts; `/tmp` paths are Linux/WSL examples.
- **Confirmation oracle:** Automatic `CONFIRMED_DEFECT` requires a reviewed executable fixture in `backend/test_harness/contracts/`, keyed by source hash and qualified symbol, with contract ID/version, documentation reference, input predicate, expected outcome and negative controls. Store compatibility/assertion checks, two fresh-container reproductions and passing baseline/setup controls. General-repository generated assertions without such fixtures remain low-confidence/advisory and require review; type hints and LLM judgments cannot confirm a defect.
- **Reporter ownership:** `conftest.py` provides narrow fakes; `codescape_pytest_reporter.py`, globally loaded with `-p`, owns all collection/phase/final-report hooks exactly once. Shared fakes across the two test locations need an explicitly registered global fixture plugin; sibling conftest fixtures do not apply automatically.
- **Verification evidence:** Require exit zero, complete valid phase reports, an actually executed passing chaos case and a non-empty passing selected regression suite, with no teardown/integrity failures. Preserve test/reporter/contract hashes, expected test IDs/counts and host-observed outcomes. Shared-process reports are not tamper-proof. Infrastructure failures use run `status='failed'`, `classification=NULL` and `report.infrastructure_error`; watchdog expiry remains `TIMEOUT`. A missing, empty, wholly skipped or failing baseline cannot support verified status.
- **Rendering:** Shared sphere geometry saves allocation/buffer memory; separate meshes still generally incur separate draw calls. Instancing/batching may reduce draw calls if measurements justify it. Keep complexity scaling and measure frame time, draw calls and navigation usability before claiming superior performance or 3D usability.
- **Terminology:** “Chaos experiment” remains the UI label for generated boundary-condition/malformed-input testing. Distributed fault injection is future work.

Hosted embedding at initial ingestion processes all included function/class chunks and may cumulatively disclose much of the included source. Function-scoped redaction limits individual requests, not total disclosure. No repository archive or whole-repository generation prompt is required; a local embedding provider remains future work.

The first integration milestone is **IG1**: local showcase ingestion, a basic 3D source view, call-only impact tracing, one reviewed contract case, sandbox classification and patch review/verification through the API/UI. Authored tests/candidates may establish the path first; live AI generation remains a separate requirement. All existing phases remain planned. See `implementation_plan (1).md` and `task_tracker.md` for dependencies and acceptance criteria.

## Problem Statement

1. **The Black-Box Dilemma:** Layered services, decorators, and callbacks obscure real call chains, causing developers to modify functions without knowing which upstream API endpoints depend on them.
2. **Fragile Refactoring:** High-complexity legacy routines remain untouched because engineers cannot predict cascading multi-hop regressions.
3. **2D Visualization Limitations:** Large dependency graphs can become difficult to navigate in conventional 2D layouts because of dense clusters, overlapping edges and limited visual separation. An interactive 3D view provides an alternative way to explore those relationships; it is not a claim that 2D layouts are universally unusable.
4. **The Exit-Code Trap in Automated Testing:** Naive AI test generators assume any failing test exit code represents a bug in the repository, failing to distinguish real code defects from generated syntax errors, broken imports, or mismatched test signatures.

---

## Core Design Principles

- **Deterministic Analysis First, Generative AI Second:** Symbols, complexity metrics, statically resolved call edges and blast-radius paths come from Tree-sitter syntax trees and SQL graph queries—not LLM inference. Dynamic Python behaviour can remain unresolved, and the graph reports that uncertainty explicitly.
- **Explicit Confidence Tagging:** Every call edge is classified as `confirmed` (resolved via import/local scope), `probable` (resolved via class hierarchy heuristic), or `unresolved` (dynamic dispatch, `getattr`, callback registries). Unresolved edges are stored with `dst_node_id = NULL`, rendered as dashed 3D lines, and counted in completeness notes.
- **Local-First, Minimal Egress:** Parsing, relational/vector storage and container execution run locally. Only redacted, function-scoped excerpts are sent through the configured `AIProvider`; live embedding and synthesis require an available provider.
- **Evidence-Based Verification Over Speculation:** A traceback frame identifies a candidate source location; it does not prove a defect by itself. Triage also checks generated-test validity, pytest phase, call compatibility, documented input contract, reproducibility and possible setup/mock/environment causes. A patch is reported as verified only after the configured chaos and regression tests pass in a fresh container; this is bounded test evidence, not a guarantee of production correctness.

---

## Key Capabilities (The Five Engines)

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

## System Architecture

| Component | Track / Layer | Responsibility |
|---|---|---|
| **WebGL Viewport** | Frontend Canvas Track | Three.js / `react-force-graph-3d` scene updated via imperative mutable refs (zero React re-renders during telemetry streaming) |
| **Engineering HUD** | Frontend HUD Track | Collapsible file rail, Monaco code inspector, side-by-side DiffEditor, and 100ms-throttled Zustand log store |
| **API & Stream Server** | Backend Layer | FastAPI async REST endpoints (`/api/v1/*`) + WebSocket container log streamer |
| **Unified Data Store** | Persistence Layer | PostgreSQL 16 + `pgvector` storing graph adjacency (`nodes`, `edges`), `vector(768)` embeddings (v1 schema dimension), `chaos_runs`, and `patches` |
| **Sandbox Worker** | Execution Layer | Network-isolated Docker containers executing `pytest` with narrow `conftest.py` fakes and a separately globally loaded reporting plugin |

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Lucide React |
| **3D Visualization** | Three.js, `react-force-graph-3d` |
| **State & Caching** | Zustand (throttled HUD store), Dexie.js (IndexedDB graph snapshot cache) |
| **Code & Diff Editor** | Monaco Editor (`@monaco-editor/react`) |
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Database & Vector Search** | PostgreSQL 16, `pgvector` (`vector(768)` v1 schema with HNSW cosine index), SQLAlchemy 2.0 (Async), `asyncpg` |
| **Static Analysis** | Tree-sitter (`tree-sitter`, `tree-sitter-python`) |
| **Container Sandbox** | Docker Engine, Python `docker` SDK, `pytest` |
| **Queue & Pub/Sub** | Redis (`redis.asyncio`) with an in-memory `asyncio.Queue` single-process development fallback (not durable) |
| **AI SDK & Models** | Official `google-genai` SDK; proposed configurable model defaults are `gemini-3.8-flash`, `gemini-3.5-flash-lite` and `gemini-embedding-2`; verify access and SDK compatibility before use; confirm the chosen embedding model supports the fixed v1 768-dimensional schema |

---

## Database Schema

CodeScape uses six core tables in PostgreSQL (`codescape`):
- **`repos`** — Ingested repository metadata, `commit_sha`, persistent clone path (`./data/repos/`), and sandbox image tag.
- **`nodes`** — Graph vertices (`file`, `class`, `function`), line ranges, McCabe `complexity`, HTTP `route_path`, full `body_text` (enabling standalone `--demo` inspection), and `embedding vector(768)`.
- **`edges`** — Directed relationships (`calls`, `imports`, `inherits`) with `confidence` (`confirmed`, `probable`, `unresolved`), nullable `dst_node_id`, and `raw_callee_expr`.
- **`chaos_runs`** — Experiment metadata, 3-tier `classification`, `blamed_node_id`, structured `report` (`JSONB`), and cached `log_ref`.
- **`patches`** — Replacement function code, deterministic `unified_diff`, verification status (`proposed`, `verified`, `failed`), and `verification_report` (`JSONB`).
- **`run_events`** — Durable WebSocket event history with per-run monotonic sequence numbers, event names, UTC timestamps and JSON payloads for reconnect/replay.

---

## Project Structure

- `backend/main.py` — FastAPI entry point, lifespan initialization, CORS, and `--demo` flag handler
- `backend/config.py` & `backend/database.py` — Async SQLAlchemy 2.0 + `pgvector` configuration
- `backend/Dockerfile.sandbox` — Non-root, pre-cached `pytest` container image definition
- `backend/models/` — SQLAlchemy ORM definitions (`repo.py`, `node.py`, `edge.py`, `chaos_run.py`, `patch.py`, `run_event.py`)
- `backend/routes/` — FastAPI REST & WebSocket routers (`repos.py`, `nodes.py`, `runs.py`, `patches.py`)
- `backend/services/` — The Five Core Engines (`ingestion_service.py`, `graph_rag_service.py`, `blast_radius_service.py`, `sandbox_service.py`, `triage_service.py`, `patch_service.py`, `ai_provider.py`, `queue_service.py`)
- `backend/utils/` — `build_sandbox.py`, `seed_demo.py`, `redaction.py`, and `evaluate_metrics.py`
- `backend/test_harness/payflow-core/` — Curated 18-file, 54-function Python showcase repository with seeded defect and regression suite
- `frontend/src/components/Canvas/` — `ForceGraphScene.tsx` and `ParticleEngine.ts`
- `frontend/src/components/HUD/` — `TopBar.tsx`, `LeftFileRail.tsx`, `RightInspector.tsx`, `BottomTerminal.tsx`, and `DiffReviewModal.tsx`
- `frontend/src/store/` & `frontend/src/cache/` — `useHudStore.ts` (Zustand) and `graphCache.ts` (Dexie.js)

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and `npm`
- **PostgreSQL 16+** with the `pgvector` extension installed
- **Docker Desktop / Docker Engine** (required for live chaos sandbox runs; optional in `--demo` mode)
- **Google Gemini API Key** (required for live semantic embeddings and AI test/patch generation; optional for structural ingestion, lexical search and `--demo` mode)

### 1. Backend & Sandbox Setup

1. Navigate to `backend/`, create a virtual environment (`python -m venv .venv`), activate it, and install dependencies (`pip install -r requirements.txt`).
2. Create a PostgreSQL database named `codescape` and enable `pgvector` (`CREATE EXTENSION IF NOT EXISTS vector;`).
3. Configure `backend/.env` using the template in [Environment Variables](#environment-variables).
4. Build the isolated chaos sandbox Docker image:
   `python utils/build_sandbox.py`
5. During Phase 1/P2 setup, run the explicit `google-genai` smoke test for the configured reasoning, summary and embedding models. Verify API access/SDK compatibility and assert the embedding response has exactly 768 values. The model IDs shown below are proposed defaults and must be replaced if unavailable to the account. Routine FastAPI startup does not make live model calls.
6. After defining all six SQLAlchemy models (including `RunEvent` in task 1.12), apply the Alembic baseline (`alembic upgrade head`) before verifying the PostgreSQL schema.
7. Seed the pre-computed `payflow-core` snapshot (optional, for instant demo readiness):
   `python utils/seed_demo.py`
8. Start the FastAPI server on port `8000` (from the `backend/` directory):
   `uvicorn main:app --reload --port 8000`

Run the backend and frontend in separate terminals. The exact commands should be smoke-tested against the checked-in scripts before treating this section as a verified setup guide. Use a non-default local database password and never commit `.env`.

### 2. Frontend Setup

1. Navigate to `frontend/`, install packages (`npm install`), and launch the Vite dev server (`npm run dev`).
2. Open `http://localhost:5173` in your browser.

---

## Offline Presentation Mode (`--demo`)

When presenting in restricted environments without Docker daemon access or internet connectivity, launch the backend with `--demo` (or set `DEMO_MODE=true` in `backend/.env`):

`python main.py --demo`

Alternatively, set `DEMO_MODE=true` in `backend/.env` and run `uvicorn main:app --reload --port 8000`. Both entry points use the same application factory and lifespan. The CLI `--demo` flag explicitly enables demo mode; otherwise the environment setting controls it.

In `--demo` mode, CodeScape serves the precomputed `payflow-core` graph and source text, recorded chaos-run evidence/logs, and a stored patch/diff report from the local PostgreSQL database. It supports 3D navigation, camera flight, deterministic blast-radius traversal, source inspection and recorded chaos/patch walkthroughs without Docker or live LLM calls.

Offline search has two explicit behaviours: (1) replay of a curated set of precomputed benchmark queries/results, and (2) deterministic lexical fallback over stored symbol names, signatures, docstrings and source text. The UI/API must label which mode produced each result. Stored repository embeddings cannot embed a new arbitrary query; fresh semantic search requires a configured embedding provider. A replayed verification result is not a new sandbox verification. PostgreSQL remains a local dependency for this architecture. After re-ingesting `payflow-core`, rerun `python utils/seed_demo.py`: node replacement cascades to recorded `chaos_runs` and `patches`, and the idempotent seeder resolves new node IDs and restores the single canonical demo run/patch and its replay event history using unique seed keys.

---

## Environment Variables

Create `backend/.env` with the following keys (never commit `.env` to version control):

- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codescape`
- `AI_PROVIDER=gemini`
- `GEMINI_API_KEY=your_gemini_api_key_here`
- `GEMINI_REASONING_MODEL=gemini-3.8-flash`
- `GEMINI_SUMMARY_MODEL=gemini-3.5-flash-lite`
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-2`
- `EMBEDDING_DIMENSIONS=768` *(fixed for v1; change only with a matching database migration)*
- `REDIS_URL=redis://localhost:6379/0` *(optional; automatically falls back to in-memory `asyncio.Queue` if unreachable)*
- `REPOS_STORAGE_PATH=./data/repos`
- `EPHEMERAL_RUNS_PATH=/tmp/codescape/runs`
- `SANDBOX_IMAGE_TAG=codescape-sandbox:latest`
- `SANDBOX_TIMEOUT_SECONDS=8`
- `DEMO_MODE=false`
- `CORS_ORIGINS=http://localhost:5173`

---

## API & WebSocket Contract

All REST endpoints are prefixed with `/api/v1` and return the standard JSON envelope:
`{"success": true, "data": {...}, "message": "..."}`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/repos` | Clone/copy and run 2-pass Tree-sitter ingestion on a Python repository |
| `GET` | `/api/v1/repos` | List ingested repositories |
| `GET` | `/api/v1/repos/{id}/graph` | Fetch all nodes, confidence-tagged edges, and complexity metrics for the 3D scene |
| `POST` | `/api/v1/repos/{id}/search` | Execute search; response identifies `live_semantic`, `replay` or `lexical_fallback` mode and may include 1-hop context/AI summary |
| `GET` | `/api/v1/nodes/{id}` | Retrieve full symbol metadata and `body_text` for the Monaco code inspector |
| `GET` | `/api/v1/nodes/{id}/blast-radius` | Run call-only reverse traversal (`max_depth`); `include_unresolved` adds details without changing impact results/counts |
| `POST` | `/api/v1/nodes/{id}/chaos-runs` | Generate boundary-condition tests and queue an isolated Docker chaos run |
| `WS` | `/api/v1/runs/{id}/stream` | Stream real-time container logs and `VisualNodeState` transitions |
| `GET` | `/api/v1/runs/{id}` | Fetch completed 3-tier triage classification and structured frame report |
| `POST` | `/api/v1/runs/{id}/patch` | Draft replacement function and compute deterministic `difflib.unified_diff` |
| `POST` | `/api/v1/patches/{id}/verify` | Verify patch in sandbox against failing chaos test + existing `tests/` suite |
| `GET` | `/api/v1/patches/{id}/export` | Export verified unified diff as a downloadable `.patch` file |

---

### WebSocket event envelope

All WebSocket messages from `queue_service.py` and `routes/runs.py` to `frontend/src/services/ws.ts` use one envelope:

```json
{
  "run_id": 42,
  "seq": 17,
  "event": "chaos_test_completed",
  "ts": "2026-11-12T08:30:00Z",
  "payload": { "classification": "CONFIRMED_DEFECT", "node_id": 123 }
}
```

`seq` increases monotonically per run. The client reconnects with `?after_seq=<last_seen_seq>`; the backend subscribes/buffers live events, replays durable `run_events` rows after that cursor, then merges and deduplicates by sequence to avoid a replay/live handoff gap. Log text and visual-state details belong inside `payload`; alternate top-level event shapes are not used.

## Evaluation & Showcase Repository (`payflow-core`)

CodeScape includes a purpose-built reference test harness (`backend/test_harness/payflow-core/`) containing 18 files and ~54 functions across a simulated payment and webhook architecture:
- **All 3 Edge Confidence Levels:** Standard imports (`confirmed`), class method calls (`probable`), and a dynamic event registry `EVENT_REGISTRY[event_type](payload)` (`unresolved`).
- **Deliberate Call Cycle:** Mutual recursion between `utils/retry.py` and `utils/audit.py` to verify cycle-safe recursive CTE termination.
- **Seeded In-Contract Defect:** `verify_signature(payload: str, sig: str) -> bool` in `services/auth.py`. Its documented contract states that malformed/empty signature strings are valid external inputs and should return `False`; the seeded implementation instead performs unguarded `bytes.fromhex()` decoding and raises. It is called by `handle_webhook`, which is called by the `/api/v1/stripe` route (two call edges and three displayed nodes). This makes the defect in-contract by documented behaviour, not merely by type hints.
- **Regression Suite:** `tests/test_payflow.py` contains exactly four passing baseline unit tests and must pass on the unpatched repository. Keep the malformed-signature failing case out of `tests/`; generate it separately as `/workspace/test_run/test_chaos.py`. Patch verification runs that chaos test plus the four baseline tests. Passing this limited suite does not prove absence of all regressions.

Evaluation reports should document the ground-truth fixture, precision/recall denominators, query relevance rules, blast-radius matching rules, classification labels, repository size, hardware, provider mode, sample count and median/p95 latency. Publish measured values only; do not present planned targets as achieved results.

---

## Scope & Future Work

- **In Scope (v1):** Python repositories, Two-Pass Tree-sitter static modeling, Hybrid Graph-RAG with 3D camera flight, recursive Blast-Radius tracing, isolated Docker chaos testing, 3-Tier failure triage, closed-loop `difflib` patch verification, and offline `--demo` mode.
- **Planned Extensions:** Full air-gapped local LLM execution (`OllamaProvider`), Git commit snapshot architectural drift diffs, additional Tree-sitter language grammars, and CI pull-request blast-radius hooks.

---

## Author

**Yadhu Nandhan T.J.**\
MCA Main Project

---

## License

MIT. Include the full MIT license text in the repository's `LICENSE` file.
