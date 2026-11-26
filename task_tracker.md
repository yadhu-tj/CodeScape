# CodeScape — Task Tracker

> **Consistency revision — 2026-11-18:** All five engines, original phases, task IDs and future-work items are retained. Technical corrections align this document with `PROJECT_CONTEXT.md`; no capability is marked implemented by this revision. Existing filenames are retained; canonical names in the proposed folder tree are future names.

> Update this file regularly during development. Status values: `[ ]` Not Started · `[~]` In Progress · `[x]` Done · `[!]` Blocked

---

## Pre-Coding Environment Checklist

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| P0 | PostgreSQL 16 + `pgvector` extension installed locally | Yadhu | `[x]` | PostgreSQL 16.15 and pgvector 0.6.0 verified in Ubuntu WSL |
| P1 | Docker Desktop / Docker Engine running locally | Yadhu | `[x]` | Docker Engine 29.1.3 installed and verified in Ubuntu-24.04 WSL; Linux containers tested. Distribution has no systemd; start dockerd directly when needed. |
| P2 | Google Gemini API key obtained (`google-genai` SDK) | Yadhu | `[x]` | **2026-11-21:** Google accepted the configured key. The summary and embedding requests passed, including the 768-value vector check. See 1.11 for reasoning status. |
| P3 | Git repository initialized | Yadhu | `[x]` | Connected to yadhu-tj/CodeScape. Bootstrap main plus focused Phase 0 feature commits; PR workflow, CI and revert guidance are documented in CONTRIBUTING.md. |
| P4 | `.gitignore` created | Yadhu | `[x]` | Exclude `.env`, `data/repos/`, `/tmp/codescape/`, `__pycache__/`, `node_modules/`, `.venv/` |
| P5 | Initial folder structure created | Yadhu | `[ ]` | Match exact tree in `PROJECT_CONTEXT.md` |
| P6 | `backend/.env` created (not committed) | Yadhu | `[ ]` | Use template from `PROJECT_CONTEXT.md` |

---

## Phase 0 — Reference Test Harness (`payflow-core`) & Sandbox Base Image
> Owner: **Yadhu** · Original dependency: Pre-Coding complete. Execution clarification: authorized Phase 0 fixture/bootstrap work uses filesystem + Docker; database/API/Git/full skeleton/.env checks remain pending prerequisites before their consuming phases.

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 0.1 | Create `backend/test_harness/payflow-core/` 18-file directory structure | Yadhu | `[x]` | `app.py`, `routes/`, `services/`, `models/`, `utils/`, `tests/` **2026-11-18:** Implemented: exactly 18 Python files and 54 explicit functions/methods, including four test functions; namespace packages avoid extra initializer files. |
| 0.2 | Implement route entrypoints (`routes/stripe.py`, `checkout.py`, `users.py`, `refunds.py`) | Yadhu | `[x]` | Explicit app/router decorators: the original `@app.post("/api/v1/stripe")` example is implemented equivalently as `@router.post("/api/v1/stripe")`; `@app.get("/health")` also exercises app decorators. **2026-11-18:** Verified: 11 application routes; sandbox HTTP smoke covers health, webhook, quote, user profile and refund branches. |
| 0.3 | Implement documented in-contract defect in `services/auth.py` (`verify_signature`) | Yadhu | `[x]` | Contract explicitly says malformed/empty string signatures must return `False`; implementation currently raises from unguarded decoding. Type hints alone are not contract evidence. **2026-11-18:** Verified: deliberate IndexError/ValueError at services/auth.py:32; three malformed cases reproduce in two fresh containers. Defect intentionally preserved. |
| 0.4 | Implement three-node/two-call-edge caller chain (`verify_signature` $\leftarrow$ `handle_webhook` $\leftarrow$ `/api/v1/stripe`) | Yadhu | `[x]` | Ground truth for Engine 3 Blast Radius **2026-11-18:** Verified: route → handle_webhook → verify_signature; selected call-site ground truth plus successful signed-webhook sandbox smoke. Parser/traversal engine verification remains Phase 2–3. |
| 0.5 | Implement `probable` edges via class methods (`self._validate()`, etc.) | Yadhu | `[x]` | Ground truth for heuristic class resolution **2026-11-18:** Implemented: CheckoutService.charge calls self._validate; baseline exercises it. Probable-edge resolution is specified in ground_truth.json and remains a Phase 2 parser check. |
| 0.6 | Implement `unresolved` dynamic registry in `services/dispatcher.py` | Yadhu | `[x]` | `handler = EVENT_REGISTRY[event_type]; handler(payload)` **2026-11-18:** Verified: handler = EVENT_REGISTRY[event_type]; handler(payload) with completed/failed handlers; successful sandbox dispatch. Actual unresolved-edge extraction/rendering remains later-phase work. |
| 0.7 | Implement deliberate mutual recursion cycle in `utils/retry.py` & `utils/audit.py` | Yadhu | `[x]` | Ground truth for PostgreSQL recursive CTE `visited_path` guard **2026-11-18:** Verified: bounded mutual call cycle and function-local import; zero/three/sixteen-budget smoke checks pass without module initialization failure. SQL cycle traversal remains Phase 3. |
| 0.8 | Write 4 passing regression unit tests in `payflow-core/tests/test_payflow.py` | Yadhu | `[x]` | Exactly four baseline tests; unpatched suite passes. Keep malformed-signature chaos case outside `tests/` in `/workspace/test_run/test_chaos.py`; patch verification runs both suites. **2026-11-18:** Verified in hardened offline Docker container: exactly four passed, zero failures/errors/skips (Python 3.11.18, pytest 8.3.5); malformed cases stay outside repository tests. |
| 0.9 | Create `backend/Dockerfile.sandbox` (`python:3.11-slim`, non-root `1000:1000`, pre-installed deps) | Yadhu | `[x]` | `PYTHONDONTWRITEBYTECODE=1`; runtime overrides `PYTHONPATH=/workspace/repo:/workspace/test_run` **2026-11-18:** Built and exercised with UID/GID 1000, read-only repo/root and writable bounded tmpfs; pinned top-level packages. Image ID and manifest hash recorded in evidence. |
| 0.10 | Create and run `backend/utils/build_sandbox.py` to build `codescape-sandbox:latest` | Yadhu | `[x]` | Verify offline execution with `--network none`; unpatched `pytest /workspace/repo/tests/` passes the four baseline tests **2026-11-18:** Verified: image built, Python/pytest version probes pass, four baseline tests pass, route/cycle smoke passes, two separate contract reproductions match expectations, source hash unchanged. |

