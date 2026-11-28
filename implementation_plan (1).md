# CodeScape — Full Development & Implementation Plan

> **Consistency revision — 2026-11-18:** All five engines, original phases, task IDs and future-work items are retained. Technical corrections align this document with `PROJECT_CONTEXT.md`; no capability is marked implemented by this revision. Existing filenames are retained; canonical names in the proposed folder tree are future names.

> **Goal:** Build the complete **CodeScape: Spatial Codebase Intelligence & Resilience Platform** — a local-first 3D dependency visualization, Hybrid Graph-RAG, deterministic blast-radius tracer, containerized chaos testing sandbox, and closed-loop patch verification platform — exactly as specified in `PROJECT_CONTEXT.md`.

---

## Architectural & Implementation Decisions (Locked)

These foundational decisions are finalized and must not be re-litigated during coding sessions:

1. **Prerequisite Test Harness First (Phase 0):** Ingestion, recursive blast-radius traversal, and sandbox verification cannot be tested without a deterministic target repository on disk. Therefore, the curated 18-file, 54-function `payflow-core` repository (with all three edge confidence levels, a deliberate call cycle, honest type hints on a seeded defect, and a passing `tests/` regression suite) is built in **Phase 0** before any backend engine code is written.
2. **Database & Vector Engine:** Single unified **PostgreSQL 16 + `pgvector`** database accessed via **SQLAlchemy 2.0 (Async) + `asyncpg`**. No separate vector database (like ChromaDB) is used so that vector similarity anchors and 1-hop relational edge joins execute in one transactional store.
3. **Modern Google GenAI SDK (`google-genai`):** Use the official `google-genai` package behind an abstract `AIProvider` interface. The current model IDs (`gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-embedding-2`) are proposed configuration defaults, not assumed guarantees. Before implementation freeze, verify model availability, SDK support, account access, quotas and the embedding API's supported output dimensions. Keep model IDs configurable. During Phase 1/P2, run a `google-genai` smoke test for the configured reasoning (`gemini-3.8-flash`), summary (`gemini-3.5-flash-lite`) and embedding (`gemini-embedding-2`) models, verifying authentication, account access, SDK compatibility and minimal calls. For v1, keep the database dimension fixed at 768 to match `vector(768)`; assert `len(vec) == 768` for every embedding before insert. Do not make routine app startup depend on live model access. A future dimension change requires a coordinated schema migration.
4. **Queue & WebSocket Fan-Out:** Implement `queue_service.py` with Redis pub/sub and an in-memory `asyncio.Queue` development fallback. The in-memory fallback is single-process only and not durable; Redis pub/sub is also not a durable job queue. Persist run/job state in PostgreSQL and document restart/reconnect behaviour. WebSocket events carry run IDs, event IDs/sequences and timestamps; support replay from a cursor where feasible.
5. **Two-Pass Static Ingestion:** Tree-sitter parses every file in Pass 1 to populate `nodes` and build an in-memory `qualified_name -> node_id` dictionary, then re-walks syntax trees in Pass 2 to resolve cross-file imports and call sites into `edges` (`confirmed`, `probable`, `unresolved` with nullable `dst_node_id`).
6. **Deterministic Unified Diffs:** The LLM never generates unified diff hunks (`@@ ... @@`). It returns a complete replacement function/method block. The backend verifies the target symbol, sync/async form, signature, decorators and source span; preserves indentation; validates the complete patched module; and generates the diff with `difflib.unified_diff()`. Stale or ambiguous source spans are rejected.
7. **Future-Proof Extensibility Hooks (Phase 8 Optional):** The database schema (`repos.commit_sha`), parser registry, and `AIProvider` interface include clean extension points so optional future features (Git Snapshot Diff, Ollama local air-gapped provider, additional Tree-sitter grammars) can be bolted on after Phase 7 without refactoring core modules.

---

## Cross-Cutting Implementation Contracts (Apply in Every Phase)

These requirements supersede any older task wording that implies a traceback frame alone proves a defect, that demo mode performs arbitrary live semantic search offline, or that basic Docker flags constitute complete isolation.

### Canonical triage outcomes

Use these exact values in models, API schemas, WebSocket events, tests and frontend badges: `INVALID_GENERATION`, `SETUP_FAILURE`, `SIGNATURE_MISMATCH`, `CONFIRMED_DEFECT`, `LOW_CONFIDENCE_DEFECT`, `BEHAVIORAL_ANOMALY`, `TIMEOUT`, and `PASSED`. A repository traceback frame is an attribution clue only. `CONFIRMED_DEFECT` requires a valid generated test, compatible target invocation, in-contract input based on documented behaviour/preconditions, reproducibility, and evidence that the failure is attributable to repository behaviour rather than setup, mocks or environment. Type hints alone do not establish runtime contracts. Otherwise use `LOW_CONFIDENCE_DEFECT` or `BEHAVIORAL_ANOMALY` and retain the evidence.

Capture pytest collection failures separately (for example with `pytest_collectreport`) and capture setup/call/teardown phases with `pytest_runtest_makereport`; persist a final report at session end. Test traceback frame ordering rather than assuming it. Load the reporting hook globally as importable module `codescape_pytest_reporter` using `-p codescape_pytest_reporter`; expose `/workspace/repo` and `/workspace/test_run` via `PYTHONPATH=/workspace/repo:/workspace/test_run` so the plugin reports both `/workspace/test_run/test_chaos.py` and `/workspace/repo/tests/` into one report.

### Offline demo contract

Offline demo mode may replay precomputed benchmark query results and recorded chaos/patch events, and may perform deterministic lexical search over stored symbol text. It cannot embed an arbitrary new query using repository vectors alone. Live semantic query embedding and LLM synthesis require an available configured provider. The API and UI must label `replay`, `lexical_fallback` and `live_semantic` search modes distinctly. A replayed patch verification is not a newly executed verification. PostgreSQL remains required for the current local demo architecture unless a self-contained snapshot store is explicitly implemented.

### Static analysis contracts

Define the McCabe-style decision-point count exactly once in `PROJECT_CONTEXT.md` and implement tests for each construct. Do not double-count `elif`; include `async for`, Boolean operand increments, conditional expressions and comprehension filters according to that definition. Treat `match`/`case` consistently and document if excluded. Static call graphs are incomplete for dynamic Python; preserve `unresolved` edges and distinguish confirmed entrypoints from inferred root nodes. A node with no known callers is not automatically a public entrypoint.

