# Phase 2: Flow Engine & Stabilize

> **Status**: Steps 7–8b ✅ | Steps 9a–9b ✅ | Step 9c ✅ | Steps 10–14 pending
> **Goal**: Agents use tools; the flow engine orchestrates atoms and subflows, whitelisting which tools agents can use at each pipeline step. MVP individual steps become composable. Agent has topology awareness. Ready for external use.

---

## Step 7: Topology Graph ✅

> **Goal**: In-memory dependency graph from `context.yaml` files. Foundation for impact analysis and context-enriched prompts. Language-agnostic code analysis framework for auto-generating missing `context.yaml`.

- [x] `src/specweaver/context/analyzers.py` — `LanguageAnalyzer` ABC, `PythonAnalyzer`, `AnalyzerFactory`
  - [x] Language detection, purpose extraction (docstring), import extraction (AST), public symbol extraction, archetype inference
  - [x] Strategy + Factory pattern — extensible for Java, Kotlin, Rust, TS, C++, SQL
- [x] `src/specweaver/context/inferrer.py` — `ContextInferrer`
  - [x] Auto-generates `context.yaml` for dirs missing one (with `AUTO-GENERATED` header + warnings)
  - [x] Level inference from parent, graceful skip for empty dirs / existing files
- [x] `src/specweaver/graph/topology.py` — `TopologyNode`, `OperationalMetadata`, `TopologyGraph`
  - [x] `TopologyGraph.from_project(root)` — scan for `context.yaml`, parse, build adjacency lists
  - [x] `consumers_of(module)` — direct reverse lookup
  - [x] `dependencies_of(module)` — transitive forward traversal
  - [x] `impact_of(module)` — transitive reverse traversal
  - [x] `cycles()` — Tarjan's SCC detection (including self-loops)
  - [x] `constraints_for(module)` — aggregated constraints from module + consumers
  - [x] `operational_warnings(module)` — SLA mismatch detection (latency-critical ↔ batch, max_latency_ms)
  - [x] `auto_infer=True` integration with `ContextInferrer`
- [x] Tests (76 total):
  - [x] `tests/unit/context/test_analyzers.py` — 26 tests
  - [x] `tests/unit/context/test_inferrer.py` — 15 tests
  - [x] `tests/unit/graph/test_topology.py` — 35 tests
- [x] Test restructure: `tests/unit/` reorganized to mirror `src/specweaver/` packages

**Estimated effort**: 1 session. ✅ Completed.

---

## Cross-Cutting Concerns

> These are not discrete steps but architectural decisions that apply across Steps 8–14.

### Concurrency Readiness

**Current state** (after Step 7): partially prepared.

| Ready to parallelize | Needs work before parallelizing |
|---|---|
| Validation rules (stateless pure functions) | `ContextInferrer.infer_and_write()` — check-then-write race condition |
| TopologyGraph queries (immutable after build) | `TopologyGraph.from_project(auto_infer=True)` — reads + writes during scan |
| LLM calls (stateless per call, I/O-bound) | All I/O is synchronous — no `async/await` anywhere yet |

**Plan**: Introduce `async/await` in the flow engine (Step 11). The LLM adapter, file I/O, and subprocess calls become async. Independent pipeline steps run concurrently via `asyncio.gather()`. File writes use atomic-write patterns or `filelock`. No fundamental redesign required.

### SQLite as Central Config Store

**Decision**: All configuration lives in a SQLite database at `~/.specweaver/specweaver.db` — **outside any project directory**. This prevents agents from modifying their own guardrails.

| Data | Storage | Rationale |
|---|---|---|
| Project registry | **SQLite** (Step 8a) | Multi-project support, `sw use <project>` |
| Per-project config (LLM, thresholds) | **SQLite** (Step 8a) | Not in project dir — agents can't touch it |
| Validation rule overrides | **SQLite** (Step 8b) | Per-project thresholds, enable/disable |
| `context.yaml` files | Co-located YAML | Structural metadata, agent-readable (not writable) |
| Flow/pipeline definitions | YAML templates | Declarative, reviewable, shareable |
| Pipeline execution state, audit log | **SQLite** (Step 11) | Transactional, supports resume, rollback |
| Topology/analysis cache | **SQLite** (Step 11) | Computed data, can rebuild, fast queries |
| Domain brain | **Qdrant** (Phase 5) | Vector search, graph queries |