---

## Phase 1 — Backend Foundation, Async DB Schema & `AIProvider`
> Owner: **Yadhu** · Dependency: Phase 0 complete

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 1.1 | `backend/requirements.txt` — Pin all async backend, Tree-sitter, Docker, and `google-genai` packages | Yadhu | `[x]` | Do not include legacy `google-generativeai`; include Alembic |
| 1.2 | `backend/config.py` — Pydantic `BaseSettings` loading `.env` | Yadhu | `[x]` | V1 `EMBEDDING_DIMENSIONS=768` (fixed to match `Vector(768)`); changing requires a migration; `DEMO_MODE=false` |
| 1.3 | `backend/database.py` — Async SQLAlchemy 2.0 engine (`asyncpg`), session maker and pgvector extension setup | Yadhu | `[x]` | Configure async engine/session and pgvector; Alembic is authoritative (baseline task 1.15 runs after models and before verification 1.14); validate configured vector dimensions. |
| 1.4 | `backend/models/repo.py` — `Repo` ORM model | Yadhu | `[x]` | Includes `commit_sha`, `local_path`, `image_tag` |
| 1.5 | `backend/models/node.py` — `Node` ORM model with `Vector(768)` and HNSW cosine index | Yadhu | `[x]` | Stores full `body_text` for standalone `--demo` mode |
| 1.6 | `backend/models/edge.py` — `Edge` ORM model with nullable `dst_node_id` & `raw_callee_expr` | Yadhu | `[x]` | Nullable `dst_node_id` is mandatory for `unresolved` edges |
| 1.7 | `backend/models/chaos_run.py` — `ChaosRun` ORM model | Yadhu | `[x]` | Includes `blamed_node_id`, `classification`, `report` (`JSONB`), `log_ref` |
| 1.8 | `backend/models/patch.py` — `Patch` ORM model | Yadhu | `[x]` | Stores `replacement_code`, `unified_diff`, `verification_report` |
| 1.9 | `backend/schemas/common.py` — Standard `{success, data, message}` response helpers | Yadhu | `[x]` | Used across all FastAPI endpoints |
| 1.10 | `backend/utils/redaction.py` — Secret & token scrubber before LLM calls | Yadhu | `[x]` | Regression tests cover triple-quoted secrets, truncated excerpts, and existing single-line assignments. |
| 1.11 | `backend/services/ai_provider.py` — Abstract `AIProvider` + `GeminiProvider` (`google-genai`) + `OllamaProvider` stub | Yadhu | `[~]` | Routine startup makes no live provider calls. The local reasoning and summary configuration uses `gemini-3.5-flash-lite`. Both live checks and the 768-value `gemini-embedding-2` check passed. CodeScape cancels patch-drafting calls after 30 seconds. A direct `gemini-3.8-flash` request returned text after 70.1 seconds. Structured drafts with that model still need verification. Test generation directs callers to reviewed fixtures. |
| 1.12 | `backend/services/queue_service.py` + `RunEvent` model — durable event persistence and live fan-out | Yadhu | `[x]` | Persist canonical `{run_id, seq, event, ts, payload}` events in PostgreSQL; Redis/in-memory queue are transports only; replay after `?after_seq=` **2026-11-21:** Verified 12 concurrent writes, cursor replay and local live delivery. **2026-11-26:** Redis 7.0.15 delivered a live notification across separate broker instances. PostgreSQL replay returned the same event with Redis disabled. |
| 1.13 | `backend/main.py` — FastAPI app entry, lifespan `init_db()`, CORS, `--demo` CLI flag | Yadhu | `[x]` | Restrict CORS to `http://localhost:5173`; shared `create_app(demo_mode=None)` supports `python main.py --demo` and `uvicorn main:app` via `DEMO_MODE`; CLI flag explicitly enables demo mode |
| 1.14 | Verify PostgreSQL tables, constraints and `pgvector` HNSW index | Yadhu | `[x]` | Execute only after task 1.15 baseline migration is applied; verify all six tables, constraints and indexes |

---