### Repository and sandbox safety

Treat user repositories as untrusted. Enforce clone/path validation, traversal and symlink checks, repository size/file-count limits and safe cleanup. Keep repository content read-only in the container. In addition to `--network none`, use a read-only root filesystem where practical, bounded writable `tmpfs`, seccomp/AppArmor where available, file-descriptor/disk limits, non-root execution, dropped capabilities and `no-new-privileges`. Do not mount the Docker socket into the sandbox. Avoid blanket `sys.modules` MagicMock substitution; use narrow, explicit interface fakes. Docker is defence in depth, not an absolute isolation guarantee.

### Patch safety

Before splicing, confirm the source revision and exact target span. Validate the replacement's function name, signature, decorators, sync/async form and class indentation. Compile/parse the complete patched module. Reject stale/ambiguous spans and unsafe paths. Apply a candidate through a separate read-only overlay in a fresh container; never edit the persistent repository. Mark a patch verified only when the chaos test and selected regression suite pass, and retain test/environment evidence. Human review remains required before adoption.

### Operational foundations

After SQLAlchemy models `1.4`–`1.8` and the `RunEvent` model from `1.12` are defined, execute task `1.15` to create and apply the Alembic baseline; only then execute task `1.14` to verify PostgreSQL tables, constraints and indexes. Alembic is authoritative; do not use `create_all()` as a competing schema path. Validate `EMBEDDING_DIMENSIONS=768` against `vector(768)` at startup and assert `len(vec) == 768` for every returned embedding before insert. Run the explicit Phase 1/P2 `google-genai` access smoke test for the configured reasoning, summary and embedding models separately from routine startup. Treat in-memory queue fallback as single-process development only. Use one WebSocket envelope (`run_id`, `seq`, `event`, `ts`, `payload`) across `queue_service.py`, `routes/runs.py` and `ws.ts`; persist events in PostgreSQL `run_events` and replay after `?after_seq=` on reconnect.

---

### Clarified v1 implementation contracts

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

### Early integration gate (IG1)

Keep the phase graph as a feature-dependency map, but do not interpret it as requiring all backend features before any working UI. After Phase 2's structural graph endpoint, pull forward the minimum call traversal, sandbox/reporter/triage/patch path and basic Phase 5–6 inspection/review controls. Prove local `payflow-core` ingestion → basic 3D/source view → call-only blast radius → reviewed malformed-signature case → evidence-based classification → reviewed patch → fresh-container chaos + four-baseline verification. Use an authored test/candidate first and clearly mark generation pending; then integrate the configured AI provider. IG1 must pass before broad Phase 4 completion and polish. Record selected source/image/test evidence and an invalid-test negative control. This is an integration checkpoint, not a replacement for later tasks or final evaluation.

Structural ingestion remains available without AI: persist nodes/edges with nullable embeddings and expose lexical search. Task 2.7 still implements live embeddings; validate it before marking semantic search complete. Keep static extraction and provider latency separate in benchmarks.

## Phases & Dependency Flow

```text
Phase 0: Reference Test Harness (payflow-core) & Docker Sandbox Image
      │
      ▼
Phase 1: Backend Foundation, Async PostgreSQL + pgvector Schema & AIProvider
      │
      ▼
Phase 2: Engine 1 (Two-Pass Tree-sitter Ingestion & Complexity)
      │
      ├─────────────────────────────────────────┐
      ▼                                         ▼
Phase 3: Engine 2 (Hybrid Graph-RAG)     Phase 5: Frontend Foundation,
      &  Engine 3 (Blast Radius CTE)              3D ForceGraph Canvas &
      │                                           Decoupled Zustand HUD
      ▼                                         │
Phase 4: Engine 4 (Docker Chaos Sandbox)        ▼
      &  Engine 5 (3-Tier Triage &       Phase 6: HUD Interactive Workflows,
         Closed-Loop Patch Verifier)              Camera Flight, Monaco Diff &
      │                                           WebSocket Telemetry
      └────────────────────┬────────────────────┘
                           ▼
             Phase 7: --demo Mode Snapshot,
                      Evaluation Metrics &
                      End-to-End Verification
                           │
                           ▼
             Phase 8 (Optional / Time-Permitting):
                      Ollama Air-Gapped Provider &
                      Git Snapshot Architectural Diff
```

> **Execution Sequence:**
> - **Phases 0 → 1 → 2 → 3 → 4** retain backend feature dependencies; IG1 pulls the minimum required portions of Phases 3–6 forward before broad backend completion.
> - **Phase 5** can begin as soon as Phase 2 (`GET /api/v1/repos/{id}/graph`) is ready.
> - **Phase 6** connects the 3D HUD to Engines 2, 3, 4, and 5.
> - **Phase 7** creates the `--demo` offline snapshot and runs the evaluation harness.

---

## Phase 0: Reference Test Harness (`payflow-core`) & Sandbox Base Image

Build the ground-truth target repository and isolated container image first so every subsequent engine can be tested against real code immediately.

#### [NEW] `backend/test_harness/payflow-core/`
Construct an 18-file, ~54-function Python microservice repository simulating a payment & webhook processing backend:
- **`app.py` & `routes/stripe.py`, `routes/checkout.py`, `routes/users.py`, `routes/refunds.py`:** Include explicit route decorators (`@app.post("/api/v1/stripe")`, `@router.post("/checkout/charge")`, `@router.get("/user/profile")`) to test entrypoint detection in Engine 1 and Engine 3.
- **`services/auth.py`:**
  - Contains the seeded defect in `verify_signature(payload: str, sig: str) -> bool`.
  - Has a documented function contract: both arguments are strings, and empty/malformed signature strings are valid external inputs that must return `False` rather than crash. Type hints alone are not the contract.
  - The seeded implementation performs unvalidated hex decoding (`bytes.fromhex(sig.split("v1=")[1])`) and raises `ValueError` or `IndexError` on those in-contract malformed inputs.
  - Called by `handle_webhook` in `services/webhook_listener.py`, which in turn is called by `/api/v1/stripe` in `routes/stripe.py` (three-node chain with two reverse call hops).
- **`services/dispatcher.py`:**
  - Implements a dictionary callback registry: `handler = EVENT_REGISTRY[event_type]; return handler(payload)`.
  - Guarantees Engine 1 extracts `unresolved` call edges (`dst_node_id = NULL`, `raw_callee_expr = "handler(payload)"`) for dashed-edge rendering and completeness notes.
