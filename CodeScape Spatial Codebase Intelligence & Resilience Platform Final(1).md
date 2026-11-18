# CodeScape: Spatial Codebase Intelligence & Resilience Platform

> **Consistency revision — 2026-11-18:** All five engines, original phases, task IDs and future-work items are retained. Technical corrections align this document with `PROJECT_CONTEXT.md`; no capability is marked implemented by this revision. Existing filenames are retained; canonical names in the proposed folder tree are future names.

Yadhu Nandhan T.J. · MCA Main Project · Concept & Architecture Document (revised v3; consistency update 2026-11-18)

## 1. Project Overview

### 1.1 The Problem

Modern codebases are too large and interconnected for any one developer to hold in their head:

- **The black-box dilemma.** Layers, services and callbacks hide the real dependency structure, so developers change a function without knowing who depends on it.
- **Fragile refactoring.** Critical legacy functions stay untouched for years because nobody can predict the cascading regressions.
- **Documentation rot.** Diagrams and READMEs describe what the system was meant to be, not what the code actually does today.
- **2D hairballs.** Node-link diagrams of real repositories collapse into unreadable tangles of crossing edges.

### 1.2 The Solution

CodeScape turns a Python repository into an explorable 3D dependency graph and builds five capabilities on top of it:

1. **Spatial comprehension.** Files, classes and functions appear as bodies in a force-directed 3D scene. Size reflects cyclomatic complexity and proximity reflects coupling.
2. **Graph-RAG search.** Ask a question in plain language and get the matching implementation together with its direct callers and callees.
3. **Blast-radius tracing.** Trace how a failure in one function propagates through multi-hop callers using graph traversal, not LLM guesswork.
4. **Sandboxed chaos testing.** Generate boundary-condition and malformed-input tests for a chosen function and run them in an ephemeral, network-isolated Docker container.
5. **Triage and verified patching.** Separate genuine defects from bad generated tests, propose a defensive patch, review it in a diff editor, and verify it by execution before anything is exported.

### 1.3 Scope of v1

In scope:

- Python repositories only (Tree-sitter Python grammar, pytest-based chaos tests).
- One predefined chaos workflow per selected function.
- Single-user deployment on one machine with Docker installed.
- A cloud-hosted LLM and embedding provider, accessed through a provider interface (see Section 2.2).
- Human in the loop: patches are proposed and verified, never applied to the repository automatically.

Out of scope for v1 (see Section 9): other languages, runtime tracing, CI integration, multi-user support, and a fully air-gapped mode.

### 1.4 Clarified v1 implementation contracts

- **Call-only analysis:** Caller/callee expansion, inferred roots and reverse blast radius use same-repository `kind='calls'` edges with known destinations and confirmed/probable confidence. Imports and inheritance remain separate stored relationships. Impact paths indicate potential dependencies, not guaranteed runtime failure propagation.
- **Unresolved calls:** `include_unresolved` controls detailed reporting only. Always return `unresolved_touch_count` and `completeness_note`, counting distinct unresolved calls sourced at the target or impacted callers. Toggling details never changes the impacted set. Render null-destination calls as source-attached dashed display stubs with expression/line tooltips; no sentinel database nodes or null graph-library targets.
- **Supported execution:** Initial live testing supports Python 3.11-compatible, Linux-compatible pytest projects with configured import roots, a prepared pinned dependency image and a non-empty passing baseline. Static inspection does not import target code. A `src/` layout requires an explicit import root and collection fixture. Common preinstalled packages support the showcase rather than every repository.
- **Preparation and portability:** Dependency installation/build hooks run only in a separate restricted disposable builder using reviewed manifests; never execute them on the host or expose host credentials/Docker sockets. Record source/manifest hashes, image digest, Python version, import roots and baseline IDs/counts in run evidence. Resolve native Windows host paths through configured roots and verify Docker Desktop mounts; `/tmp` paths are Linux/WSL examples.
- **Confirmation oracle:** Automatic `CONFIRMED_DEFECT` requires a reviewed executable fixture in `backend/test_harness/contracts/`, keyed by source hash and qualified symbol, with contract ID/version, documentation reference, input predicate, expected outcome and negative controls. Store compatibility/assertion checks, two fresh-container reproductions and passing baseline/setup controls. General-repository generated assertions without such fixtures remain low-confidence/advisory and require review; type hints and LLM judgments cannot confirm a defect.
- **Reporter ownership:** `conftest.py` provides narrow fakes; `codescape_pytest_reporter.py`, globally loaded with `-p`, owns all collection/phase/final-report hooks exactly once. Shared fakes across the two test locations need an explicitly registered global fixture plugin; sibling conftest fixtures do not apply automatically.
- **Verification evidence:** Require exit zero, complete valid phase reports, an actually executed passing chaos case and a non-empty passing selected regression suite, with no teardown/integrity failures. Preserve test/reporter/contract hashes, expected test IDs/counts and host-observed outcomes. Shared-process reports are not tamper-proof. Infrastructure failures use run `status='failed'`, `classification=NULL` and `report.infrastructure_error`; watchdog expiry remains `TIMEOUT`. A missing, empty, wholly skipped or failing baseline cannot support verified status.
- **Rendering:** Shared sphere geometry saves allocation/buffer memory; separate meshes still generally incur separate draw calls. Instancing/batching may reduce draw calls if measurements justify it. Keep complexity scaling and measure frame time, draw calls and navigation usability before claiming superior performance or 3D usability.
- **Terminology:** “Chaos experiment” remains the UI label for generated boundary-condition/malformed-input testing. Distributed fault injection is future work.

### 1.5 Delivery order and evidence