## Phase 2 — Engine 1: Two-Pass Tree-sitter Ingestion & Complexity
> Owner: **Yadhu** · Dependency: Phase 1 complete

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 2.1 | `ingestion_service.py` — Directory filter & git clone/copy manager (`./data/repos/`) | Yadhu | `[ ]` | Skip `.venv`, `__pycache__`, `.git`, `.env*`, secrets |
| 2.2 | `ingestion_service.py` — Pass 1 AST walker: extract `file`, `class`, and `function` symbols | Yadhu | `[ ]` | Capture exact `start_line`, `end_line`, `signature`, `docstring`, `body_text` |
| 2.3 | `ingestion_service.py` — Pass 1 decorator inspector: extract HTTP route paths (`@app.post`, `@router.get`) | Yadhu | `[ ]` | Store in `nodes.route_path` |
| 2.4 | `ingestion_service.py` — Pass 1 CodeScape McCabe-style complexity calculator | Yadhu | `[ ]` | Follow the exact construct/counting contract in `PROJECT_CONTEXT.md`; test `elif`, `async for`, Boolean operands, conditional expressions and comprehension filters; avoid double-counting. |
| 2.5 | `ingestion_service.py` — Flush Pass 1 `Node` rows and build in-memory `qualified_name -> node_id` map | Yadhu | `[ ]` | Prerequisite for cross-file Pass 2 resolution |
| 2.6 | `ingestion_service.py` — Pass 2 AST walker: resolve imports, inheritance, and call sites | Yadhu | `[ ]` | Tag `confirmed`, `probable`, or `unresolved` (`dst_node_id=None`, `raw_callee_expr`) |
| 2.7 | `ingestion_service.py` — Batched configured embedding-model vector generation (`output_dimensionality=768` for v1 schema) | Yadhu | `[ ]` | Redact excerpts before embedding; store in `nodes.embedding` |
| 2.8 | `routes/repos.py` — `POST /api/v1/repos`, `GET /api/v1/repos`, `GET /api/v1/repos/{id}/graph` | Yadhu | `[ ]` | Exclude raw 768-float array from `/graph` response for fast serialization |
| 2.9 | Ingest `payflow-core` and verify 18 files, ~54 functions, and all 3 edge confidence levels in DB | Yadhu | `[ ]` | Milestone 2 Verification |

---

## Phase 3 — Engine 2 (Hybrid Graph-RAG) & Engine 3 (Blast Radius CTE)
> Owner: **Yadhu** · Dependency: Phase 2 complete

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 3.1 | `graph_rag_service.py` — Implement live semantic query embedding and vector anchor search | Yadhu | `[ ]` | Validate non-empty query and vector dimension; separate live mode from offline replay/lexical fallback. |
| 3.2 | `graph_rag_service.py` — Stage 2: Deterministic 1-hop incoming callers & outgoing callees expansion | Yadhu | `[ ]` | Same-repository calls only; resolved destinations/confirmed-probable confidence for joins; separately count/list unresolved outgoing calls. |
| 3.3 | `graph_rag_service.py` — Stage 3: Context packaging + configured summary provider | Yadhu | `[ ]` | Return `ai_summary: null` if provider unavailable/fails; keep deterministic context and identify search mode. |
| 3.4 | `blast_radius_service.py` — Cycle-safe PostgreSQL `WITH RECURSIVE` reverse caller traversal | Yadhu | `[ ]` | Both steps filter active repo, calls only, known destinations and confirmed/probable confidence; initialize path with target + caller, exclude self-call base rows, deduplicate by minimum depth. |
| 3.5 | `blast_radius_service.py` — Group callers by hop depth; distinguish confirmed entrypoints from inferred roots | Yadhu | `[ ]` | Routes and supported main/CLI/framework entrypoints are confirmed; zero-known-caller nodes are only inferred roots. |
| 3.6 | `blast_radius_service.py` — Compute `unresolved_touch_count` & completeness note for impacted subgraph | Yadhu | `[ ]` | Always count distinct unresolved calls sourced at target or impacted callers; `include_unresolved` adds detail only and never changes impacted nodes/depths/counts. |
| 3.7 | `routes/repos.py` & `routes/nodes.py` — Wire `POST /repos/{id}/search`, `GET /nodes/{id}`, `GET /nodes/{id}/blast-radius` | Yadhu | `[ ]` | |
| 3.8 | Test Graph-RAG & Blast Radius against `payflow-core` (`verify_signature` & `retry_with_audit` cycle) | Yadhu | `[ ]` | Milestone 3 Verification |

---

## Phase 4 — Engine 4 (Docker Chaos Sandbox) & Engine 5 (Triage & Patch Loop)
> Owner: **Yadhu** · Dependency: Phase 3 complete

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 4.1 | `sandbox_service.py` — Implement structured pytest reporting and narrow external-interface fakes | Yadhu | `[ ]` | Use `pytest_collectreport` + `pytest_runtest_makereport`; globally load `codescape_pytest_reporter` via `-p`; set `PYTHONPATH=/workspace/repo:/workspace/test_run`; run both chaos and repo suites into one report; use `-o cache_dir=/tmp/.pytest_cache`; avoid blanket `sys.modules` MagicMock substitution; persist final JSON report. |
| 4.2 | `sandbox_service.py` — Implement hardened `run_in_sandbox()` with dual-volume mounts | Yadhu | `[ ]` | `--network none`, read-only root, bounded tmpfs with `uid=1000,gid=1000,mode=1777`, resource/file limits, non-root, dropped caps, no-new-privileges, seccomp/AppArmor where available; verify UID 1000 can write `/tmp` and cache. |
| 4.3 | `sandbox_service.py` — Real-time container log streaming to `LogStreamBroker` + 8.0s async watchdog kill | Yadhu | `[ ]` | |
| 4.4 | `triage_service.py` — Prompt configured reasoning model to generate boundary/malformed-input `test_chaos.py` | Yadhu | `[ ]` | |
| 4.5 | `triage_service.py` — Tier 1 pre-execution `ast.parse()` check (`INVALID_GENERATION`) | Yadhu | `[ ]` | Discard syntax errors before touching Docker |
| 4.6 | `triage_service.py` — Tier 2 pytest collection/import check (`SETUP_FAILURE`) | Yadhu | `[ ]` | |
| 4.7 | `triage_service.py` — Evidence-based failure classification and candidate source attribution | Yadhu | `[ ]` | Traceback location is evidence, not proof; validate test, call shape, documented input contract, reproducibility and environment before `CONFIRMED_DEFECT`. |
| 4.8 | `patch_service.py` — Draft complete replacement function via configured reasoning model & validate with `ast.parse()` | Yadhu | `[ ]` | Never ask LLM for raw diff hunks |
| 4.9 | `patch_service.py` — Line-range splice (`start_line`..`end_line`) + deterministic `difflib.unified_diff()` | Yadhu | `[ ]` | |
| 4.10 | `patch_service.py` — `verify_patch()` with validated read-only overlay + chaos and regression tests | Yadhu | `[ ]` | Validate symbol/signature/decorators/async form/indentation/source span; compile full module; host checkout remains untouched. |
| 4.11 | `routes/runs.py` & `routes/patches.py` — Wire chaos run, WS stream, patch draft, verify, and `.patch` export routes | Yadhu | `[ ]` | |
| 4.12 | Test full defect discovery $\rightarrow$ triage $\rightarrow$ patch $\rightarrow$ container verification on `verify_signature` | Yadhu | `[ ]` | Milestone 4 Verification |