- **`utils/retry.py` & `utils/audit.py`:**
  - Include a deliberate mutual call cycle (`retry_with_audit` $\leftrightarrow$ `audit_and_retry`) so Engine 3's PostgreSQL recursive CTE cycle guard (`visited_path`) is verified under test.
- **`tests/test_payflow.py`:**
  - Keep `tests/test_payflow.py` strictly to four passing baseline regression tests (valid signature verification, checkout calculation and user profile lookup). The malformed-signature defect case must not be added to this directory: it is generated/written separately as `/workspace/test_run/test_chaos.py`. The unpatched baseline command must pass cleanly. Patch verification runs the generated chaos test and the four-test repository suite together.

#### [NEW] `backend/Dockerfile.sandbox`
- Base image: `python:3.11-slim`
- Create non-root group and user `sandbox` (`UID 1000`, `GID 1000`).
- Install `pytest` and common target dependencies (`pydantic`, `fastapi`, `requests`, `httpx`, `stripe`, `boto3`, `psycopg2-binary`) during image build so runtime containers need zero network access.
- Set `ENV PYTHONDONTWRITEBYTECODE=1` and `ENV PYTHONPATH=/workspace/repo`.
- Set `WORKDIR /workspace/test_run` and `USER 1000:1000`.

#### [NEW] `backend/utils/build_sandbox.py`
- Helper script that builds `Dockerfile.sandbox` into local Docker image tag `codescape-sandbox:latest` and verifies `docker run --rm --network none codescape-sandbox:latest pytest --version`.

---

**Phase 0 implementation evidence (2026-11-18):** The showcase now contains exactly 18 Python files and 54 explicit functions/methods including four baseline tests. The image built in Ubuntu WSL; all four baseline tests and HTTP/dispatcher/bounded-cycle smoke checks pass in hardened network-disabled containers. Two fresh oracle runs each reproduce three intentional malformed-signature exceptions with four passing controls. Source hashes remain unchanged. See `backend/test_harness/PHASE0_VERIFICATION.md`; later engines and IG1 remain planned. Illustrative source-line references in future demo descriptions must be resolved from the actual source/traceback (the seeded decode currently occurs at `services/auth.py:32`).

## Phase 1: Backend Foundation, Async DB Schema & `AIProvider`

Establish the FastAPI server, async PostgreSQL + `pgvector` models, standard response envelopes, and the redacted `google-genai` provider layer.

#### [NEW] `backend/requirements.txt`
- Core packages: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `pgvector`, `pydantic`, `pydantic-settings`, `python-dotenv`, `tree-sitter`, `tree-sitter-python`, `google-genai`, `docker`, `redis`, `gitpython`, `httpx`, `alembic`.

#### [NEW] `backend/config.py`
- `Settings(BaseSettings)` loading all variables defined in `PROJECT_CONTEXT.md` (`DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_REASONING_MODEL="gemini-3.8-flash"`, `GEMINI_SUMMARY_MODEL="gemini-3.5-flash-lite"`, `GEMINI_EMBEDDING_MODEL="gemini-embedding-2"`, `EMBEDDING_DIMENSIONS=768` (fixed for v1 schema; change only with a migration), `DEMO_MODE`, etc.).

#### [NEW] `backend/database.py`
- Create `AsyncEngine` via `create_async_engine(settings.DATABASE_URL)` and `async_sessionmaker`.
- Create the async engine/session layer and ensure the `vector` extension is available. Do not use `create_all()` as the authoritative schema path. After models `1.4`–`1.8` and `RunEvent` from `1.12` are defined, execute task `1.15` to create and apply the Alembic baseline; then execute `1.14` to verify all tables, constraints and indexes. Validate configured vector dimensions against `Vector(768)` at startup.

#### [NEW] `backend/models/`
Implement the SQLAlchemy 2.0 `DeclarativeBase` models matching `PROJECT_CONTEXT.md` exactly, including `RunEvent` for durable WebSocket replay:
- **`repo.py` (`Repo`):** `id`, `name`, `source_url`, `commit_sha`, `local_path`, `image_tag`, `status`, `ingested_at`.
- **`node.py` (`Node`):** `id`, `repo_id`, `kind`, `qualified_name`, `file_path`, `start_line`, `end_line`, `signature`, `docstring`, `route_path`, `complexity`, `body_text`, `embedding = mapped_column(Vector(768))`.
- **`edge.py` (`Edge`):** `id`, `repo_id`, `src_node_id`, `dst_node_id` (**nullable**), `kind`, `confidence`, `call_site_line`, `raw_callee_expr`.
- **`chaos_run.py` (`ChaosRun`):** `id`, `repo_id`, `node_id`, `blamed_node_id` (nullable), `status`, `classification`, `test_code`, `report` (`JSONB`), `log_ref`, optional unique `seed_key`, `started_at`, `finished_at`.
- **`patch.py` (`Patch`):** `id`, `run_id`, `node_id`, `replacement_code`, `unified_diff`, `rationale`, `status`, `verification_report` (`JSONB`), optional unique `seed_key`, `created_at`, `verified_at`.
- **`run_event.py` (`RunEvent`):** `id`, `run_id`, per-run monotonic `seq`, `event`, UTC `ts`, and `payload` (`JSONB`); enforce unique `(run_id, seq)`.

#### [NEW] `backend/schemas/common.py`
- `api_response(data, message="Success", status_code=200)` and `error_response(message, status_code=400)` returning the mandatory `{"success": bool, "data": ..., "message": str}` envelope.

#### [NEW] `backend/utils/redaction.py`
- `redact_code_excerpt(text: str) -> str`: Scrubs high-entropy API keys, bearer tokens, private key blocks, and `.env` assignments before any code snippet is passed to `AIProvider`.

#### [NEW] `backend/services/ai_provider.py`
- Abstract base class `AIProvider` with four methods:
  - `embed_texts(texts: list[str]) -> list[list[float]]`
  - `summarize_graph_context(query: str, anchor: dict, callers: list[dict], callees: list[dict]) -> str | None`
  - `generate_chaos_test(target_node: dict, callees: list[dict]) -> str`
  - `draft_function_patch(target_node: dict, test_code: str, traceback_report: dict) -> dict`