Retain all milestones, with an early **IG1** integration gate after structural ingestion: basic 3D/source inspection → call-only impact → one reviewed malformed-signature contract case → sandbox classification → reviewed patch → fresh-container chaos plus four-baseline verification through API/UI. Pull minimum portions of later phases forward; authored tests/candidates prove wiring first, while AI generation remains pending until integrated. Final replay, benchmarks, real-repository evaluation and UI polish still have their own completion requirements.

## 2. Design Principles

```
┌──────────────────────────────────────────────────────────────────────┐
│                      CODESCAPE DESIGN TENETS                         │
├──────────────────────────────────────────────────────────────────────┤
│ 1. Deterministic analysis first, generative AI second                │
│    Parsers and graph queries build the map; the LLM only proposes    │
│    tests and patches.                                                │
├──────────────────────────────────────────────────────────────────────┤
│ 2. Local-first, minimal egress                                       │
│    Analysis, storage and execution stay on the host; only small      │
│    code excerpts reach the LLM provider.                             │
├──────────────────────────────────────────────────────────────────────┤
│ 3. Spatial depth for exploration                                     │
│    A third dimension separates clusters and makes large graphs       │
│    navigable.                                                        │
├──────────────────────────────────────────────────────────────────────┤
│ 4. Empirical verification over speculation                           │
│    Defects and patches are assessed through bounded test evidence    │
│    in an isolated container, with explicit review and limits.         │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.1 Parsers Over Hallucinations

Many “AI for code” tools paste files into an LLM and ask what calls a function or what a change will break. That fails for three reasons: context windows are finite, LLMs invent imports and miss re-assignments, and they cannot guarantee coverage of an entire repository.

CodeScape inverts the hierarchy. Symbols, call sites and complexity scores come from Tree-sitter syntax trees and graph queries. The LLM is reserved for summarization, chaos-test parameter ideas, and patch drafting.

**What “deterministic” means here.** Tree-sitter gives accurate syntax, not full semantic resolution. Python’s dynamic features (`getattr`, callbacks, decorators, dynamic dispatch) cannot always be resolved statically. So CodeScape tags every call edge with a confidence level, and its analyses are deterministic *over the extracted graph*: the same repository always yields the same graph and the same traversal results, and the limits of the analysis are shown rather than hidden.

| Confidence | Meaning | Example |
| --- | --- | --- |
| Confirmed | Callee resolves to exactly one in-repo definition via local scope or an import | `verify_signature(sig)` after `from services.auth import verify_signature` |
| Probable | Resolved by heuristic, such as `self.method()` inside a class or a method name defined once in the repo | `self._validate(payload)` |
| Unresolved | Cannot be resolved statically: callbacks, registries, `getattr`, dynamic dispatch, unresolved imports | `handler = registry[name]; handler(x)` |

Blast radius and Graph-RAG expansion traverse confirmed and probable edges by default. Unresolved edges are drawn dashed, counted, and reported with every result (for example, “3 unresolved call sites touch this subgraph”), so users know what the analysis could not see.

### 2.2 Local-First Design and Data Egress

CodeScape v1 is **local-first, not air-gapped**. Parsing, graph storage, vector storage and test execution all run on the host. The LLM and embedding calls go to a hosted provider, so some code excerpts leave the machine. The design minimizes and documents what leaves:

| Component | Where it runs | What leaves the machine |
| --- | --- | --- |
| Tree-sitter ingestion, complexity scoring | Local | Nothing |
| PostgreSQL + pgvector (graph and vectors) | Local | Nothing |
| Docker chaos sandbox | Local, `--network none` | Nothing |
| Embedding generation (v1) | Hosted provider | Function-level text chunks |
| Test planner, patch suggester, summaries (v1) | Hosted provider | The target function, its 1-hop context, and the failing traceback |

Safeguards: repositories are not uploaded as a single archive or whole-repository prompt; ingestion skips `.env` files and common secret patterns, and excerpts are redacted before egress. Initial hosted embedding processes all included function/class chunks, so cumulatively it may send much of the included source. Function scoping limits each request, not aggregate disclosure; local embeddings remain future work.

The LLM and embedding layers sit behind a provider interface. A fully air-gapped deployment, with a local open-weights model and local embeddings in place of the hosted provider, is the planned next version (Section 9).

### 2.3 Why 3D Instead of 2D

Kuratowski’s theorem says non-planar graphs cannot be drawn in two dimensions without edge crossings, and real dependency graphs are routinely non-planar. Every graph, however, can be embedded in three dimensions without any crossings.

The screen is still a 2D projection, so edges can overlap visually from a fixed viewpoint. The practical benefits of 3D are therefore:

- The layout has an extra degree of freedom, so the force-directed engine can separate unrelated clusters into different depth planes instead of stacking them.
- The user can orbit and zoom to resolve occlusion, which a static 2D diagram cannot offer.
- Camera flights, dimming and highlighting keep large graphs navigable.

The cost is occlusion and harder navigation. CodeScape addresses this with automatic camera flight to search results, dimming of uninvolved nodes during analysis, and a file-tree rail for orientation.

## 3. System Architecture

### 3.1 Technology Stack

| Layer | Technology | Role |
| --- | --- | --- |
| Frontend | React + TypeScript | HUD, panels, routing |
| 3D rendering | Three.js via react-force-graph-3d | Force-directed scene |
| UI state | Zustand | Buffered telemetry and inspector state |
| Code viewing | Monaco Editor | Source view and side-by-side diffs |
| Client cache | Dexie.js (IndexedDB) | Caches the last loaded graph snapshot for fast reload |
| Backend | FastAPI | REST endpoints and WebSocket streaming |
| Parsing | Tree-sitter (Python grammar) | Symbols, call sites, complexity |
| Database | PostgreSQL + pgvector | Graph as adjacency tables, embeddings, runs, patches |
| Queue and pub/sub | Redis, with a zero-dependency in-memory `asyncio.Queue` fallback | Chaos-run jobs and live log fan-out to WebSockets. The fallback keeps standalone local workstation execution free of any external message-broker daemon; Redis is used when available |
| Execution | Docker workers | Sandboxed pytest runs |
| AI | Hosted LLM and embedding provider behind an interface | Summaries, test planning, patch drafts |

### 3.2 The Five Engines

```
┌───────────────────┬──────────────────────────────────────────────────────┐
│ 1. Ingestion      │ Recursive parsing, complexity scoring, and           │
│                   │ confidence-tagged dependency edges.                  │
├───────────────────┼──────────────────────────────────────────────────────┤
│ 2. Graph-RAG      │ Vector search anchored to one symbol, expanded by    │
│                   │ 1-hop structural context, plus camera flight.        │
├───────────────────┼──────────────────────────────────────────────────────┤
│ 3. Blast Radius   │ Deterministic reverse traversal of call edges to     │
│                   │ find impacted callers and entrypoints.               │
├───────────────────┼──────────────────────────────────────────────────────┤
│ 4. Chaos Sandbox  │ Isolated Docker execution: no network, read-only     │
│                   │ source, resource limits, mocked external services.   │
├───────────────────┼──────────────────────────────────────────────────────┤
│ 5. Triage & Loop  │ Traceback-based classification, then patch           │
│                   │ verification by execution.                           │
└───────────────────┴──────────────────────────────────────────────────────┘
```

### 3.3 Demo Mode

Starting the platform with `--demo` loads a pre-computed snapshot from the database: the graph, one cached chaos run with its streamed logs, and one cached patch with its verification result. Because each node stores its full source `body_text` alongside its line range (Section 5.1), Monaco code inspection and diff review work from the database snapshot alone, even if the cloned repository is no longer on disk. This mode needs neither the Docker daemon nor an LLM connection. It exists so the 3D exploration, camera flights, blast radius and diff review can be shown reliably when the presentation environment is restricted or offline.

## 4. The Five Engines in Detail

### Engine 1: Ingestion and Static Modeling

**Directory filtering.** Before parsing, the target directory passes an ignore filter that skips virtual environments (`.venv`), caches (`__pycache__`), build outputs, version-control directories and secret-bearing files. Only the author’s own code is mapped, so third-party packages cannot exhaust resources.

**Symbol extraction.** Tree-sitter parses each file into a syntax tree from which the engine extracts:

- Classes and modules, including inheritance.
- Functions and methods: signature, type hints, decorators, docstring, and exact start and end lines.
- Decorators, including route registrations such as `@app.post("/api/v1/stripe")` or `@router.post(...)`, so the exposed route path is stored alongside the function and entrypoints can be labelled with their HTTP route in the blast-radius view.
- Call sites, each resolved to a callee where possible and tagged confirmed, probable or unresolved (Section 2.1).

**Two-pass resolution.** Tree-sitter parses one file at a time, so a call site in `routes/stripe.py` cannot be linked to `verify_signature`'s node while `services/auth.py` has not been parsed yet. Ingestion therefore runs in two strict passes:

1. **Pass 1 — Definitions.** Parse every file, extract symbols, compute McCabe complexity, and insert all file, class and function rows into `nodes`, building an in-memory map of `qualified_name -> node_id`.
2. **Pass 2 — References.** Re-walk the parsed syntax trees, resolve imports and call sites against Pass 1's map, assign confidence (confirmed, probable, unresolved), and bulk-insert the resulting rows into `edges`.

This ordering makes supported cross-file resolution independent of file enumeration order and keeps edge insertion bulk-oriented. It does not guarantee resolution of every Python call: shadowing, reassignment and dynamic behavior can remain unresolved.

**Complexity mapping.** For every function the engine computes McCabe cyclomatic complexity:

```
M = 1 + (number of decision points)
```

CodeScape's McCabe-style decision points are `if`, `elif` counted once, `for`, `async for`, `while`, each `except` handler, each additional Boolean operand (`and`/`or`), conditional expressions and comprehension filters. `match`/`case` is excluded until separately specified and tested. The exact definition in `PROJECT_CONTEXT.md` governs; parity with another tool is not assumed. In the 3D scene a function’s sphere volume is proportional to M (so its radius scales with the cube root of M). A five-line utility is a small pearl; a nested payment router is a heavy sphere, which makes hotspots visible at a glance.

### Engine 2: Hybrid Graph-RAG and Spatial Navigation

Plain RAG returns disconnected text chunks with no sense of where they sit in the software. CodeScape adds structure:

```
User natural-language query
        │
        ▼