---

## Phase 5 — Frontend Foundation, Decoupled Zustand Store & 3D Scene
> Owner: **Yadhu** · Dependency: Phase 2 complete (can run in parallel with Phases 3 & 4)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 5.1 | Initialize Vite + React 18 + TypeScript + Tailwind CSS + Lucide icons | Yadhu | `[ ]` | Install `react-force-graph-3d`, `three`, `zustand`, `@monaco-editor/react`, `dexie`, `axios` |
| 5.2 | `src/types/codescape.ts` — Shared TypeScript interfaces for nodes, edges, visual states, reports, patches | Yadhu | `[ ]` | |
| 5.3 | `src/store/useHudStore.ts` — Decoupled Zustand store with 100ms throttled log buffer & `canvasControllerRef` | Yadhu | `[ ]` | Prevents WebSocket logs from re-rendering `<ForceGraph3D />` |
| 5.4 | `src/cache/graphCache.ts` — Dexie.js IndexedDB snapshot persistence for instant reload | Yadhu | `[ ]` | |
| 5.5 | `src/components/Canvas/ForceGraphScene.tsx` — Shared `SphereGeometry(1, 16, 16)` with GPU scale $R \propto \sqrt[3]{M}$ | Yadhu | `[ ]` | Saves geometry allocation/buffer memory; separate meshes still generally incur separate draw calls. Evaluate instancing/batching only if needed; benchmark actual frame time for a documented graph size/device rather than guaranteeing 60 FPS. |
| 5.6 | `ForceGraphScene.tsx` — Visual state materials (`IDLE`, `FOCUSED`, `ANALYZING`, `TESTING`, `CONFIRMED_DEFECT`, `VERIFIED_FIX`) | Yadhu | `[ ]` | Mutate Three.js materials directly via imperative refs |
| 5.7 | `ForceGraphScene.tsx` — Edge confidence rendering (solid `confirmed`, translucent `probable`, dashed `unresolved`) | Yadhu | `[ ]` | Resolved calls are links; unresolved calls are source-attached display stubs with expression/line tooltips, no synthetic database nodes and no null graph-library targets. |
| 5.8 | `ForceGraphScene.tsx` — Camera flight (`flyToNode`) with mandatory $\lVert C - N \rVert < 10^{-4}$ degenerate-case guard | Yadhu | `[ ]` | Fallback to $\vec{u} = (0, 0, 1)$ to prevent `NaN` WebGL crash |
| 5.9 | `src/components/Canvas/ParticleEngine.ts` — Crimson shockwave rings & backward blast-radius edge particles | Yadhu | `[ ]` | |

---

## Phase 6 — HUD Interactive Panels, WebSocket Telemetry & Monaco Diff Modal
> Owner: **Yadhu** · Dependency: Phases 3, 4, and 5 complete

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 6.1 | `src/services/api.ts` & `src/services/ws.ts` — REST client and throttled WebSocket stream manager | Yadhu | `[ ]` | |
| 6.2 | `src/components/HUD/TopBar.tsx` — Repo selector, Demo badge, confidence legend, Graph-RAG search input | Yadhu | `[ ]` | Triggers search + 3D camera flight |
| 6.3 | `src/components/HUD/LeftFileRail.tsx` — Collapsible file/class/function tree + unresolved edge visibility toggle | Yadhu | `[ ]` | |
| 6.4 | `src/components/HUD/RightInspector.tsx` — Symbol metadata, complexity & route badges, read-only Monaco source view | Yadhu | `[ ]` | Includes "Simulate Blast Radius" & "Run Chaos Experiment" buttons |
| 6.5 | `RightInspector.tsx` — Blast Radius results view (hop depth tree, impacted entrypoints, `unresolved_touch_count` note) | Yadhu | `[ ]` | |
| 6.6 | `src/components/HUD/BottomTerminal.tsx` — Collapsible log console + canonical triage classification banner | Yadhu | `[ ]` | Displays all canonical outcomes and evidence rationale; unlocks patch drafting only for eligible confirmed defects. |
| 6.7 | `src/components/HUD/DiffReviewModal.tsx` — Side-by-side Monaco `DiffEditor`, "Verify Patch", and "Export `.patch`" | Yadhu | `[ ]` | Transitions node from crimson to emerald (`VERIFIED BY EXECUTION`) |
| 6.8 | `src/App.tsx` — Assemble full HUD layout over 3D WebGL viewport | Yadhu | `[ ]` | Milestone 6 Verification |