- Concrete class `GeminiProvider(AIProvider)` using `from google import genai` and `from google.genai import types`:
  - Embeddings call `client.models.embed_content(model=settings.GEMINI_EMBEDDING_MODEL, contents=..., config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIMENSIONS))`.
  - Summarization uses `settings.GEMINI_SUMMARY_MODEL` wrapped in `try/except` returning `None` on failure (graceful degradation).
  - Chaos test generation and patch drafting use `settings.GEMINI_REASONING_MODEL` after running `redact_code_excerpt()`.
- Concrete stub `OllamaProvider(AIProvider)` raising a clear not-configured message or connecting to local Ollama URL if `AI_PROVIDER=ollama` is set in Phase 8.
- Add `backend/utils/smoke_test_genai.py` or equivalent P2 setup command: call each configured reasoning/summary model with a minimal prompt, call the embedding model with `output_dimensionality=768`, and assert the returned vector length is 768. Report unavailable model IDs, permission/quota/SDK errors clearly; do not make routine FastAPI startup call the provider.

#### [NEW] `backend/services/queue_service.py`
- Unified pub/sub streamer `LogStreamBroker`:
  - Persists every event to PostgreSQL `run_events` with per-run monotonic `seq` before fan-out. Redis pub/sub or the in-memory single-process queue is only the live transport, not replay storage.
  - Uses one envelope `{run_id, seq, event, ts, payload}` for logs, state transitions and triage events.
  - Supports reconnect via `?after_seq=<last_seen_seq>`: subscribe and buffer live events first, replay persisted events after the cursor, then merge/deduplicate by `seq` to avoid a replay/live handoff gap. Allocate each per-run sequence while locking the parent run row (or with an equivalent atomic counter).

#### [NEW] `backend/main.py`
- Implement a shared `create_app(demo_mode: bool | None = None)` factory for FastAPI initialization, lifespan, CORS and router registration. Module-level `app = create_app()` reads `DEMO_MODE` for `uvicorn main:app`. The `if __name__ == "__main__"` CLI parses `--demo` and runs `uvicorn` with `create_app(demo_mode=True)`; the CLI flag explicitly enables demo mode and does not create a separate startup/lifespan path.

---

## Phase 2: Engine 1 — Two-Pass Tree-sitter Ingestion & Complexity

Build the static parser that turns a local or cloned Python repository into confidence-tagged nodes, edges, complexity scores, and 768-d embeddings.