[Stage 1: Semantic anchor]
 Embed the query; find the most similar symbol by cosine similarity
 (symbols embedded at function level: signature + docstring + body).
        │
        ▼
[Stage 2: 1-hop structural expansion]
 Deterministically fetch direct callers and callees from the graph.
        │
        ▼
[Stage 3: Context packaging and synthesis]
 Bundle function code + callers + callees into one context for the LLM.
        │
        ▼
[Stage 4: Camera flight]
 Fly the 3D viewport to the target node and open the inspector.
```

**Camera standoff.** To avoid clipping into the node mesh, the engine reads the target’s live position N and the current camera position C, computes the unit vector u from N toward C, and places the camera at:

```
P_camera = N + u × D        (D = standoff distance)
```

The camera glides along this path with an ease-out curve, keeping the node centered while the inspector drawer opens.

**Degenerate-case guard.** If the user triggers a search for a node the camera is already centered on, `‖C − N‖ = 0` and the unit-vector computation divides by zero, injecting NaN coordinates into Three.js and blanking the WebGL canvas. The engine therefore checks the norm before dividing: if `‖C − N‖ < 10⁻⁴` (camera already at the target), it falls back to a default directional vector `u = (0, 0, 1)` and simply performs the standoff pull-back along that axis.

### Engine 3: Deterministic Blast-Radius Traversal

The question this engine answers: *if this function breaks or changes its contract, what else is affected?* It does so without an LLM, by traversing call edges backward from the target to its callers.

```
             [TARGET: verify_token]
                      ▲
                      │ direct caller (depth 1)
              [get_current_user]
                ▲           ▲
  (depth 2)     │           │     (depth 2)
        [/checkout/charge]  [/user/profile]