SQLite runs in WAL mode for concurrency. Single `~/.specweaver/specweaver.db` file. Zero external dependencies (ships with Python).

**Project directory changes**: `.specweaver/` in the project becomes a **marker only** — no config files inside. The project is identified in the DB by its registered name.

```
~/.specweaver/                         ← SpecWeaver home (global, outside projects)
    specweaver.db                      ← SQLite: projects, config, rules, state

/projects/my-app/                      ← actual project
    .specweaver/                       ← marker directory (empty, signals "managed project")
    context.yaml                       ← boundary defs (structural, readable by agents)
    src/...
```

### Project Identity & Switching

- **Project name as ID**: unique, enforced at registration. Format: `^[a-z0-9][a-z0-9_-]*$`
- **`sw use <project>`**: switch active project. If name unknown → interactive setup dialog
- **Active project**: tracked in DB (last-used project auto-selected on CLI start)

---

## Step 8a: Project Registry & Config Store ✅

> **Goal**: SQLite database at `~/.specweaver/` for multi-project management.

- [x] `src/specweaver/config/database.py` — SQLite setup + schema (projects, llm_profiles, project_llm_links, active_state, schema_version tables)
- [x] `src/specweaver/config/settings.py` — rewrite to read from DB (register, get_active, remove, update, migration)
- [x] CLI commands: `sw init`, `sw use`, `sw projects`, `sw remove`, `sw update`, `sw scan`
- [x] Tests: DB creation, project CRUD, name validation, LLM profiles, active project, CLI (1034 tests)

**Completed**: March 2026.

---

## Step 8b: Per-Rule Validation Configuration ✅

> **Goal**: Configurable thresholds per validation rule, stored in the project config DB.

- [x] `validation_overrides` table in `database.py` — CRUD + cascade
- [x] `src/specweaver/config/settings.py` — `RuleOverride`, `ValidationSettings` Pydantic models
- [x] `src/specweaver/validation/runner.py` — accept `ValidationSettings`, apply overrides
- [x] 7 rules updated to accept constructor overrides: S01, S03, S04, S05, S07, S08, S11, C04
- [x] CLI: `sw config set/get/list/reset`, `--strict`, `--set` CLI overrides
- [x] Tests: 88 tests covering override application, disabled rules, edge cases
- [x] **1128 tests passing, 0 regressions**

**Completed**: March 2026.

---

## Step 9: Context-Enriched Prompts ✅

> **Goal**: All LLM-calling commands (`sw draft`, `sw review`, `sw implement`) use structured, token-aware, topology-enriched prompts via a shared `PromptBuilder`.

**Design decisions** (brainstormed 2026-03-14):

| # | Decision |
|---|---|
| 1 | `PromptBuilder` owns full prompt including instructions (commands pass instruction text) |
| 2 | All 3 LLM commands use `PromptBuilder` (draft, review, implement) |
| 3 | `context_limit` added to `llm_profiles` table (schema v2 migration) |
| 4 | Hybrid truncation: priority-ordered + proportional redistribution. Instructions = priority 0 (never truncated) |
| 5 | Strategy pattern for topology context selection — ABC + concrete selectors, extensible |
| 6 | Store token counts per-file (quick win for analytics / status) |

### 9a: Token Budget Awareness ✅ _(inspired by PasteMax)_
- [x] `llm/adapter.py` — `count_tokens()` (abstract) + `estimate_tokens()` (default `len // 4`)
- [x] `llm/gemini_adapter.py` — `count_tokens()` via native `client.models.count_tokens()`
- [x] `llm/models.py` — `TokenBudget` dataclass (used/limit/remaining, warn at >80%)
- [x] Schema migration v1→v2: add `context_limit` column (default 128000)
- [x] Tests: token counting, estimate fallback, budget tracking, schema migration (+16 tests)