#### [NEW] `backend/services/ingestion_service.py`
Implement `ingest_repository(repo_path_or_url: str, db: AsyncSession) -> Repo`:
1. **Repository Acquisition & Filtering:**
   - If `repo_path_or_url` is a local directory (e.g., `./backend/test_harness/payflow-core`), copy/sync to `./data/repos/<name>` and read current git `commit_sha` if present. If a remote git URL, clone into `./data/repos/<name>`.
   - Walk `.py` files while filtering out `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `build`, `dist`, and `.env*`.
2. **Pass 1 — Symbol Extraction & McCabe Complexity:**
   - Parse each file with `tree_sitter_python`.
   - Extract `file` node, `class_definition` nodes, and `function_definition` / `decorated_definition` nodes.
   - Inspect decorators for `@app.<method>("<path>")` or `@router.<method>("<path>")` to populate `route_path`.
   - Calculate the CodeScape McCabe-style metric using the exact decision-point contract in `PROJECT_CONTEXT.md`: `if`, `elif`, `for`, `async for`, `while`, each `except` handler, additional Boolean operands, conditional expressions and comprehension filters. Avoid double-counting `elif`; add parser unit tests for each construct. `match`/`case` must be explicitly included or excluded.
   - Flush all `Node` rows to PostgreSQL to obtain primary keys and build `symbol_map: dict[str, Node]`, plus a class-method lookup map and file-scope import alias map.
3. **Pass 2 — Call & Import Resolution with Confidence Tagging:**
   - Re-walk cached ASTs for every function and class body.
   - For every `call` node:
     - Resolve against local scope or explicit file imports $\rightarrow$ `Edge(kind='calls', confidence='confirmed', dst_node_id=target.id)`.
     - Resolve `self.<method>()` when the class scope or hierarchy identifies a candidate $\rightarrow$ `Edge(kind='calls', confidence='probable', dst_node_id=target.id)`. An unknown receiver with only a same-named method in the repository stays unresolved.
     - Otherwise (dynamic subscript call `EVENT_REGISTRY[k](x)`, `getattr`, unresolvable callback) $\rightarrow$ `Edge(kind='calls', confidence='unresolved', dst_node_id=None, raw_callee_expr=expr_text)`.
   - Bulk-insert all `Edge` rows.
4. **Batched Vector Embedding:**
   - Batch all `function` and `class` nodes (e.g., 32 per batch), redact secrets, generate 768-d vectors via `ai_provider.embed_texts()`, and update `nodes.embedding`.

#### [NEW] `backend/routes/repos.py` (Ingestion & Graph Endpoints)
- `POST /api/v1/repos` — Trigger ingestion for `payflow-core` or a provided repo URL/path. The optional repository-relative `import_root` defaults to `.` and maps a directory such as `src` to the top level of static Python imports.
- `GET /api/v1/repos` — List all ingested repositories.
- `GET /api/v1/repos/{id}/graph` — Return all `nodes` (excluding raw 768-float embedding array to keep JSON payload lean, but including `complexity`, `kind`, `route_path`, `file_path`, `start_line`, `end_line`) and all `edges` (`src_node_id`, `dst_node_id`, `confidence`, `raw_callee_expr`), plus summary counts.

---

## Phase 3: Engine 2 (Hybrid Graph-RAG) & Engine 3 (Blast Radius CTE)

Build semantic+structural search and deterministic reverse impact traversal.

#### [NEW] `backend/services/graph_rag_service.py`
Implement `hybrid_graph_search(repo_id: int, query: str, db: AsyncSession, mode: SearchMode)`:
1. Validate `query.strip()` is non-empty (raise 400 if empty).
2. In `live_semantic` mode, embed the query using `ai_provider.embed_texts([query])`, validate vector length and query non-null embeddings within the active repository ordered by cosine distance. If query embedding fails, return explicitly labelled lexical fallback or a clear unavailable result when disabled; do not claim a vector anchor. Summary-only failure preserves an already computed anchor.
3. In `replay` mode, match against the curated benchmark query set and return its stored result/anchor.
4. In `lexical_fallback` mode, rank stored symbol names, signatures, docstrings and `body_text` deterministically without an embedding call.
5. Select the anchor and return the selected search mode plus a mode-specific explanation. Never silently fall back while labelling the result live semantic.
6. Query same-repository `kind='calls'` edges joined with nodes; resolved caller/callee joins require non-null destinations and confirmed/probable confidence:
   - **Direct Callers (1-hop incoming):** `Edge.dst_node_id == anchor_node.id`
   - **Direct Callees (1-hop outgoing):** `Edge.src_node_id == anchor_node.id` and `Edge.dst_node_id.is_not(None)`
   - **Unresolved Outgoing Calls:** count and list `raw_callee_expr` where `Edge.src_node_id == anchor_node.id` and `Edge.confidence == 'unresolved'`.
7. Call `ai_provider.summarize_graph_context(query, anchor_node, callers, callees)` only when a provider is available; return `None` on provider error without failing deterministic search.
8. Return `search_mode`, `anchor_node`, `secondary_matches`, `callers`, `callees`, `unresolved_calls`, and `ai_summary`.

#### [NEW] `backend/services/blast_radius_service.py`
Implement `compute_blast_radius(node_id: int, max_depth: int, include_unresolved: bool, db: AsyncSession)`:
1. Execute the cycle-safe PostgreSQL `WITH RECURSIVE` query walking backward from `dst_node_id` to `src_node_id`:
   - Base case: direct callers of `node_id`, excluding self-calls, with `depth = 1` and `visited_path = ARRAY[node_id, e.src_node_id]`. Both steps filter active `repo_id`, `kind='calls'`, non-null destinations and confirmed/probable confidence.
   - Recursive step: join `edges e` on `e.dst_node_id = br.caller_id` where `br.depth < :max_depth` AND `NOT (e.src_node_id = ANY(br.visited_path))`.
2. Deduplicate impacted nodes by minimum hop `depth`.
3. Always count distinct unresolved calls sourced at the target or any impacted node (`unresolved_touch_count`). `include_unresolved` controls the detailed `unresolved_calls` list only; it does not change traversal, impact sets, hop depths or counts. Explain that unknown incoming callers remain unmeasurable.
4. Identify confirmed impacted entrypoints from explicit route/framework/main/CLI metadata. Return nodes with zero known callers separately as inferred roots; do not treat missing static callers as proof of a public entrypoint.
5. Return structured payload: `target_node`, `impacted_nodes_by_depth`, `affected_edges`, `impacted_entrypoints`, `unresolved_touch_count`, and `completeness_note`.

#### [MODIFY] `backend/routes/repos.py` & [NEW] `backend/routes/nodes.py`
- `POST /api/v1/repos/{id}/search` — Invokes `hybrid_graph_search()`.
- `GET /api/v1/nodes/{id}` — Returns full node details including `body_text`, callers, and callees for the right-hand Inspector drawer.
- `GET /api/v1/nodes/{id}/blast-radius` — Query params `max_depth: int = 6`, `include_unresolved: bool = False`. Invokes `compute_blast_radius()`.

---

## Phase 4: Engine 4 (Docker Chaos Sandbox) & Engine 5 (Triage & Patch Loop)

Build the isolated container runner, auto-injected `conftest.py`, 3-tier traceback classifier, and deterministic `difflib` patch verification pipeline.

#### [NEW] `backend/services/sandbox_service.py`
Implement the isolated container execution manager:
1. **`_generate_conftest_py() -> str`:**
   Returns narrow fixture/fake source for `/tmp/codescape/runs/<run_id>/conftest.py`; generate the separate globally loaded `codescape_pytest_reporter.py` alongside it:
   - Supplies narrow explicit fakes for only the external interfaces required by the harness. Do not blanket-replace third-party modules with unconstrained `MagicMock` objects; network isolation remains the primary egress control.
   - Put `pytest_collectreport`, `pytest_runtest_makereport` and `pytest_sessionfinish` hooks only in the global reporter module. Include normalized frames and phase; verify ordering and collection from both suites. Do not duplicate hooks in conftest; register a global fixture plugin explicitly if fakes must cover both locations.
2. **`run_in_sandbox(repo: Repo, run_dir: Path, run_id: int, file_overrides: dict[str, Path] | None = None) -> dict`:**
   - Configures Docker volume mounts:
     - `repo.local_path` $\rightarrow$ `/workspace/repo` (`mode="ro"`)
     - `run_dir` $\rightarrow$ `/workspace/test_run` (`mode="rw"`)
     - Any `file_overrides` (used during patch verification) mounted `"ro"` directly over `/workspace/repo/<rel_path>`.
   - Starts container with `network_mode="none"`, read-only root filesystem, bounded writable `tmpfs`, `mem_limit="256m"`, `nano_cpus=1_000_000_000`, `pids_limit=64`, file-descriptor/disk limits, `user="1000:1000"`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, and seccomp/AppArmor where supported. Mount `/tmp` as bounded tmpfs with explicit ownership, e.g. `rw,noexec,nosuid,size=64m,uid=1000,gid=1000,mode=1777`, so UID/GID 1000 can use `tempfile` and pytest cache with the root filesystem read-only. Never mount the Docker socket. Document Docker's threat-model limitations.
   - Streams container stdout/stderr lines in real time to `LogStreamBroker.publish(run_id, line)` while enforcing an **8.0-second async watchdog timeout**.
   - Run pytest with `PYTHONPATH=/workspace/repo:/workspace/test_run` and `python -m pytest -p codescape_pytest_reporter -o cache_dir=/tmp/.pytest_cache /workspace/test_run/test_chaos.py /workspace/repo/tests/`. Keep `codescape_pytest_reporter.py` in `/workspace/test_run` so `-p` imports it before collection; it must collect both test locations into `/workspace/test_run/report.json`. The cache is explicitly redirected away from the read-only repository. Read and return `/workspace/test_run/report.json` alongside timeout flag and full log text.

#### [NEW] `backend/services/triage_service.py`
Implement `execute_and_triage_chaos_run(run_id: int, db: AsyncSession)`:
1. Fetch target `Node` and its 1-hop callees.
2. Call `ai_provider.generate_chaos_test(target_node, callees)` to produce `test_chaos.py` targeting boundary conditions, empty strings, malformed hex/JSON, extreme numbers, and `None`/type-edge inputs.
3. **Tier 1 (Pre-Execution AST Syntax Check):**
   - Run `ast.parse(test_code)` on the host.
   - If `SyntaxError` is raised $\rightarrow$ set `classification = "INVALID_GENERATION"`, publish state to WebSocket, save `ChaosRun`, and return immediately without launching Docker.
4. First establish the selected baseline alone in a fresh sandbox. Write `test_chaos.py`, narrow `conftest.py`, the global reporter and any explicitly registered shared-fake plugin to the configured run directory; record artifact hashes and invoke `sandbox_service.run_in_sandbox()`. Confirm eligible findings using the reviewed contract fixture and two fresh-container reproductions. Preserve baseline failures separately.
5. **Tier 2 (Pytest Collection / Import Check):**
   - If `report.json` shows failure during `collect` or `setup` phase (e.g., `ImportError`, `ModuleNotFoundError`) $\rightarrow$ set `classification = "SETUP_FAILURE"`.
6. **Tier 3 (Failure Attribution and Evidence Assessment):**
   - If killed by watchdog $\rightarrow$ `TIMEOUT`; if all tests pass $\rightarrow$ `PASSED`.
   - Classify collection/import/fixture failures as `SETUP_FAILURE` using collection and phase reports.
   - Validate generated test call shape and assertions; classify a generated-test call mismatch as `SIGNATURE_MISMATCH` and unsupported/unexpected postconditions as `BEHAVIORAL_ANOMALY`.
   - Normalize traceback frames and map repository frames to candidate `blamed_node_id` values, but do not use frame location or order as proof.
   - Use `CONFIRMED_DEFECT` only when the test is valid, invocation is compatible, input is in-contract according to documented preconditions/behaviour (not type hints alone), failure is reproducible, and setup/mock/environment causes are excluded. Otherwise use `LOW_CONFIDENCE_DEFECT` or `BEHAVIORAL_ANOMALY`. Store the rationale and evidence in the report.

#### [NEW] `backend/services/patch_service.py`
Implement closed-loop patch drafting and container verification:
1. **`generate_patch(run_id: int, db: AsyncSession) -> Patch`:**
   - Retrieve `ChaosRun` and blamed/target `Node`.
   - Request complete replacement function code from `ai_provider.draft_function_patch()`.
   - Validate replacement function syntax with `ast.parse()`.
   - Read original source lines from `repo.local_path / node.file_path`, splice the replacement function over `[node.start_line - 1 : node.end_line]`, and generate the exact unified diff via `difflib.unified_diff(original_lines, patched_lines, fromfile=f"a/{node.file_path}", tofile=f"b/{node.file_path}")`.
   - Save and return `Patch(status="proposed", unified_diff=..., replacement_code=...)`.
2. **`verify_patch(patch_id: int, db: AsyncSession) -> Patch`:**
   - Create verification directory `/tmp/codescape/runs/verify_<patch_id>/`.
   - Revalidate the source hash/span and image digest. Write the patched full file to the safe verification overlay and copy the unchanged failing `test_chaos.py`, narrow `conftest.py`, global reporter, reviewed contract fixture and any shared-fake plugin. Record hashes and expected test IDs/counts.
   - Mount `patched_target.py` read-only over `/workspace/repo/<node.file_path>` inside a fresh `--network none` sandbox container and execute pytest over **both** `/workspace/test_run/test_chaos.py` and `/workspace/repo/tests/` using the same global `-p codescape_pytest_reporter`, `PYTHONPATH=/workspace/repo:/workspace/test_run`, and `-o cache_dir=/tmp/.pytest_cache` configuration.
   - Mark `verified` only with exit zero, complete valid reports, an executed passing chaos case and non-empty passing selected baseline, no teardown/integrity errors and host immutability evidence. Skips, missing reports or absent/failing baselines are insufficient; retain failure/infrastructure reasons and keep the patch unverified.
   - **Never modify** `./data/repos/<repo_name>` on disk.

#### [NEW] `backend/routes/runs.py` & [NEW] `backend/routes/patches.py`
- `POST /api/v1/nodes/{id}/chaos-runs` — Queues background task `execute_and_triage_chaos_run` and returns `run_id`.
- `GET /api/v1/runs/{id}` — Returns `ChaosRun` status, classification, and JSON report.
- `WS /api/v1/runs/{id}/stream` — Streams live container logs and state transitions (or replays cached logs in `--demo` mode).
- `POST /api/v1/runs/{id}/patch` — Invokes `generate_patch()`.
- `POST /api/v1/patches/{id}/verify` — Invokes `verify_patch()`.
- `GET /api/v1/patches/{id}/export` — Returns downloadable `.patch` unified diff file.

---

## Phase 5: Frontend Foundation, Decoupled Zustand Store & 3D Scene

Can begin once Phase 2 is complete. Enforces strict separation between the WebGL Canvas Track and the React/Zustand HUD Track; 60 FPS is a measured target under a defined workload, not a guarantee.

#### Initialize Frontend & Dependencies
- Vite + React 18 + TypeScript: `react-force-graph-3d`, `three`, `@types/three`, `zustand`, `@monaco-editor/react`, `dexie`, `axios`, `lucide-react`, `tailwindcss`.

#### [NEW] `frontend/src/types/codescape.ts`
- Define strict TypeScript interfaces for `GraphNode`, `GraphEdge`, `VisualNodeState` (`'IDLE' | 'FOCUSED' | 'ANALYZING' | 'TESTING' | 'CONFIRMED_DEFECT' | 'VERIFIED_FIX'`), `BlastRadiusResponse`, `ChaosRunReport`, and `PatchProposal`.

#### [NEW] `frontend/src/store/useHudStore.ts`
- Zustand state store managing:
  - Active repository, graph summary stats, selected node, inspector tab, active `BlastRadiusResponse`, active `ChaosRunReport`, and active `PatchProposal`.
  - Throttled terminal log buffer (`logLines: string[]`) that flushes incoming WebSocket log batches at most every `100ms` so high-speed pytest output never stalls the UI thread.
  - Imperative callback ref registry (`canvasControllerRef`) so HUD actions trigger 3D camera flights and material mutations **without** causing `<ForceGraphScene />` to re-render its `graphData` prop.

#### [NEW] `frontend/src/cache/graphCache.ts`
- Dexie.js IndexedDB table `snapshots` caching the last loaded `(repo_id, nodes, edges, timestamp)` so reloading the browser renders the 3D scene immediately while checking for backend updates.

#### [NEW] `frontend/src/components/Canvas/ForceGraphScene.tsx`
- Renders `<ForceGraph3D />` with a single shared `new THREE.SphereGeometry(1, 16, 16)` geometry instance scaled per node via GPU matrix transformations:
  $$\text{scale} = k \cdot \sqrt[3]{\max(1, \text{node.complexity})}$$
- Implements visual state materials (`IDLE` directory colors, `FOCUSED` $1.25\times$ white rim, `ANALYZING` cyan pulse, `TESTING` amber strobe, `CONFIRMED_DEFECT` crimson + shockwave ring, `VERIFIED_FIX` emerald glow).
- Renders resolved confirmed/probable links as solid/translucent lines. Render unresolved calls separately as source-attached dashed stubs (`THREE.LineDashedMaterial`) with deterministic display-only endpoints and expression/line tooltips; never pass null endpoints as graph links or create synthetic database nodes.
- Implements **`flyToNode(node)`** with the mandatory **Degenerate-Case Guard**:
  - Reads target $N = (x_n, y_n, z_n)$ and camera $C = (x_c, y_c, z_c)$.
  - Computes $d = \|C - N\|$. If $d < 10^{-4}$, sets $\vec{u} = (0, 0, 1)$; else $\vec{u} = \frac{C - N}{d}$.
  - Smoothly animates camera position to $P_{\text{camera}} = N + \vec{u} \times 40$ over `1200ms`.

---

## Phase 6: HUD Interactive Panels, WebSocket Telemetry & Monaco Diff Modal

Wire all five backend engines into the heads-up display.

#### [NEW] `frontend/src/services/api.ts` & `frontend/src/services/ws.ts`
- `api.ts`: Axios wrapper for `/api/v1/*` endpoints.
- `ws.ts`: WebSocket client connecting to `ws://localhost:8000/api/v1/runs/{id}/stream`, buffering incoming log lines and dispatching `VisualNodeState` changes directly to `canvasControllerRef` + `useHudStore`. Parse only the canonical `{run_id, seq, event, ts, payload}` envelope; retain `last_seen_seq`, reconnect with `?after_seq=<last_seen_seq>`, and process replayed events idempotently.

#### [NEW] `frontend/src/components/HUD/TopBar.tsx`
- Displays active repository selector (`payflow-core`), ingestion button, `DEMO MODE` status indicator badge, edge confidence legend, and the **Hybrid Graph-RAG natural-language search bar**.
- Submitting a search calls `POST /api/v1/repos/{id}/search`, highlights the anchor node + 1-hop callers/callees in 3D, invokes `flyToNode(anchor)`, and opens the Right Inspector with the AI structural summary.

#### [NEW] `frontend/src/components/HUD/LeftFileRail.tsx`
- Collapsible hierarchical directory -> file -> class -> function tree.
- Clicking any symbol flies the 3D camera to that node.
- Includes toggle switches to filter node kinds or show/hide `unresolved` dashed edges.

#### [NEW] `frontend/src/components/HUD/RightInspector.tsx`
- Displays selected symbol's `qualified_name`, `kind`, McCabe complexity badge, `route_path` badge (if entrypoint), confidence-tagged incoming callers and outgoing callees, and a read-only **Monaco Editor** displaying `node.body_text` with exact line numbers (`start_line` to `end_line`).
- Action buttons:
  1. **"Simulate Blast Radius"** $\rightarrow$ calls `GET /api/v1/nodes/{id}/blast-radius`, dims unrelated nodes in the 3D scene to translucent gray, highlights the target node in crimson and upstream callers in amber, activates backward directional particles toward impacted entrypoints (e.g., `/api/v1/stripe`), and displays the `completeness_note` (`unresolved_touch_count`).
  2. **"Run Chaos Experiment"** $\rightarrow$ calls `POST /api/v1/nodes/{id}/chaos-runs`, transitions node state to `TESTING` (amber strobe), opens the Bottom Terminal drawer, and starts WebSocket streaming.

#### [NEW] `frontend/src/components/HUD/BottomTerminal.tsx`
- Collapsible live telemetry console streaming container output from `useHudStore`.
- Displays the canonical classification banner (`INVALID_GENERATION`, `SETUP_FAILURE`, `SIGNATURE_MISMATCH`, `CONFIRMED_DEFECT`, `LOW_CONFIDENCE_DEFECT`, `BEHAVIORAL_ANOMALY`, `TIMEOUT`, `PASSED`) with candidate source location and concise evidence rationale; never present a traceback frame alone as proof.
- When `classification === 'CONFIRMED_DEFECT'`, displays **"Draft Defensive Patch"** button to trigger `POST /api/v1/runs/{id}/patch`.

#### [NEW] `frontend/src/components/HUD/DiffReviewModal.tsx`
- Opens a side-by-side **Monaco DiffEditor** comparing the original `node.body_text` (left) with the proposed `replacement_code` (right), alongside the deterministic unified diff and rationale.
- **"Verify Patch in Sandbox"** button calls `POST /api/v1/patches/{id}/verify`:
  - Runs the failing chaos test + `payflow-core` regression suite in a fresh container.
  - On success, transitions the 3D node from crimson to emerald (`VERIFIED_FIX`), displays the **"VERIFIED BY EXECUTION"** badge (showing regression suite pass count), and unlocks the **"Export `.patch`"** download button.

---

## Phase 7: `--demo` Mode Snapshot, Evaluation Harness & End-to-End Verification

Verify offline presentation reliability under the documented PostgreSQL dependency and capture the empirical evaluation metrics required by Section 8 of the concept specification.

#### [NEW] `backend/utils/seed_demo.py`
- Populates PostgreSQL with the complete pre-computed snapshot of `payflow-core`:
  - All 18 files, 54 functions, and ~112 confidence-tagged edges with pre-computed compatible 768-d embeddings; counts and source line numbers must be derived from the actual fixture rather than forced to illustrative totals.
  - Pre-recorded `ChaosRun` on `verify_signature` (`CONFIRMED_DEFECT` at `services/auth.py` line 18, `ValueError: non-hexadecimal number found in fromhex() arg`) including realistic timestamped pytest container log lines in `log_ref`.
  - Precomputed `Patch` with deterministic unified diff and stored verification report for recorded demo replay; demo search uses cached benchmark-query results and/or lexical fallback, not arbitrary live semantic embedding.
- Make seeding transactional and idempotent using unique `seed_key` values on `ChaosRun` and `Patch` with upserts. Re-running after `payflow-core` re-ingestion must resolve the new `verify_signature` node ID and recreate/rebind the recorded `ChaosRun`, `Patch` and their `run_events` history after cascade deletion; repeated runs must not create duplicate demo records. Re-ingestion is followed by `seed_demo.py` before the demo is considered ready.

#### [NEW] `backend/utils/evaluate_metrics.py`
- Automated evaluation script measuring and printing a Markdown report table for Section 8.3:
  1. Call-edge precision & recall against `payflow-core` ground truth.
  2. Unresolved-edge rate (`confirmed` vs. `probable` vs. `unresolved`).
  3. Graph-RAG top-1 and top-3 retrieval hit rate across 10 benchmark natural-language queries.
  4. Blast-radius exact-match correctness and cycle termination verification.
  5. Chaos yield and 3-tier classification accuracy.
  6. Ingestion time and search latency, measured over a documented number of warm/cold runs with repository size, hardware, model/provider mode and percentile (median/p95) recorded.

For each metric, document the ground-truth dataset, denominator, matching rule and calculation. Report measured values only; do not invent targets or imply 60 FPS is guaranteed. For rendering, record graph size, device/browser, average and percentile frame time, and whether telemetry was active.

### Mandatory End-to-End Verification Checklist (Run Before Completion)

1. **Two-Pass Ingestion & Edge Confidence Verification:** Ingest `payflow-core` $\rightarrow$ verify `nodes` and `edges` counts $\rightarrow$ confirm `services/dispatcher.py` produces an `unresolved` edge with `dst_node_id IS NULL` and `raw_callee_expr` populated $\rightarrow$ confirm dashed line appears in 3D scene.
2. **Complexity Scaling & Canvas Performance Check:** Verify high-complexity functions render as visibly larger spheres ($R \propto \sqrt[3]{M}$) using shared `SphereGeometry`; record frame-time performance for a documented graph size, browser and device during orbit and WebSocket log streaming. Treat 60 FPS as a target, not a guarantee.
3. **Graph-RAG & Degenerate Camera Flight Check:** Search *"Where is webhook signature verification implemented?"* $\rightarrow$ verify camera glides smoothly to `verify_signature`. Repeat the search to check stable navigation. Separately set camera coordinates equal to the target ($\|C - N\| < 10^{-4}$) in a controlled check and verify the guard prevents `NaN`; a normal standoff camera is 40 units away and does not exercise this guard.
4. **Blast-Radius & Cycle Guard Check:** Trigger Blast Radius on `verify_signature` $\rightarrow$ verify `verify_signature -> handle_webhook -> /api/v1/stripe` lights up amber with backward particles. Trigger Blast Radius on `utils/retry.py` (`retry_with_audit`) $\rightarrow$ verify recursive CTE terminates cleanly without infinite loop.
5. **Sandbox Isolation Check:** Trigger Chaos Run $\rightarrow$ verify container runs with `--network none` and `/workspace/repo:ro`. Writes to the repository and attempted external egress must fail or be bounded by the watchdog. Socket creation itself is not prohibited by network isolation; loopback and Unix-domain sockets can exist. Verify actual resource and writable-storage bounds on the documented host.
6. **3-Tier Triage Discrimination Check:**
   - Feed a syntax-broken test string to Tier 1 $\rightarrow$ verify `INVALID_GENERATION` without container launch.
   - Feed a wrong-argument-count generated test $\rightarrow$ verify signature validation classifies `SIGNATURE_MISMATCH` based on the incompatible invocation, not traceback path alone.
   - Run a valid test using a documented malformed-signature input $\rightarrow$ verify reproducible repository failure is classified `CONFIRMED_DEFECT` and attributed to `services/auth.py`; run a negative control with an invalid generated test to ensure it is not misclassified.
7. **Closed-Loop Patch & Host Immutability Check:** Generate patch for `verify_signature` $\rightarrow$ verify `unified_diff` has valid `difflib` headers $\rightarrow$ click "Verify Patch" $\rightarrow$ verify both the chaos test and the 4 tests in `payflow-core/tests/` pass $\rightarrow$ verify `git status` inside `./data/repos/payflow-core` shows zero modified files on disk.
8. **Offline `--demo` Mode Check:** Stop Docker daemon and unset `GEMINI_API_KEY` $\rightarrow$ start backend with `python main.py --demo` $\rightarrow$ verify 3D exploration, deterministic blast radius, cached-query replay and lexical fallback, Monaco source inspection, recorded chaos-log playback and stored patch-review flow. Verify the UI labels replay/fallback and does not imply a fresh semantic search or new sandbox verification.

---

## Phase 8 (Optional / Future Expansion Hooks — If Time Permits)

Phases 1–7 preserve extension points for the following enhancements. The intent is to limit core refactoring; schema/API changes may still be required and must use migrations and coordinated documentation updates:

1. **Air-Gapped Local AI Provider (`OllamaProvider` in `services/ai_provider.py`):** Implement the stubbed `OllamaProvider` methods using local `qwen2.5-coder` and `nomic-embed-text` (`768d`) so setting `AI_PROVIDER=ollama` in `.env` makes CodeScape 100% air-gapped.
2. **Git Snapshot Architectural Diff (`GET /api/v1/repos/{id}/diff/{other_repo_id}`):** Since `repos.commit_sha` is already stored per ingestion, compare two ingested snapshots by matching `qualified_name` across the two `repo_id`s and coloring added, removed, or complexity-increased nodes in the 3D viewport.

---

## Added verification coverage for the consistency revision

Preserve existing E2E checks and add: mixed call/import/inheritance edges; direct self-recursion and diamond paths; equal impact sets/counts under both unresolved-detail toggles; dashed stubs without target IDs; reviewed-contract versus advisory-only classification; clean-baseline gating; zero/skip/teardown/incomplete-report negative controls; reporter and shared-fixture scope across both test locations; dependency-builder compatibility and native-host mount checks; source/image/artifact identity; and the IG1 API/UI walkthrough before polish. Track these as supplementary packages in `task_tracker.md`, not as completed features.

## Documentation Change Control

`PROJECT_CONTEXT.md` is the source of truth for technical contracts. Update this plan when an architectural decision changes, then update `task_tracker.md` with the implementation and verification work, and update `README.md` to describe only the current intended/implemented behaviour. Mark unimplemented features as planned or in development. Do not silently change API paths, classification values, schema fields, model IDs or demo semantics in only one document.