```

**Traversal rules**

- **Reverse direction.** Follow only same-repository `kind='calls'` edges from callee to caller. Imports and inheritance remain separate architectural relationships; static reachability indicates potential impact rather than inevitable runtime failure.
- **Cycle safety.** Real code has circular imports and mutual recursion. The traversal is a PostgreSQL recursive query that carries a path array and stops a branch when a node reappears, with a configurable depth limit as a second guard.
- **Edge confidence.** Traverse confirmed/probable calls with known destinations only. `include_unresolved` adds unresolved-call reporting details; null destinations cannot be traversed and the toggle never changes impacted nodes or counts.
- **Output.** Deduplicate potential impacted callers by minimum hop depth. Return detected route/framework/main/CLI entrypoints separately from zero-known-caller inferred roots. Always count distinct unresolved calls sourced at the target or impacted callers and return a completeness note; unknown incoming callers cannot be measured this way. Render unresolved calls as source-attached dashed display stubs without synthetic graph nodes.

**Visual behavior.** Uninvolved modules dim to translucent gray, the target glows red, impacted callers glow amber, and particles flow backward along the edges to show the fault spreading toward public-facing routes.

### Engine 4: Isolated Containerized Chaos Sandbox

Running auto-generated code on a developer’s machine is unsafe, so every experiment runs in a container using a dual-volume pattern:

```
HOST                                        DOCKER CONTAINER
┌─────────────────────────────┐             ┌──────────────────────────────────┐
│ Cloned repo                 │             │                                  │
│ ./data/repos/<repo>         │─(mount :ro)─► /workspace/repo   (READ-ONLY)    │
└─────────────────────────────┘             │                                  │
┌─────────────────────────────┐             │                                  │
│ Ephemeral run directory     │             │                                  │
│ /tmp/codescape/runs/<id>/   │─(mount :rw)─► /workspace/test_run (READ-WRITE) │
│   ├── test_chaos.py         │             │   ├── test_chaos.py              │
│   └── report.json           │◄─(writes)───┴── report.json                    │
└─────────────────────────────┘             └──────────────────────────────────┘
```

**Isolation contract**

1. **Source immutability.** The repository is mounted read-only, so destructive writes are rejected by the kernel. `PYTHONDONTWRITEBYTECODE=1` prevents Python from trying to write bytecode into it.
2. **Ephemeral workspace.** The generated test and the structured report live in a disposable read-write run directory.
3. **Network quarantine.** The container runs with `--network none`, preventing external network access. This does not ban every socket operation: loopback and Unix-domain sockets may still exist. Verify external egress denial rather than asserting socket creation always fails.
4. **Resource and privilege limits.** Memory ceiling (for example 256 MB), a one-CPU quota (not processor affinity), non-root user (`--user 1000:1000`), `--cap-drop ALL`, `--security-opt no-new-privileges`, a process limit, and a host-side watchdog that kills the run after 8 seconds.
5. **Dependencies.** Runtime network is disabled, so supported projects use a prepared image built separately under the reviewed-manifest/restricted-builder policy in Section 1.4. Never execute target install/build code on the host. Store the image digest and dependency manifest hash; missing packages are setup failures. The showcase image is prepared in advance; inspection does not require executing preparation.
6. **Injected fixtures and global reporting plugin.** Run from `/workspace/test_run` with `PYTHONPATH=/workspace/repo:/workspace/test_run`. The backend writes narrow fakes into `conftest.py` and reporting hooks into `codescape_pytest_reporter.py`.
   - **External-interface fakes.** Explicit adapters cover required `requests`, `httpx`, `boto3`, `stripe` and `psycopg2` interfaces in the showcase. Avoid blanket module substitution through `sys.modules` or generic `MagicMock`; missing/incompatible dependencies remain setup failures. Shared fakes for repository tests require an explicitly registered global fixture plugin because the sibling generated conftest does not cover them automatically.
   - **Structured JSON evidence.** The global reporter captures collection via `pytest_collectreport`, setup/call/teardown via `pytest_runtest_makereport`, and final JSON via `pytest_sessionfinish`. Normalize frame paths/lines/order and validate against fixtures; frame origin identifies candidates rather than proving fault. Invoke `python -m pytest -p codescape_pytest_reporter -o cache_dir=/tmp/.pytest_cache /workspace/test_run/test_chaos.py /workspace/repo/tests/` to produce one `/workspace/test_run/report.json` for both locations. Keep hooks out of conftest to avoid duplicates.
7. **Persistent repository storage.** Cloned repositories live in a persistent application directory (`./data/repos/`), not `/tmp`, which is wiped on reboot on Linux and WSL. Only the ephemeral run directories (`/tmp/codescape/runs/<id>/`) are disposable by design.

### Engine 5: Failure Triage and Closed-Loop Verification

Naive tools fall into the **exit-code trap**: a failing test is assumed to mean a bug found. In practice a generated test may have bad syntax, wrong argument counts or missing imports. CodeScape classifies every run through three tiers:

```
Generated chaos test
        │
        ▼