---

## Phase 7 — `--demo` Mode Snapshot, Evaluation Metrics & End-to-End Verification
> Owner: **Yadhu** · Dependency: Phase 6 complete

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 7.1 | `backend/utils/seed_demo.py` — Seed `payflow-core` graph, compatible vectors, recorded chaos run/logs and stored patch report | Yadhu | `[ ]` | Transactional/idempotent upsert using unique `seed_key` values on `chaos_runs` and `patches`; rerun after every re-ingestion to rebind newly generated node IDs and restore cascade-deleted run/patch/event history; repeated runs create no duplicates. PostgreSQL remains local dependency; no arbitrary live semantic embedding or fresh patch verification. |
| 7.2 | Wire `WS /api/v1/runs/{id}/stream` replay, `POST /api/v1/patches/{id}/verify` recorded-result flow, cached query results and deterministic lexical search | Yadhu | `[ ]` | Docker/API key not required; arbitrary live semantic embedding is not claimed; label replay vs lexical fallback; recorded patch verification is replay only. |
| 7.3 | `backend/utils/evaluate_metrics.py` — Run reproducible graph, retrieval, blast-radius, triage and latency benchmarks | Yadhu | `[ ]` | Define ground truth, denominator, matching rules, sample count, hardware/provider mode and median/p95; record measured results only. |
| 7.4 | E2E Check 1: Verify Two-Pass Ingestion & dashed `unresolved` edge rendering on `services/dispatcher.py` | Yadhu | `[ ]` | |
| 7.5 | E2E Check 2: Benchmark WebGL frame performance during live WebSocket log streaming | Yadhu | `[ ]` | Record graph size, hardware/browser, frame-time distribution and telemetry conditions; treat 60 FPS as a target, not a guarantee. |
| 7.6 | E2E Check 3: Verify repeated Graph-RAG search on same node triggers degenerate camera guard without `NaN` crash | Yadhu | `[ ]` | |
| 7.7 | E2E Check 4: Verify Blast Radius on `verify_signature` and cycle termination on `retry_with_audit` | Yadhu | `[ ]` | |
| 7.8 | E2E Check 5: Verify Docker `--network none` and `/workspace/repo:ro` immutability under chaos run | Yadhu | `[ ]` | |
| 7.9 | E2E Check 6: Verify canonical triage distinguishes invalid generation, setup, signature mismatch, confirmed/low-confidence defect, anomaly, timeout and pass | Yadhu | `[ ]` | Include negative controls; frame location alone must never produce `CONFIRMED_DEFECT`. |
| 7.10 | E2E Check 7: Verify closed-loop patch passes chaos + regression suite without modifying `./data/repos/payflow-core` | Yadhu | `[ ]` | |
| 7.11 | E2E Check 8: Verify full walkthrough in offline `--demo` mode | Yadhu | `[ ]` | Final Viva Readiness Check |

---

## Phase 8 — Optional Future Extensions (If Time Permits)
> Owner: **Yadhu** · Dependency: Phase 7 complete (100% optional, non-blocking)

| # | Task | Owner | Status | Notes |
|---|---|---|---|---|
| 8.1 | Implement `OllamaProvider` in `services/ai_provider.py` (`qwen2.5-coder` + `nomic-embed-text` @ 768d) | Yadhu | `[ ]` | Enables 100% air-gapped local execution |
| 8.2 | Implement `GET /api/v1/repos/{id}/diff/{other_repo_id}` git snapshot architectural drift comparison | Yadhu | `[ ]` | Highlights added/removed/complexity-grown nodes across commits |

---

## Task Execution Standard

The phase tables above retain the original 88 parent work packages for progress reporting. The five original cross-cutting tasks (`1.15`, `2.10`, `3.9`, `6.9`, `7.12`) and the eight additional packages listed below remain explicitly supplementary and are not folded into the parent-work-package total; therefore the historical parent total remains 88; there are now 13 separately tracked supplementary packages, for 101 original/supplementary packages including seven pre-coding entries (81 Phase 0–7 packages + 7 pre-coding + 13 supplementary). Exclude optional Phase 8 and child rows from this total. IG1 is a gate, not an additional package. The child tasks below are the actionable breakdown for work that was previously too broad; track child completion in the Notes column or a linked issue/checklist. A parent task is complete only when its child tasks and acceptance criteria pass.

For each new task, record: **Priority** (`P0` blocker / `P1` core / `P2` polish), **Estimate** (focused hours), **Status**, **Blocked by**, and **Acceptance criteria**. Estimates are planning aids, not commitments. Keep implementation and verification visible as separate work where failure risk is high.

### Expanded task breakdowns

#### 2.6 — Pass 2 reference and call resolution