### 9b: Structured Prompt Formatting ✅ _(inspired by PasteMax)_
- [x] `src/specweaver/llm/prompt_builder.py` — `PromptBuilder` class
  - [x] `.add_file(path, priority)` / `.add_context(text, label, priority)` — flexible content API
  - [x] `.add_instructions(text)` — priority 0, never truncated
  - [x] `.build()` — assembles XML-tagged prompt (`<instructions>`, `<file_contents>`, `<context>`)
  - [x] Per-file language detection via `detect_language()`
  - [x] Hybrid truncation: priority-ordered + proportional redistribution on underflow
- [x] Refactor: `reviewer.py`, `drafter.py`, `generator.py` all use `PromptBuilder`
- [x] Tests: prompt assembly, truncation, tag structure, language detection (+49 tests)

### 9c: Topology Context Injection + Context Selectors ✅
- [x] `src/specweaver/graph/selectors.py` — **Strategy pattern** for context selection
  - [x] `ContextSelector` ABC — `select(graph, target) -> set[str]`
  - [x] `DirectNeighborSelector` — direct consumers + deps only (default for `sw draft`)
  - [x] `NHopConstraintSelector(depth=2)` — N-hop UNION constraint-sharing modules (default for `sw review`)
  - [x] `ConstraintOnlySelector` — constraint violations only (for `sw check --selector constraint`)
  - [x] `ImpactWeightedSelector` — 2-hop neighbours + transitive impact set
- [x] `graph/topology.py` — `neighbors_within()`, `modules_sharing_constraints()`, `format_context_summary()`
- [x] `prompt_builder.py` — `.add_reminder(text)`, `.add_topology(contexts)`, `.add_file(..., role=)`
- [x] `prompt_builder.py` — trust signals: `role="reference"` / `role="target"` in `<file>` tags
- [x] `prompt_builder.py` — automatic dynamic budget scaling (content < 25% → 1.5x topology room, > 75% → 0.5x)
- [x] `cli.py` — wired topology + selectors into `draft`, `review`, `implement`
  - [x] `_select_topology_contexts()` helper centralizes selector lookup → module wiring
  - [x] `--selector` flag on all 3 commands (choices: direct, nhop, constraint, impact)
  - [x] Default selectors: draft→direct, review→nhop, implement→direct
  - [x] Graceful fallback: no `context.yaml` → proceed without topology (no error)
- [x] Tests: 28 tests across `test_topology_injection.py` + `test_topology_wiring.py` + `test_selectors.py`
- [x] **Runnable**: `sw review spec.md` loads topology context via selector and passes to LLM prompt
- [x] **1340 tests passing, 0 regressions**

**Depends on**: Step 7 (Topology Graph) for 9c only. 9a and 9b are independent.

**Estimated effort**: 2.5 sessions (9a: 0.5, 9b: 1, 9c: 1). ✅ Completed 2026-03-14.

---

## Step 10: Flow Engine — Pipeline Models & Definition Format

> **Goal**: Define what a pipeline IS — YAML schema, step types, parameter model. No execution yet, just the data model and parsing.

- [ ] `src/specweaver/flow/models.py` — pipeline data model
  - [ ] `PipelineDefinition` — name, description, list of `PipelineStep`
  - [ ] `PipelineStep` — step type enum (validate_spec, draft, review_spec, implement, validate_code, review_code), parameters, gates
  - [ ] `GateDefinition` — gate type (auto, hitl), condition (pass/warn/fail), on_fail action
  - [ ] `PipelineState` — lifecycle position per spec (pending → drafted → validated → reviewed → implemented ...)
- [ ] `src/specweaver/flow/parser.py` — load pipeline YAML, validate against schema, return `PipelineDefinition`
- [ ] Bundled pipeline templates:
  - [ ] `new_feature.yaml` — draft → check spec → review spec → implement → check code → review code
  - [ ] `validate_only.yaml` — check spec (simple, no LLM)
- [ ] Tests: parsing valid/invalid YAML, model validation, step enum coverage
- [ ] **Runnable**: `PipelineDefinition.from_yaml("new_feature.yaml")` returns a valid model

**Estimated effort**: 1–2 sessions.

---

## Step 11: Flow Engine — Runner & State Tracking