[Tier 1: Pre-execution syntax check]
 Parse the test locally. Syntax error? ──► INVALID_GENERATION (discarded)
        │
        ▼
[Tier 2: Pytest lifecycle]
 Collection or import failure?          ──► SETUP_FAILURE (environment issue)
        │
        ▼
[Tier 3: Evidence assessment]
 Normalize frames to candidate symbols; origin alone proves no defect:
  ├─ incompatible generated invocation ──► SIGNATURE_MISMATCH
  ├─ reviewed contract + all evidence gates pass ──► CONFIRMED_DEFECT
  ├─ repository implicated, evidence incomplete ──► LOW_CONFIDENCE_DEFECT
  ├─ unsupported postcondition/expectation ──► BEHAVIORAL_ANOMALY
  ├─ host watchdog exceeded ──► TIMEOUT
  └─ complete executed suite passes ──► PASSED
 Missing/inconsistent infrastructure evidence: failed run, classification null.
```

**Refinements that make the classification trustworthy**

- **First-party frame rule.** Verify traceback ordering, then map relevant first-party frames to candidate symbols. A third-party exception may involve repository misuse, invalid generated input or setup; preserve those alternatives until contract and control evidence supports attribution. Frame origin alone establishes neither a defect nor a signature mismatch.
- **Attribution to the right function.** The repo frame’s file and line are mapped to a graph node through the stored line ranges. If the node is a callee of the target rather than the target itself, the defect is attributed to that callee and the target is marked as affected.
- **Contract check.** Type hints describe intended types but do not establish runtime behavior or valid malformed-input handling. Automatic confirmation requires the reviewed executable contract fixture, a compatible valid test, passing baseline/setup controls and two fresh-container reproductions on the same source/image. Without that oracle, preserve a low-confidence/advisory finding for review.
- **Postcondition oracle for `BEHAVIORAL_ANOMALY`.** Generic checks such as exception behavior or annotation-compatible returns, and LLM/docstring-derived assertions, are advisory unless a reviewed contract supports them. Expected exceptions can be valid behavior. Do not promote a speculative assertion into a confirmed defect; preserve its provenance and review status.

**Closed-loop patch verification**

1. **Patch drafting.** The patch suggester receives the target function, the exact crashing input, the failing line and the traceback, and returns a **complete replacement function block** containing guard clauses or boundary checks. The backend splices this block into the source file in Python using the node's stored `start_line` and `end_line`, then generates the unified diff deterministically with `difflib.unified_diff`. The LLM is never asked to emit hunk headers (`@@ -14,7 +14,9 @@`) itself, because LLMs are unreliable at calculating exact line numbers, and a malformed hunk makes `git apply` or `patch` fail.
2. **Visual review.** Monaco’s diff editor shows the original on the left and the proposal on the right.
3. **Verification run.** An ephemeral container re-runs the failing test with the patched file mounted read-only over the original path, with the rest of the repository unchanged. It also runs the selected non-empty, previously passing repository baseline suite. A missing, empty, wholly skipped or failing baseline prevents verified status in v1; retain the compatibility/evidence limitation.
4. **Outcome.** Require exit zero, complete valid phase reports, an executed passing chaos case and non-empty passing selected baseline, no teardown/integrity errors, unchanged original source and retained environment/test evidence. Then the node turns crimson to emerald with “VERIFIED BY EXECUTION”; otherwise the proposal stays unverified.

The repository on disk is never modified by verification. “Verified” means the reproduced failure is fixed and no existing test regressed; it does not claim the function is correct in general.

## 5. Data Model and API

### 5.1 Proposed Schema

| Table | Key columns | Purpose |
| --- | --- | --- |
| `repos` | id, name, source\_url, commit\_sha, ingested\_at, image\_tag, local\_path | Ingested repositories, their clone location under `./data/repos/`, and their prebuilt sandbox image |
| `nodes` | id, repo\_id, kind (file, class, function), qualified\_name, file\_path, start\_line, end\_line, signature, docstring, route\_path, complexity, body\_text, embedding (vector(768)) | Graph vertices; `body_text` stores the full source of the symbol so code inspection and `--demo` mode work standalone from the database snapshot |
| `edges` | id, repo\_id, src\_node\_id, dst\_node\_id (nullable), kind (calls, imports, inherits), confidence (confirmed, probable, unresolved), call\_site\_line, raw\_callee\_expr | Graph edges; see nullable-destination note below |
| `chaos_runs` | id, repo\_id, node\_id, blamed\_node\_id, status, classification, test\_code, report (JSONB), log\_ref, seed\_key, started\_at, finished\_at | One row per experiment with contract/reproduction/environment evidence; nullable unique seed_key supports idempotent demo seeding. |
| `patches` | id, run\_id, node\_id, replacement\_code, unified\_diff, rationale, status (proposed, verifying, verified, failed), verification\_report (JSONB), created\_at, verified\_at, seed\_key | Patch proposals and bounded verification evidence; `unified_diff` is generated deterministically with `difflib.unified_diff` (Section 4, Engine 5). Earlier conceptual names `diff` and `verification_run_id` are superseded by these canonical fields. |
| `run_events` | id, run\_id, seq, event, ts, payload (JSONB) | Durable per-run WebSocket replay with unique (run_id, seq); Redis/in-memory fan-out is not replay storage. |

**Nullable edge destination.** An unresolved call site such as `handler(x)` does not resolve to any definition in `nodes`, so `dst_node_id` is **nullable** and the raw callee expression is preserved in `raw_callee_expr` (TEXT). This keeps unresolved edges first-class rows that can be counted, dashed in the scene, and reported in completeness notes, rather than being dropped or forced through a foreign-key violation. A sentinel `UNRESOLVED_TARGET` node per file was considered and rejected in favour of the nullable column, so unresolved counts cannot be confused with real nodes during traversal.

Indexes: `edges(dst_node_id)` for fast reverse traversal, and a pgvector index on `nodes.embedding`.

### 5.2 API Contract

All listed routes use the `/api/v1` prefix and the standard `{success, data, message}` REST envelope. `PROJECT_CONTEXT.md` defines the full six-table DDL. WebSocket events use `{run_id, seq, event, ts, payload}` with UTC timestamps, durable `run_events` persistence and `?after_seq=` replay/deduplication. The omitted list/detail routes are included below.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/repos` | Clone and ingest a repository |
| GET | `/repos` | List ingested repositories |
| GET | `/nodes/{id}` | Retrieve full symbol details and source |
| GET | `/repos/{id}/graph` | Nodes and edges for the 3D scene |
| POST | `/repos/{id}/search` | Graph-RAG query; returns anchor node, callers, callees and summary |
| GET | `/nodes/{id}/blast-radius` | Potential impacted callers (`max_depth=6`); `include_unresolved=false` adds reporting details when true, never unknown traversal |
| POST | `/nodes/{id}/chaos-runs` | Queue a chaos experiment |
| WS | `/runs/{id}/stream` | Live container logs and state changes |
| GET | `/runs/{id}` | Classification and report |
| POST | `/runs/{id}/patch` | Generate a patch proposal |
| POST | `/patches/{id}/verify` | Run patch verification |
| GET | `/patches/{id}/export` | Download the verified diff |