| Child ID | Action | Acceptance criteria |
|---|---|---|
| 2.6.1 | Extract import statements and aliases | Absolute, relative and aliased imports are represented with source locations. |
| 2.6.2 | Resolve absolute in-repository imports | Correct module/file targets are selected; external imports are not mislabelled as internal nodes. |
| 2.6.3 | Resolve relative imports | Package-relative imports resolve correctly across nested packages. |
| 2.6.4 | Extract call expressions | Direct calls, attribute calls, subscript calls and `getattr` patterns retain raw source expressions and line numbers. |
| 2.6.5 | Resolve local and imported function calls | Unambiguous targets become `confirmed`; tests cover aliases and same-name symbols. |
| 2.6.6 | Resolve class methods and inheritance heuristically | Heuristic matches become `probable`, never silently `confirmed`; ambiguous matches remain unresolved. |
| 2.6.7 | Persist unresolved calls | `dst_node_id` is NULL, `raw_callee_expr` is populated and the edge renders as unresolved. |
| 2.6.8 | Run parser resolution tests on `payflow-core` | Ground-truth edges and all confidence levels match the fixture expectations. |

#### 4.1 — Pytest reporting and external interface fakes

| Child ID | Action | Acceptance criteria |
|---|---|---|
| 4.1.1 | Implement collection reporting | Collection/import failures appear in the final JSON report even when no test item runs. |
| 4.1.2 | Implement setup/call/teardown reporting | Each test phase and outcome is represented without duplicate/missing reports. |
| 4.1.3 | Normalize traceback frames | Paths, line numbers, function names and frame ordering are covered by fixture tests. |
| 4.1.4 | Add narrow external-interface fakes | Only required methods are faked; unexpected calls fail clearly rather than returning arbitrary MagicMocks. |
| 4.1.5 | Validate report schema | Missing report, malformed JSON and partial run are handled as explicit infrastructure outcomes. |

#### 4.2 — Sandbox hardening

| Child ID | Action | Acceptance criteria |
|---|---|---|
| 4.2.1 | Implement dual-volume mounts | Repository is read-only; run directory is writable; no host path escapes managed roots. |
| 4.2.2 | Disable network and remove ambient privileges | Network access fails; non-root user, dropped capabilities and no-new-privileges are verified. |
| 4.2.3 | Add filesystem restrictions | Read-only root filesystem and bounded writable tmpfs work with pytest. |
| 4.2.4 | Add resource limits | Memory, CPU, PIDs, file descriptors, writable storage and timeout are enforced. |
| 4.2.5 | Add optional seccomp/AppArmor profile | Profile is applied where supported; unsupported hosts report the limitation explicitly. |
| 4.2.6 | Test adversarial harness cases | Write-to-repo, network, process-spawn and resource-exhaustion attempts are blocked or bounded. |

#### 4.7 — Evidence-based triage

| Child ID | Action | Acceptance criteria |
|---|---|---|
| 4.7.1 | Define canonical classification enum | All eight classifications are shared by DB, Pydantic schemas, API, WebSocket and frontend. |
| 4.7.2 | Detect invalid generation and setup failures | Syntax errors are rejected pre-container; collection/import/fixture failures become `SETUP_FAILURE`. |
| 4.7.3 | Detect generated-test signature mismatch | Invalid invocation is attributed to the generated test and never promoted to confirmed repository defect. |
| 4.7.4 | Map repository frames to candidate symbols | `blamed_node_id` maps by normalized path and source span; ambiguous mappings are retained as ambiguous. |
| 4.7.5 | Validate input contract and test quality | Contract evidence is explicit; type hints alone are not treated as runtime validation. |
| 4.7.6 | Verify reproducibility and exclude environment artefacts | Re-run/controls support the classification; mock/setup failures cannot be labelled confirmed defects. |
| 4.7.7 | Implement confidence-aware outcome selection | `CONFIRMED_DEFECT` is reserved for sufficient evidence; uncertain cases become low-confidence/anomaly outcomes. |
| 4.7.8 | Add classification fixture suite | Each classification has at least one positive fixture and relevant negative-control fixture. |

#### 4.10 — Patch validation and verification

| Child ID | Action | Acceptance criteria |
|---|---|---|
| 4.10.1 | Validate target source revision and span | Stale or ambiguous source range is rejected before patch creation. |
| 4.10.2 | Validate replacement symbol and signature | Name, parameters, decorators and sync/async form match the intended target contract. |
| 4.10.3 | Preserve indentation and source boundaries | Class methods, decorated functions and multiline definitions remain syntactically valid. |
| 4.10.4 | Parse/compile complete patched module | Full module compiles; imports and neighbouring definitions remain intact. |
| 4.10.5 | Stage read-only patch overlay | Candidate is mounted at the correct repository-relative path in a fresh container. |
| 4.10.6 | Run chaos and regression suites | Both required suites pass and their exact results are stored. |
| 4.10.7 | Verify host immutability and export gating | Persistent checkout hash/status is unchanged; only verified candidates can be exported, with human review clearly required. |

#### 7.2 — Offline demo search and replay

| Child ID | Action | Acceptance criteria |
|---|---|---|
| 7.2.1 | Seed curated benchmark queries and results | Each replay query maps to a deterministic stored result and anchor. |
| 7.2.2 | Implement lexical fallback | Arbitrary text query can search stored symbol names/signatures/docstrings/body text without an embedding provider. |
| 7.2.3 | Label search mode in API/UI | Results clearly identify `replay`, `lexical_fallback` or `live_semantic`. |
| 7.2.4 | Replay recorded chaos and patch events | UI identifies the run as recorded; no new Docker execution is implied. |
| 7.2.5 | Verify demo without Docker/API key | Graph, deterministic blast radius, source view, search fallback and recorded walkthrough work with network disabled. |

#### 7.3 — Evaluation methodology