> **Goal**: Execute a pipeline step-by-step. Track where each spec is in the lifecycle. Persist state so interrupted runs can resume. Introduce async execution and SQLite state persistence.

- [ ] `src/specweaver/flow/runner.py` — `PipelineRunner`
  - [ ] Accept `PipelineDefinition` + project context
  - [ ] **Async execution**: `async def run_step()` — LLM calls, file I/O, subprocess via `asyncio`
  - [ ] Execute steps sequentially by default, `asyncio.gather()` for independent steps
  - [ ] Map step types to existing modules (validate → `runner.run_rules`, draft → `Drafter.draft`, etc.)
  - [ ] Track `PipelineState` per spec
  - [ ] **Context overflow recovery** _(inspired by Aider)_ — if prompt exceeds model context window, auto-truncate via `PromptBuilder` and retry
- [ ] `src/specweaver/flow/state.py` — **SQLite** state persistence (`.specweaver/state.db`)
  - [ ] Tables: `pipeline_runs`, `step_results`, `audit_log`
  - [ ] WAL mode for concurrent read/write
  - [ ] Save/load state, support resume from last completed step
  - [ ] Atomic transitions (no half-written state on crash)
- [ ] `src/specweaver/llm/adapter.py` — `async def generate()` (backward-compatible sync wrapper)
  - [ ] **Message sanity checking** _(inspired by Aider)_ — validate role alternation before API calls
- [ ] Tests: runner with mock steps, state save/load, resume from checkpoint, concurrent step execution
- [ ] **Runnable**: Pipeline runs end-to-end programmatically (not yet via CLI)

**Depends on**: Step 10 (Pipeline Models).

**Estimated effort**: 2–3 sessions.

---

## Step 12: Flow Engine — Gates, Retry & Feedback Loops

> **Goal**: Configurable gates (auto-pass, HITL approval), retry on failure, feedback loops (re-draft after failed review).

- [ ] `src/specweaver/flow/gates.py` — gate implementations (auto, HITL, validation)
- [ ] `src/specweaver/flow/runner.py` — extend with gate + retry logic
  - [ ] On gate failure: retry step, escalate, or abort (configurable)
  - [ ] Feedback loop: e.g., review DENIED → re-run draft with review findings injected
  - [ ] Max retry count per step
  - [ ] **Lint-fix reflection loop** _(inspired by Aider)_ — run linter/tests → feed errors back to LLM → re-generate, with `max_reflections` cap
- [ ] Tests: gate logic, retry counts, feedback injection, abort conditions
- [ ] **Runnable**: Pipeline pauses at HITL gates, retries failed steps, auto-fixes lint errors

**Depends on**: Step 11 (Runner).

**Estimated effort**: 1–2 sessions.

---

## Step 13: CLI Polish & Error Handling

> **Goal**: `sw run` command to invoke pipelines from CLI. Proper error handling, colored progress, `--verbose` / `--json` output modes.

- [ ] `sw run` CLI command — load pipeline YAML, run through `PipelineRunner`
  - [ ] `sw run new_feature my_module`, `sw run --resume`
  - [ ] `--verbose` and `--json` flags
- [ ] Progress indicators: Rich spinners/progress bars during LLM calls
- [ ] Error handling: graceful LLM failures, network retries, clear messages
- [ ] Tests: CLI integration tests, error scenarios
- [ ] **Runnable**: `sw run new_feature greet_service` runs the full pipeline

**Depends on**: Steps 11-12 (Flow Engine Runner + Gates).

**Estimated effort**: 1–2 sessions.

---

## Step 14: Documentation & Phase 2 Milestone

> **Goal**: README, quick-start guide, `sw --help` for all commands. Test coverage audit.

- [ ] `README.md` — installation, quick-start, command reference
- [ ] `sw --help` and per-command help text audit
- [ ] Quick-start guide: from `sw init` to a completed pipeline run
- [ ] Test coverage audit: ensure 70–90% across all modules
- [ ] Gap-fill: any under-tested modules from Steps 7-13
- [ ] **Milestone**: Pipelines are configurable and reusable. Agent has topology awareness. Someone else could install and use SpecWeaver.

**Depends on**: All preceding Phase 2 steps.

**Estimated effort**: 1 session.