## 6. User Experience and HUD

CodeScape is a heads-up display layered over a real-time WebGL canvas.

```
┌────────────────────────────────────────────────────────────────────────┐
│ [Logo]  [ Active repo: payflow-core ]      [ Semantic Graph-RAG search ] │  Top bar
├────────────────┬──────────────────────────────────────────────┬──────────────┤
│ File tree &    │                                           │ Symbol       │
│ structure      │      3D force-directed graph              │ inspector    │
│ (collapsible   │      (Three.js canvas)                    │ (collapsible │
│  left rail)    │                                           │  right rail) │
├────────────────┴──────────────────────────────────────────────┴──────────────┤
│ [▲ Terminal]  Live telemetry drawer: container logs, diffs, timeline      │  Bottom drawer
└───────────────────────────────────────────────────────────────────────┘
```

### 6.1 Decoupled State Management

In force-directed graphs, pushing streaming data into top-level React state restarts the physics simulation and scatters the layout. CodeScape separates two tracks:

- **Canvas track.** The 3D scene runs its own render loop and is updated through mutable references. Color changes, glow pulses and particle flows are applied directly to Three.js materials, causing no React re-renders.
- **HUD track.** WebSocket telemetry, terminal output and inspector state go through an isolated Zustand store with buffered, throttled updates, so the terminal can show hundreds of log lines per second while the graph stays steady.

### 6.2 Visual State Machine

| State | Node presentation | Canvas and HUD reaction |
| --- | --- | --- |
| `IDLE` | Color by directory or module | Nodes settle into architectural clusters |
| `FOCUSED` | Scaled 1.25× with a white rim glow | Camera glides to standoff position; inspector shows code and metrics |
| `ANALYZING` | Cyan with a slow pulse | Upstream links light up; Graph-RAG assembles context |
| `TESTING` | Amber with a fast strobe | Bottom drawer opens and streams container logs |
| `CONFIRMED_DEFECT` | Deep crimson with shockwave rings | Callers light up amber; backward particles show the failure ripple |
| `VERIFIED_FIX` | Crimson fading to emerald | Diff modal shows “VERIFIED BY EXECUTION”; export unlocks |

Edge rendering follows confidence: confirmed edges are solid, probable edges are lighter, and unresolved edges are dashed.

### 6.3 Scale Target

v1 targets repositories of up to a few hundred files. Larger repositories are handled by collapsing directories into single nodes until expanded. The real limit will be measured in the evaluation (Section 8).

## 7. End-to-End Walkthrough

The scenario runs against the showcase repository `payflow-core`, a curated repository that contains a deliberately seeded defect. The figures below are illustrative and should be replaced with measured values from the finished build.

```
[Step 1: Ingestion]
  User loads payflow-core.
  Tree-sitter maps 18 files, 54 functions, 112 edges in 1.4 seconds.
  Each edge is tagged confirmed, probable or unresolved.
  High-complexity functions render as larger spheres.

[Step 2: Semantic exploration]
  Query: “Where is webhook signature verification implemented?”
  Graph-RAG anchors on verify_signature in services/auth.py.
  The camera glides to the node and the inspector opens with the
  source, complexity score and callers.

[Step 3: Blast radius]
  User clicks “Simulate Blast Radius”.
  Reverse traversal finds the impacted chain:
    verify_signature (Auth) -> handle_webhook (Listener) -> /api/v1/stripe (Route)
  Unrelated modules dim; the three dependents glow amber.
  Completeness note: 0 unresolved call sites in this subgraph
  (the repo's event dispatcher does render as a dashed unresolved
  edge elsewhere, proving that channel works too).

[Step 4: Chaos experiment]
  User clicks “Run Chaos Experiment”.
  The planner notes unvalidated string slicing in verify_signature and
  generates tests with empty and malformed hex payloads.
  A container starts with --network none and a read-only repo mount.

[Step 5: Triage]
  The run fails with: ValueError: non-hexadecimal digit found.
  The innermost first-party frame is /workspace/repo/services/auth.py, line 18,
  which maps to the target node.
  A reviewed contract requires malformed strings to return False. A clean
  baseline, valid invocation/assertion, two fresh-container reproductions
  and setup/fake controls support CONFIRMED_DEFECT. The node turns crimson.

[Step 6: Patch and proof]
  The patch suggester adds a guard clause rejecting malformed payloads.
  The Monaco diff shows the change side by side.
  User clicks “Verify Patch”.
  A fresh container re-runs the failing test and the repo’s existing tests
  with the patched file mounted read-only.
  Everything passes; the node turns emerald and the diff shows
  “VERIFIED BY EXECUTION”.
```