| Child ID | Action | Acceptance criteria |
|---|---|---|
| 7.3.1 | Define graph ground truth | Expected nodes/edges and confidence labels are stored in a reviewable fixture. |
| 7.3.2 | Define precision/recall calculations | Denominators, matching keys and treatment of unresolved edges are documented. |
| 7.3.3 | Define retrieval benchmark | Ten or more queries have expected relevant symbols and a documented top-k relevance rule. |
| 7.3.4 | Define blast-radius benchmark | Expected impacted nodes/hops/entrypoints are documented, including cycles and unresolved edges. |
| 7.3.5 | Define triage benchmark | Each classification has labelled cases and confusion-matrix reporting. |
| 7.3.6 | Measure latency reproducibly | Record repository size, hardware, provider mode, run count, median and p95. |
| 7.3.7 | Publish measured report | Report contains actual results, limitations and test environment; no unmeasured claims. |

#### Supplementary cross-cutting tasks (not included in the parent-work-package total)

| Suggested ID | Action | Acceptance criteria |
|---|---|---|
| 1.15 | Add and apply Alembic migration baseline | Execute immediately after SQLAlchemy models `1.4`–`1.8` plus `RunEvent` from `1.12` are defined and before task `1.14`; a fresh database upgrade succeeds and a subsequent schema migration is testable. **2026-11-21:** Applied revision 0001 to the fresh local database; `alembic check` found no schema changes. |
| 2.10 | Validate repository acquisition safety | Traversal, symlinks, oversized repositories and unsafe clone destinations are handled safely. |
| 3.9 | Implement search-mode routing and no-result handling | Live embedding, replay and lexical fallback are explicit; empty/low-confidence matches are handled. |
| 6.9 | Add canonical WebSocket event envelope and reconnect/replay | `queue_service.py`, `runs.py` and `ws.ts` share `{run_id, seq, event, ts, payload}`; `seq` is monotonic per run; events persist in `run_events`; `?after_seq=` replay is tested. |
| 7.12 | Benchmark rendering under a defined workload | Graph size/device/browser and frame-time results are recorded; 60 FPS is not claimed universally. |

---

## Consistency revision — additional execution packages (2026-11-18)

All original phase rows and task IDs above remain planned. These eight packages supplement the five original cross-cutting packages; no feature is removed or marked complete. Estimates are provisional focused hours, exclude waiting for services and may change after the first prototype. Each package is owned by Yadhu.

| ID | Work and acceptance criteria | Priority | Estimate | Status | Blocked by |
|---|---|---|---|---|---|
| 0.11 | Create `backend/test_harness/contracts/` reviewed fixture for `verify_signature`: source hash/symbol, contract ID/version, documentation reference, valid-input predicate, expected False result and negative controls; fixture code runs only in sandbox. Preserve exactly four passing repository baseline tests. **2026-11-18:** Verified: versioned contract manifest binds exact source and oracle SHA256, documentation, predicate and expected outcomes; two fresh-container runs each give three intended exceptions and four passing controls. Future triage engine is not marked implemented. | P0 | 3–5 h | `[x]` | 0.3, 0.8 |
| 2.11 | Separate structural ingestion from optional embedding and image preparation. Persist graph with null embeddings when provider is absent; expose labelled lexical search. Record source content hash even for non-git inputs; later verify it before patching. | P0 | 4–8 h | `[ ]` | 2.1–2.6, 2.8 |
| 3.10 | Add mixed-kind/self-cycle/mutual-cycle/diamond graph fixtures; both traversal steps and 1-hop joins use same-repo resolved calls only. Toggle changes unresolved detail list only; impacted set/minimum depths/counts are identical. Count includes target; document unknown incoming-call limitation. | P0 | 3–6 h | `[ ]` | 3.2, 3.4–3.6 |
| 4.13 | Define supported Python/pytest/Linux compatibility and explicit import roots; prove root and src-layout collection. Run selected baseline alone first. Prepare pinned reviewed dependencies in a restricted disposable builder, never target hooks on host; retain manifest hash, image digest, Python/import/test metadata and native-host Docker mount evidence. Missing/empty/wholly-skipped/failing baseline prevents verified status. | P0 | 6–12 h | `[ ]` | 0.9–0.10, 2.10, 2.11 |
| 4.14 | Own hooks once in global reporter, narrow fakes in conftest and explicit global shared-fixture plugin when needed. Test collection/setup/call/teardown reporting and fixture scope across both test locations. Reject duplicate, missing, malformed, partial, zero-test and teardown-error reports. | P0 | 4–8 h | `[ ]` | 4.1, 4.2 |
| 4.15 | Implement confirmation gates against 0.11: valid invocation/assertion/input, clean baseline, two fresh-container reproductions, setup/fake controls and evidence provenance. Advisory-only general-repository assertions remain low-confidence/anomaly; test that absent fixtures and annotations alone cannot unlock confirmation or drafting. Infrastructure failure uses failed status/null classification/error evidence; timeout remains TIMEOUT. | P0 | 6–12 h | `[ ]` | 0.11, 4.7, 4.13–4.14 |
| 4.16 | Retain pre/post test/reporter/contract hashes, expected test IDs/counts, source/image identity, host exit/timeout/log evidence and immutable-host check. Verify only executed passing chaos plus non-empty passing baseline with complete reports and no teardown/integrity error; reject skip-only/tampering/infrastructure controls and document limits of shared-process evidence. | P0 | 4–8 h | `[ ]` | 4.10, 4.13–4.15 |
| 5.10 | Implement display-only unresolved stubs without null link targets/sentinel nodes, tooltip/source selection and visibility toggle independent of counts. Record geometry sharing versus draw-call behavior; add controlled camera-equals-target check separately from repeated normal search. Benchmark navigation tasks as well as frame times. | P1 | 3–6 h | `[ ]` | 5.5, 5.7–5.8 |