## 8. Evaluation Plan

### 8.1 Evaluation Corpus

- **Showcase repository (`payflow-core`).** A curated repository written for the demonstration, with known structure and a seeded defect. It gives exact ground truth, which makes metrics such as edge precision and blast-radius correctness measurable. Because it is controlled, it is a staged demonstration and is presented as one.
- **Generalization repositories.** Two small, real open-source Python projects, to be selected. They show the platform works outside the curated case and give honest unresolved-edge and false-positive numbers.

### 8.2 Showcase Repository Test Harness (`payflow-core`)

`payflow-core` is not written casually: it is a designed test harness whose 18-file, 54-function structure deliberately triggers every capability in this specification. If the harness does not exercise an engine, that engine has nothing to show during evaluation. The harness therefore guarantees:

- **All three edge confidence levels.** The codebase includes standard imports (confirmed), `self.method()` calls (probable), and at least one dictionary-based event/webhook dispatcher (`handler = EVENT_REGISTRY[event_type]; handler(payload)`) so Engine 1 actually extracts unresolved edges and the scene renders dashed edges with real completeness counts.
- **A deliberate cycle.** A mutual recursion or circular helper call between two utility functions proves that the PostgreSQL recursive query's path-array cycle guard terminates instead of looping forever.
- **Honest type hints and an explicit contract on the seeded defect.** Keep `verify_signature(payload: str, sig: str) -> bool`, and document that malformed/empty signature strings are valid external inputs that must return `False`. A reviewed executable fixture in `backend/test_harness/contracts/` supplies that oracle and negative controls. Type hints alone cannot justify `CONFIRMED_DEFECT`; all confirmation gates still apply.
- **An existing regression suite.** `tests/test_payflow.py` contains exactly four passing baseline happy-path tests on the unpatched snapshot. Keep the malformed-signature chaos case separately in `/workspace/test_run/test_chaos.py`. Verification runs both; the evidence establishes that these selected tests passed, not that every regression is absent. The earlier 3–5-test estimate is fixed at four for reproducible acceptance.

### 8.3 Metrics

| Metric | How it is measured | Result |
| --- | --- | --- |
| Call-edge precision and recall | Extracted edges compared with hand-labelled ground truth on `payflow-core` and a sample from each real repository | To be recorded |
| Unresolved-edge rate | Share of call sites tagged unresolved, per repository | To be recorded |
| Retrieval hit rate | A set of natural-language queries with known targets; share where the target is ranked first or in the top three | To be recorded |
| Blast-radius correctness | Exact match against hand-computed impact sets on `payflow-core` | To be recorded |
| Chaos yield | Confirmed defects found per set of runs; share of generated tests discarded as invalid | To be recorded |
| Classification false-positive rate | Share of `CONFIRMED_DEFECT` results that a human reviewer judges not to be real defects | To be recorded |
| Verified-fix rate | Share of proposed patches that pass verification | To be recorded |
| Performance | Ingestion time, search latency and rendering frame rate at each repository’s node count | To be recorded |

## 9. Limitations and Future Work

### 9.1 Known Limitations

- Static call resolution in Python is incomplete, which is why edges carry confidence and unresolved edges are reported.
- LLM output is non-deterministic, so generated tests and patches can differ between runs. Demo mode caches one run for repeatability.
- v1 sends code excerpts to a hosted LLM provider and is not air-gapped.
- v1 supports Python only, and its mocking covers a fixed set of common libraries.
- “Verified” means the reproduced failure is fixed and existing tests pass; it does not prove general correctness.

### 9.2 Future Work

- **Air-gapped mode.** Swap the provider interface to a local open-weights model (for example through Ollama) and local embeddings, with pre-pulled Docker images, for deployments where code cannot leave the machine.
- **More languages** through additional Tree-sitter grammars.
- **Runtime trace overlay** to resolve edges that static analysis cannot.
- **Git snapshot diff** to show architectural drift between commits.
- **CI integration** to run blast-radius checks on pull requests.
- **Scalability work** for repositories beyond a few hundred files.

## 10. Development Milestones

0. **Reference test harness (`payflow-core`).** Build and commit the curated showcase repository first (Section 8.2): all three edge confidence levels, a deliberate call cycle, honest type hints on the seeded defect, and a `tests/` regression suite. Ingestion, blast-radius traversal and sandbox verification cannot be written or tested without the target codebase on disk, so the harness is a prerequisite, not an afterthought — this milestone links the evaluation methodology in Section 8 directly to the development timeline.
1. **Repository intelligence.** Ingestion, symbol extraction, complexity scoring, confidence-tagged call edges.
2. **Graph-RAG.** Embeddings, pgvector search, 1-hop structural expansion.
3. **3D explorer.** Scene, HUD, camera flight, inspector.
4. **Testing engine.** Docker sandbox, test generation, three-tier triage.
5. **Live telemetry and AI analysis.** WebSocket log streaming, LLM summaries, patch suggestion and verification.
6. **Advanced features.** Polish blast-radius visualization already exercised by IG1. Git snapshot diff remains Phase 8 optional future work, outside core v1.

**Phase 0 implementation evidence (2026-11-18):** The showcase now contains exactly 18 Python files and 54 explicit functions/methods including four baseline tests. The image built in Ubuntu WSL; all four baseline tests and HTTP/dispatcher/bounded-cycle smoke checks pass in hardened network-disabled containers. Two fresh oracle runs each reproduce three intentional malformed-signature exceptions with four passing controls. Source hashes remain unchanged. See `backend/test_harness/PHASE0_VERIFICATION.md`; later engines and IG1 remain planned. Illustrative source-line references in future demo descriptions must be resolved from the actual source/traceback (the seeded decode currently occurs at `services/auth.py:32`).

## 11. Viva Defense Guide

### 1. Why 3D instead of a 2D flowchart?

Real dependency graphs are usually non-planar, so any 2D drawing must have crossing edges (Kuratowski). In 3D every graph can be drawn without crossings, but the screen is still a 2D projection, so the real gain is practical: the layout engine gets a depth axis to separate clusters, and the user can orbit to resolve occlusion. I offset the cost, harder navigation, with camera flight, dimming and a file-tree rail.

### 2. Why not let an LLM analyze the whole codebase?

Context limits, hallucinated imports and no coverage guarantee. I use Tree-sitter and graph queries for the structure, so the same repository always gives the same graph and traversal results. The LLM only drafts test ideas, summaries and patches.

### 3. Is the analysis really deterministic? Python is dynamic.

It is deterministic over the extracted graph, not over every possible runtime behavior. Every call edge is tagged confirmed, probable or unresolved, unresolved edges are drawn dashed and counted, and each result reports how many unresolved call sites touch it. Measured edge precision and recall are in Section 8.

### 4. How do you stop AI-generated tests from producing false positives?

I combine syntax checks, pytest lifecycle reports and normalized candidate source frames with a reviewed contract fixture, a passing baseline, invocation/assertion validation, two fresh-container reproductions and setup/fake controls. Type hints and frame origin cannot prove a defect. Without the reviewed oracle, findings stay low-confidence or advisory for review. False-positive rates remain to be measured and reported with negative controls.

### 5. You stress IP security, yet you use a cloud LLM. How is that consistent?

v1 is local-first, not air-gapped. Parsing, storage and execution are local, and the sandbox has no network. Generation/synthesis sends redacted scoped context (target, direct caller/callee context and traceback); hosted ingestion embeddings process all included symbol chunks and can cumulatively disclose much of the included source. No repository archive is uploaded, but chunking is not an aggregate privacy guarantee. The LLM sits behind a provider interface so a local model can replace it in the air-gapped version, which is documented future work.

### 6. Is the demonstration rigged?

The showcase repository is curated with a seeded defect, and I say so. It is used because it gives exact ground truth for measuring accuracy. To show generalization I also run the platform on real open-source projects and report their unresolved-edge and false-positive rates.

### 7. What if the LLM’s patch is wrong or breaks something?

Nothing touches the repository on disk. A patch is verified in a fresh container by re-running the failing test and the repository’s existing tests. If anything fails, the proposal stays unverified. Even a verified patch only claims the reproduced failure is fixed and no existing test regressed.

### 8. Why not use dynamic runtime tracing (Py-Spy, eBPF, cProfile) to map dependencies instead of static AST parsing?

Runtime tracing only observes code paths actively triggered by existing test suites or live traffic. Cold legacy functions, unconfigured endpoints and unexercised error-handling blocks remain invisible to such traces. Static Tree-sitter parsing can inspect declared symbols in included, parseable source without executing those paths. Filtering, syntax errors, generated code and unsupported constructs still limit coverage; unresolved calls and parsing limitations are reported rather than hidden.

### 9. How does the 3D scene maintain 60 FPS when a high-complexity function has a massive visual radius?

Complexity scales visual volume via radius R ∝ ∛M with shared `SphereGeometry(1, 16, 16)` buffers. Scaling an existing mesh does not add triangles or draw calls, but adding separate node meshes generally does add draw calls. Geometry sharing saves allocation/memory; instancing/batching may reduce draw calls if needed. Record graph size, hardware/browser and frame-time/draw-call measurements; 60 FPS is a target, not an established result.

### 10. What happens if Docker or the network fails during the presentation?

Demo mode (`--demo`) loads a pre-computed snapshot with the graph, a cached chaos run and a cached patch verification. Because node bodies are stored in the database, code inspection and diff review also work without the cloned repository on disk. It needs neither Docker nor an LLM connection, but local PostgreSQL must be running and seeded. The 3D exploration, camera flights, call-only blast radius and diff review still work. Search is labelled curated-query replay or lexical fallback; recorded verification is historical evidence. Reseed transactionally after re-ingestion using unique seed keys and newly resolved node IDs.

## 12. Summary of Capabilities

| Dimension | Traditional approach | CodeScape |
| --- | --- | --- |
| Architecture mapping | Static diagrams and wikis that go stale | Automated 3D graph derived from the code |
| Search and discovery | `grep` or flat vector search | Hybrid Graph-RAG: semantic match plus 1-hop structural context |
| Impact analysis | Manual tracing and guesswork | Deterministic multi-hop traversal over a confidence-tagged graph, with cycle protection |
| Resilience testing | Hand-written unit tests for anticipated cases | Generated boundary-condition tests run in an isolated sandbox |
| Security and isolation | Running generated code on the host, or sending whole repositories to cloud tools | Local analysis and execution, no-network sandbox, minimal-excerpt LLM calls, air-gapped mode planned |
| Patch validation | Accepting AI suggestions on trust | Candidate assessed by re-running the failing test and selected baseline before reviewed export; bounded evidence is retained |