The provider/privacy acceptance checks also document aggregate embedding egress: initial hosted embeddings process every included symbol chunk, potentially disclosing much of the source despite request scoping and redaction. Preserve this explanation in setup/docs; do not claim archive-free ingestion means no aggregate source disclosure.

### IG1 — early API/UI integration gate

**When:** after structural graph endpoint readiness and before declaring broad Phase 4 complete. Pull forward the minimum portions of 3.4–3.7, 4.1–4.3, 4.5–4.12, 5.1–5.3, 5.5, 5.7–5.8 and 6.1/6.4/6.6–6.8, plus the applicable supplementary contracts above. This changes execution order, not the scope or completion definition of those tasks.

**Evidence:** load local `payflow-core` → select/source-inspect a node in basic 3D → show call-only impact with unresolved completeness → execute one authored reviewed malformed-signature case in Docker → classify with baseline/reproduction controls → review an authored candidate → verify chaos plus four baseline tests in a fresh container through API/UI. Preserve source/image/test/report identities, host immutability, one invalid-test negative control and an advisory-without-contract negative control. Label authored artifacts; AI generation tasks remain pending until integrated. Defer semantic search, animation polish, Dexie caching and full replay until this gate passes; then complete every original task and final evaluation.

| Gate | Owner | Status | Acceptance |
|---|---|---|---|
| IG1 | Yadhu | `[ ]` Not Started | The API/UI workflow above passes with reviewable evidence; no unimplemented feature is labelled complete. |

## Architectural Verification Milestones (Self-Checkpoints)

| Milestone | After Task | What Must Be Proven Before Moving Forward |
|---|---|---|
| **M0: Harness Ready** | `0.10` | `payflow-core` passes `pytest` inside `codescape-sandbox:latest` with `--network none`. |
| **M1: Ingestion Proven** | `2.9` | Structural ingestion produces confirmed/probable/null-destination unresolved calls without provider access. Record static extraction latency separately from embedding/image preparation; < 3s is a target under a documented workload, not an unconditional gate. Task 2.7 additionally proves compatible 768-d vectors before live semantic search is complete. |
| **M2: Traversal Proven** | `3.8` | Blast radius on `verify_signature` traces up to `/api/v1/stripe` and terminates cleanly on `retry_with_audit` cycle. |
| **M3: Closed-Loop Proven** | `4.12` | A valid in-contract chaos test reproducibly exposes the seeded defect; triage records sufficient evidence for `CONFIRMED_DEFECT`; a validated patch passes the chaos and regression suites in a fresh container; persistent host checkout remains unchanged. |
| **M4: Viva Ready** | `7.11` | `python main.py --demo` runs graph exploration, camera flight, deterministic blast radius, cached-query replay/lexical fallback, recorded log stream and recorded patch-review flow without Docker or live AI calls; the UI clearly labels replay versus live execution. |

---

## Phase 0 completion evidence — 2026-11-18

**11/11 Phase 0 tasks complete:** original 0.1–0.10 plus supplementary 0.11. M0 is satisfied by four passing baseline tests in network-disabled Docker. See `backend/test_harness/PHASE0_VERIFICATION.md` and local `data/evidence/phase0-baseline.json` for source/image identities and results. Six host-safe tooling tests pass; target/oracle execution occurred only in containers. No application ingestion/search/traversal/triage/patch engine is marked implemented. At the original Phase 0 verification no Git repository or commit existed. Repository publication now uses a bootstrap main and focused feature commits with a PR/CI workflow; remaining pre-coding items remain visible above.

## Progress Summary

| Phase | Owner | Total Tasks | Done | Status |
|---|---|---|---|---|
| Pre-Coding | Yadhu | 7 | 5 | `[~]` In Progress |
| Phase 0 (Test Harness & Sandbox Image) | Yadhu | 10 | 10 | `[x]` Done; supplementary 0.11 also complete (11/11) |
| Phase 1 (Backend Foundation & DB Schema) | Yadhu | 14 | 13 | `[~]` In progress; supplementary 1.15 complete |
| Phase 2 (Engine 1: Two-Pass Ingestion) | Yadhu | 9 | 0 | `[ ]` Not Started |
| Phase 3 (Engine 2 & 3: Graph-RAG & Blast Radius) | Yadhu | 8 | 0 | `[ ]` Not Started |
| Phase 4 (Engine 4 & 5: Chaos Sandbox & Patch Loop) | Yadhu | 12 | 0 | `[ ]` Not Started |
| Phase 5 (Frontend 3D Canvas & Zustand Store) | Yadhu | 9 | 0 | `[ ]` Not Started |
| Phase 6 (HUD Panels, WS Telemetry & Monaco Diff) | Yadhu | 8 | 0 | `[ ]` Not Started |
| Phase 7 (`--demo` Mode, Metrics & E2E Testing) | Yadhu | 11 | 0 | `[ ]` Not Started |
| **Original Parent Work Packages (including pre-coding)** | **Yadhu** | **88** | **13** | `[~]` In Progress |
| Original supplementary packages | Yadhu | 5 | 0 | `[ ]` Not Started |
| Consistency-revision supplementary packages | Yadhu | 8 | 1 | `[~]` In Progress (0.11 complete) |
| **Original packages including supplements and pre-coding** | **Yadhu** | **101** | **14** | `[~]` In Progress |
| Phase 8 (Optional Extensions) | Yadhu | 2 | 0 | `[ ]` Optional |
