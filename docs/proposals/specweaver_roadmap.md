# SpecWeaver Roadmap

> **Date**: 2026-03-08
> **Status**: ACTIVE
> **Context**: Step-by-step plan for SpecWeaver development. Fresh start from scratch, informed by [flowManager](https://github.com/sbula/flowManager) learnings. MVP-first approach: prove the concept, then expand feature by feature.

> [!IMPORTANT]
> **The Core Principle**: MVP first → Prove it works → Isolate & implement features one by one → Full functionality.
> Every phase must produce something *runnable*. No phase is "just spec work."

---

## Current State (updated 2026-03-14)

**What exists:**
- ✅ Repo: `sbula/specweaver` — fresh, clean
- ✅ Documentation: MVP feature definition, methodology, architecture, lifecycle layers
- ✅ Decision log: Python, Typer CLI, Gemini API, deployment isolation
- ✅ Project scaffold: `pyproject.toml`, CLI shell, `sw init`
- ✅ Loom layer: Filesystem tools, atoms, and interfaces (**183 tests**, fully linted + type-checked)
- ✅ Validation engine: 19 rules (S01-S11, C01-C08), configurable thresholds, per-project overrides
- ✅ LLM adapter: Gemini API adapter with interface abstraction
- ✅ Spec drafting: Interactive `sw draft` with HITL context
- ✅ Spec/Code review: LLM-powered `sw review` with ACCEPTED/DENIED verdicts
- ✅ Code generation: `sw implement` generates code + tests from spec
- ✅ Topology graph: In-memory dep graph, impact analysis, cycle detection, auto-infer
- ✅ Project registry: SQLite config store, multi-project, `sw use/projects/remove/update`
- ✅ Validation config: `sw config set/get/list/reset`, `--strict`, `--set` CLI overrides

**Phase 1 (MVP)**: Steps 1–5 ✅ | Step 6 ⏸ (deferred)
**Phase 2 (Flow Engine)**: Steps 7–8b ✅ | Step 9a ✅ | Steps 9b–14 pending

**What we're building next** (see [mvp_feature_definition.md](mvp_feature_definition.md)):
- Step 9: Token budgeting, PromptBuilder, topology context injection
- Steps 10–14: Flow engine (pipeline models, executor, audit, HITL gates)

---

## Phase 1: MVP — Prove the Concept

> **Goal**: A runnable CLI that demonstrates the Core Loop end-to-end. Static validation works. LLM integration works (at least for one feature). You can `sw validate spec` a real spec and get real results.

### Step 1: Project Scaffold + CLI Shell

> **Goal**: `sw --help` works. Project structure is real.

- [x] `pyproject.toml` with Typer dependency
- [x] `src/specweaver/__init__.py`, `cli.py` — F1: CLI entry point with subcommands (stubs)
- [x] `src/specweaver/config/settings.py` — project path resolution (`--project` / `SW_PROJECT`)
- [x] `src/specweaver/project/scaffold.py` — `sw init` creates `.specweaver/` in target
- [x] Tests: CLI dispatch, settings resolution, scaffold creation
- [x] **Runnable**: `sw init --project ./test-project` creates the directory structure

**Estimated effort**: 1–2 sessions. ✅ Largely completed.

---

### Step 1b: Loom — Filesystem Tools & Atoms ✅ COMPLETED

> **Goal**: Agents and Engine have secure, role-gated filesystem access. Agents see only whitelisted boundaries.

- [x] `loom/commons/filesystem/executor.py` — `FileExecutor` + `EngineFileExecutor` (path traversal, symlinks, protected patterns, atomic writes)
- [x] `loom/tools/filesystem/tool.py` — `FileSystemTool` with role-intent gating, `FolderGrant` boundary enforcement, `../` security fix
- [x] `loom/tools/filesystem/interfaces.py` — 3 role interfaces + factory
- [x] `loom/atoms/filesystem/atom.py` — 5 intents: scaffold, backup, restore, aggregate_context, validate_boundaries
- [x] `context.yaml` boundary manifests for filesystem modules
- [x] 183 tests (780 total passing), ruff + mypy clean
- [x] **Security audited**: `../` bypass, backslash normalization, trailing slashes, empty grants

---

### Step 2: Validation Engine + First Spec Rules ✅ COMPLETED

> **Goal**: `sw validate spec path/to/spec.md` runs rules and reports results. This is the highest-leverage MVP feature — it proves the core concept without LLM cost.

- [x] `src/specweaver/validation/models.py` — Rule, RuleResult, Finding interfaces
- [x] `src/specweaver/validation/runner.py` — runs all rules, collects results
- Spec rules (static-only first):
  - [x] `s01_one_sentence.py` — conjunction count in Purpose ✅
  - [x] `s02_single_setup.py` — environment category count ✅
  - [x] `s05_day_test.py` — complexity score heuristic ✅
  - [x] `s06_concrete_example.py` — code block presence in Contract ✅
  - [x] `s08_ambiguity.py` — weasel word scan ✅
  - [x] `s09_error_path.py` — error/failure keyword search ✅
  - [x] `s10_done_definition.py` — verification section check ✅
  - [x] `s11_terminology.py` — inconsistent casing + undefined domain term detection ✅ (2026-03-12)
- [x] Test fixtures: `good_spec.md`, `bad_spec_ambiguous.md`, `bad_spec_no_examples.md`, `bad_spec_too_big.md`
- [x] Tests: per-rule tests (5–11 cases each), runner integration test
- [x] **Runnable**: `sw check good_spec.md` → all PASS. `sw check bad_spec_ambiguous.md` → S08 FAIL.

**Status**: All 11 rules implemented and tested (851 tests, 93% coverage).

> [!NOTE]
> Formal spec definitions (dogfooding: writing SpecWeaver specs for SpecWeaver's own rules) are deferred until LLM-integrated validation is available. The rules work and are tested; dogfooding is a documentation task, not a functional blocker.

---

### Step 3: LLM Adapter + Remaining Spec Rules ✅ COMPLETED

> **Goal**: LLM adapter works. The 2 LLM-dependent spec rules (S03, S07) are implemented. The dependency-direction rule (S04) is wired.

- [x] `src/specweaver/llm/adapter.py` — LLMAdapter abstract interface
- [x] `src/specweaver/llm/gemini_adapter.py` — Gemini API concrete adapter (with message conversion, error mapping, content filter handling)
- [x] `s03_stranger.py` — static heuristic: external refs + undefined term count ✅
- [x] `s04_dependency_dir.py` — static: cross-reference direction scan + dead-link detection (traceability extension, 2026-03-12) ✅
- [x] `s07_test_first.py` — static heuristic: contract testability scoring ✅
- [x] Tests: adapter unit tests (20+), rule tests (6 each for S03/S04/S07), error hierarchy, models

**Status**: All spec rules operational (11/11). LLM adapter ready.

---

### Step 4: Spec Review (F4) + Spec Drafting (F2) ✅ COMPLETED

> **Goal**: LLM-powered features. `sw review spec` produces semantic judgment. `sw draft` co-authors a spec interactively.

- [x] `src/specweaver/review/reviewer.py` — F4: unified review engine (ACCEPTED/DENIED/ERROR verdicts, finding extraction, raw response preserved)
- [x] `src/specweaver/context/provider.py` — ContextProvider ABC
- [x] `src/specweaver/context/hitl_provider.py` — HITL interactive context (Rich prompts, section display)
- [x] `src/specweaver/drafting/drafter.py` — F2: interactive spec drafting (5-section template, LLM per section, TODO on skip)
- [x] Tests: reviewer (10 tests incl. parse edge cases), drafter (8 tests), context provider (4 tests), HITL (5 tests), behavioral tests (error propagation, boundary inputs)
- [x] **Runnable**: `sw draft greet_service` → interactive session → `greet_service_spec.md` produced.

**Estimated effort**: 2–3 sessions. ✅ Completed.

---

### Step 5: Implementation + Code Validation + Code Review (F5, F6, F7) ✅ COMPLETED

> **Goal**: The full loop works. Spec → code → tests → validation → review.

- [x] `src/specweaver/implementation/generator.py` — F5: code generation + test generation (markdown fence cleaning, dir creation)
- [x] Code validation rules:
  - [x] `c01_syntax_valid.py` — `ast.parse` syntax check
  - [x] `c02_tests_exist.py` — test file presence
  - [x] `c03_tests_pass.py` — pytest subprocess (mocked, with timeout handling)
  - [x] `c04_coverage.py` — coverage ≥ threshold (configurable, default 70%)
  - [x] `c05_import_direction.py` — forbidden upward import scan
  - [x] `c06_no_bare_except.py` — AST scan
  - [x] `c07_no_orphan_todo.py` — TODO/FIXME/HACK/XXX grep
  - [x] `c08_type_hints.py` — AST annotation coverage check
- [x] Code review via `reviewer.review_code(code, spec)`
- [x] Integration test: `test_pipeline.py` — init → check spec → implement → check code
- [x] E2E test: `test_lifecycle.py` (972 lines) — full init → draft → check → review → implement → check → review
- [x] **Runnable**: Full core loop demonstrated on a real spec.

**Estimated effort**: 3–4 sessions. ✅ Completed.

---

### Step 6: Dogfooding — SpecWeaver Validates Its Own Specs ⏸ DEFERRED

> **Goal**: Use SpecWeaver on its own documentation. This is the "product works" moment.
> **Deferred**: Flow needs to be more stable and configurable with better validation integration before dogfooding provides meaningful feedback.

- [ ] Run `sw check` on `mvp_feature_definition.md` and architecture docs
- [ ] Run `sw draft` to create a real Component Spec for one of SpecWeaver's own modules
- [ ] Run the full loop on a small, real feature
- [ ] Fix any issues discovered during dogfooding
- [ ] **Milestone**: SpecWeaver has been used on a real project (itself).

**Estimated effort**: 1–2 sessions. Will be revisited after Phase 2 is finished.

---

## Phase 2: Flow Engine & Stabilize

> **Goal**: Agents use tools; the flow engine orchestrates atoms and subflows, whitelisting which tools agents can use at each pipeline step. MVP individual steps become composable. Agent has topology awareness. Ready for external use.

---

### Step 7: Topology Graph ✅ COMPLETED

> **Goal**: In-memory dependency graph from `context.yaml` files. Foundation for impact analysis and context-enriched prompts. Language-agnostic code analysis framework for auto-generating missing `context.yaml`.

- [x] `src/specweaver/context/analyzers.py` — `LanguageAnalyzer` ABC, `PythonAnalyzer`, `AnalyzerFactory`
  - [x] Language detection, purpose extraction (docstring), import extraction (AST), public symbol extraction, archetype inference
  - [x] Strategy + Factory pattern — extensible for Java, Kotlin, Rust, TS, C++, SQL
- [x] `src/specweaver/context/inferrer.py` — `ContextInferrer`
  - [x] Auto-generates `context.yaml` for dirs missing one (with `AUTO-GENERATED` header + warnings)
  - [x] Level inference from parent, graceful skip for empty dirs / existing files
- [x] `src/specweaver/validation/topology.py` — `TopologyNode`, `OperationalMetadata`, `TopologyGraph`
  - [x] `TopologyGraph.from_project(root)` — scan for `context.yaml`, parse, build adjacency lists
  - [x] `consumers_of(module)` — direct reverse lookup
  - [x] `dependencies_of(module)` — transitive forward traversal
  - [x] `impact_of(module)` — transitive reverse traversal
  - [x] `cycles()` — Tarjan's SCC detection (including self-loops)
  - [x] `constraints_for(module)` — aggregated constraints from module + consumers
  - [x] `operational_warnings(module)` — SLA mismatch detection (latency-critical ↔ batch, max_latency_ms)
  - [x] `auto_infer=True` integration with `ContextInferrer`
- [x] Tests (76 total):
  - [x] `tests/unit/context/test_analyzers.py` — 26 tests (core + edge cases: syntax errors, `__pycache__`, multi-line docstrings)
  - [x] `tests/unit/context/test_inferrer.py` — 15 tests (core + edge cases: idempotency, level inference, no-docstring TODO)
  - [x] `tests/unit/validation/test_topology.py` — 35 tests (core + edge cases: malformed YAML, self-reference, duplicate names, cyclic traversal)
- [x] Test restructure: `tests/unit/` reorganized to mirror `src/specweaver/` packages (7 subdirs + rules/spec/ + rules/code/)

**Estimated effort**: 1 session. ✅ Completed.

---

### Phase 2 Cross-Cutting Concerns

> These are not discrete steps but architectural decisions that apply across Steps 8–14.

#### Concurrency Readiness

**Current state** (after Step 7): partially prepared.

| Ready to parallelize | Needs work before parallelizing |
|---|---|
| Validation rules (stateless pure functions) | `ContextInferrer.infer_and_write()` — check-then-write race condition |
| TopologyGraph queries (immutable after build) | `TopologyGraph.from_project(auto_infer=True)` — reads + writes during scan |
| LLM calls (stateless per call, I/O-bound) | All I/O is synchronous — no `async/await` anywhere yet |

**Plan**: Introduce `async/await` in the flow engine (Step 11). The LLM adapter, file I/O, and subprocess calls become async. Independent pipeline steps run concurrently via `asyncio.gather()`. File writes use atomic-write patterns or `filelock`. No fundamental redesign required — the existing architecture doesn't block parallelism.

#### SQLite as Central Config Store

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

#### Project Identity & Switching

- **Project name as ID**: unique, enforced at registration. Format: `^[a-z0-9][a-z0-9_-]*$` (lowercase, hyphens, underscores, no spaces/special chars)
- **`sw use <project>`**: switch active project. If name unknown → interactive setup dialog
- **Active project**: tracked in DB (last-used project auto-selected on CLI start)

### Step 8a: Project Registry & Config Store ✅ DONE

> **Goal**: SQLite database at `~/.specweaver/` for multi-project management. Projects registered by name, config stored outside project directory (agents cannot modify guardrails).

- [x] `src/specweaver/config/database.py` — SQLite setup + schema
  - [x] `projects` table: `name` (PK, `^[a-z0-9][a-z0-9_-]*$`), `root_path`, timestamps
  - [x] `llm_profiles` table: `id`, `name`, `is_global`, `model`, `temperature`, `max_output_tokens`, `response_format`
  - [x] `project_llm_links` table: `project_name` + `role` → `profile_id` (ON DELETE CASCADE)
  - [x] `active_state` table: singleton key-value (active_project)
  - [x] `schema_version` table for future DB migrations
  - [x] WAL mode, `~/.specweaver/specweaver.db`
  - [x] Default seed: 3 global LLM profiles (review, draft, search)
- [x] `src/specweaver/config/settings.py` — rewrite to read from DB
  - [x] `register_project(name, root_path)` — validate name, insert, link default profiles
  - [x] `get_active_project()` / `set_active_project(name)`
  - [x] `get_project_config(name)` → `SpecWeaverSettings`
  - [x] `remove_project(name)` — cascade delete
  - [x] `update_project_path(name, new_path)`
  - [x] Migration: read legacy `.specweaver/config.yaml` → import into DB on first use
- [x] CLI commands:
  - [x] `sw init <name> --path <path>` — create marker + register in DB + root context.yaml
  - [x] `sw use <name>` — switch active (error + hint if not found)
  - [x] `sw projects` — list registered projects, show active
  - [x] `sw remove <name>` — unregister from DB (with confirmation)
  - [x] `sw update <name> path <new-path>` — change project root path
  - [x] `sw scan` — auto-generate missing context.yaml files (uses ContextInferrer)
- [x] `.specweaver/` in project dir becomes marker-only (no config.yaml inside)
- [x] Tests: DB creation, project CRUD, name validation, LLM profiles, active project, CLI (1034 tests)
- [x] **Runnable**: `sw init my-app --path .` registers; `sw projects` lists; `sw use` switches

**Completed**: March 2026.

---

### Step 8b: Per-Rule Validation Configuration ✅ DONE

> **Goal**: Configurable thresholds per validation rule, stored in the project config DB. Different projects can tune warning/failure thresholds and enable/disable rules without code changes.

- [x] `validation_overrides` table in `database.py` — CRUD: set, get, list, delete + cascade on project removal
- [x] `src/specweaver/config/settings.py` — `RuleOverride`, `ValidationSettings` Pydantic models
- [x] `src/specweaver/validation/runner.py` — accept `ValidationSettings`, apply overrides, `run_all` flag
  - [x] Inject thresholds into rules at construction via `_THRESHOLD_PARAMS` mapping
  - [x] Skip disabled rules (unless `run_all=True`)
- [x] 7 rules updated to accept constructor overrides:
  - [x] S01 (`warn_conjunctions`, `fail_conjunctions`, `max_h2`), S03, S04, S05, S08, S11 (spec rules), S07 (`warn_score`, `fail_score`)
  - [x] C04 (coverage — already configurable, verified)
- [x] CLI: `sw config set/get/list/reset` commands
- [x] Wire `sw check` to load overrides from DB for the active project
- [x] Add `--strict` flag to `sw check` (WARNs → exit code 1)
- [x] Add `--set` CLI override for one-off threshold changes (cascade: defaults → DB → CLI)
- [x] Tests: 88 tests covering override application, disabled rules, edge cases, DB wiring, CLI flags
- [x] **1128 tests passing, 0 regressions, 0 new lint issues**

**Depends on**: Step 8a (Config Store). ✅

**Completed**: March 2026.

---

### Step 9: Context-Enriched Prompts

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

#### 9a: Token Budget Awareness _(inspired by PasteMax)_
- [x] `llm/adapter.py` — add `count_tokens(text, model)` (abstract) + `estimate_tokens(text)` (default `len // 4`)
- [x] `llm/gemini_adapter.py` — implement `count_tokens()` via native `client.models.count_tokens()`
- [x] `llm/models.py` — add `TokenBudget` dataclass (used/limit/remaining, warn at >80%)
- [x] Schema migration v1→v2: add `context_limit` column to `llm_profiles` (default 128000)
- [ ] `sw review` / `sw draft` / `sw implement` — print token estimate before LLM call (9b/9c)
- [x] Tests: token counting, estimate fallback, budget tracking, schema migration (+16 tests, total 1144)

#### 9b: Structured Prompt Formatting _(inspired by PasteMax)_
- [ ] `src/specweaver/llm/prompt_builder.py` — `PromptBuilder` class
  - [ ] `.add_spec(path, priority=1)` / `.add_code(path, priority=2)` / `.add_context(text, label, priority=3)`
  - [ ] `.add_instructions(text)` — priority 0, never truncated
  - [ ] `.build() -> str` — assembles XML-tagged prompt (`<file_map>`, `<file_contents>`, `<system_context>`, `<user_instructions>`)
  - [ ] Per-file language detection for syntax-highlighted code fencing
  - [ ] Hybrid truncation: priority-ordered + proportional redistribution on underflow
- [ ] Refactor `reviewer.py` — extract review criteria into instruction constants, use `PromptBuilder`
- [ ] Refactor `drafter.py` — use `PromptBuilder` for LLM calls (keep Jinja2 for final file rendering)
- [ ] Refactor `generator.py` — use `PromptBuilder` for implementation prompts
- [ ] Tests: prompt assembly, truncation, tag structure, language detection, priority ordering

#### 9c: Topology Context Injection + Context Selectors
- [ ] `src/specweaver/context/selectors.py` — **Strategy pattern** for context selection
  - [ ] `ContextSelector` ABC — `select(graph, target) -> set[str]`
  - [ ] `DirectNeighborSelector` — direct consumers + deps only (for `sw draft`)
  - [ ] `NHopConstraintSelector(n_hops=1)` — N-hop UNION constraint-sharing modules (default for `sw review`, `sw implement`)
  - [ ] `ConstraintOnlySelector` — constraint violations only (for `sw check --strict`)
  - [ ] Placeholder: `ImpactWeightedSelector` stub (Phase 4)
- [ ] `topology.py` — new methods: `neighbors_within(module, depth)`, `modules_sharing_constraints(module)`, `format_context_summary(modules)`
- [ ] `cli.py` — wire topology + selectors into `draft`, `review`, `implement`
  - [ ] Load `TopologyGraph.from_project()` if active project has `context.yaml`
  - [ ] Command selects appropriate `ContextSelector`
  - [ ] Graceful fallback: no `context.yaml` → proceed without topology (no error)
- [ ] Tests: each selector on diamond/chain/isolated graphs, empty graph edge case, format_context_summary
- [ ] **Runnable**: `sw review spec.md` shows topology context + token estimate

**Depends on**: Step 7 (Topology Graph) for 9c only. 9a and 9b are independent.

**Estimated effort**: 2.5 sessions (9a: 0.5, 9b: 1, 9c: 1).

---

### Step 10: Flow Engine — Pipeline Models & Definition Format

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

### Step 11: Flow Engine — Runner & State Tracking

> **Goal**: Execute a pipeline step-by-step. Track where each spec is in the lifecycle. Persist state so interrupted runs can resume. Introduce async execution and SQLite state persistence.

- [ ] `src/specweaver/flow/runner.py` — `PipelineRunner`
  - [ ] Accept `PipelineDefinition` + project context
  - [ ] **Async execution**: `async def run_step()` — LLM calls, file I/O, subprocess via `asyncio`
  - [ ] Execute steps sequentially by default, `asyncio.gather()` for independent steps
  - [ ] Map step types to existing modules (validate → `runner.run_rules`, draft → `Drafter.draft`, etc.)
  - [ ] Track `PipelineState` per spec
- [ ] `src/specweaver/flow/state.py` — **SQLite** state persistence (`.specweaver/state.db`)
  - [ ] Tables: `pipeline_runs`, `step_results`, `audit_log`
  - [ ] WAL mode for concurrent read/write
  - [ ] Save/load state, support resume from last completed step
  - [ ] Atomic transitions (no half-written state on crash)
- [ ] `src/specweaver/llm/adapter.py` — `async def generate()` (backward-compatible sync wrapper)
- [ ] Tests: runner with mock steps, state save/load, resume from checkpoint, concurrent step execution
- [ ] **Runnable**: Pipeline runs end-to-end programmatically (not yet via CLI)

**Depends on**: Step 10 (Pipeline Models). Uses existing modules: `validation/runner`, `drafting/drafter`, `review/reviewer`, `implementation/generator`.

**Estimated effort**: 2–3 sessions.

---

### Step 12: Flow Engine — Gates, Retry & Feedback Loops

> **Goal**: Configurable gates (auto-pass, HITL approval), retry on failure, feedback loops (re-draft after failed review).

- [ ] `src/specweaver/flow/gates.py` — gate implementations
  - [ ] Auto gate: pass if step results meet threshold
  - [ ] HITL gate: pause, show results, wait for human approve/reject/edit
  - [ ] Validation gate: run `sw check` as a gate condition
- [ ] `src/specweaver/flow/runner.py` — extend with gate + retry logic
  - [ ] On gate failure: retry step, escalate, or abort (configurable)
  - [ ] Feedback loop: e.g., review DENIED → re-run draft with review findings injected
  - [ ] Max retry count per step
- [ ] Tests: gate logic, retry counts, feedback injection, abort conditions
- [ ] **Runnable**: Pipeline pauses at HITL gates, retries failed steps

**Depends on**: Step 11 (Runner).

**Estimated effort**: 1–2 sessions.

---

### Step 13: CLI Polish & Error Handling

> **Goal**: `sw run` command to invoke pipelines from CLI. Proper error handling, colored progress, `--verbose` / `--json` output modes.

- [ ] `sw run` CLI command — load pipeline YAML, run through `PipelineRunner`
  - [ ] `sw run new_feature my_module` — run the `new_feature` pipeline for `my_module`
  - [ ] `sw run --resume` — pick up from last checkpoint
  - [ ] `--verbose` flag — show detailed step output
  - [ ] `--json` flag — machine-readable output
- [ ] Progress indicators: Rich spinners/progress bars during LLM calls
- [ ] Error handling across all commands:
  - [ ] Graceful LLM failures (timeout, rate limit, content filter)
  - [ ] Network errors → retry with backoff
  - [ ] File not found / permission errors → clear message
- [ ] Tests: CLI integration tests, error scenarios
- [ ] **Runnable**: `sw run new_feature greet_service` runs the full pipeline with visible progress

**Depends on**: Steps 11-12 (Flow Engine Runner + Gates).

**Estimated effort**: 1–2 sessions.

---

### Step 14: Documentation & Phase 2 Milestone

> **Goal**: README, quick-start guide, `sw --help` for all commands. Test coverage audit.

- [ ] `README.md` — installation, quick-start, command reference
- [ ] `sw --help` and per-command help text audit
- [ ] Quick-start guide: from `sw init` to a completed pipeline run
- [ ] Test coverage audit: ensure 70–90% across all modules
- [ ] Gap-fill: any under-tested modules from Steps 7-13
- [ ] **Milestone**: Pipelines are configurable and reusable. Agent has topology awareness. Someone else could install and use SpecWeaver.

**Depends on**: All preceding Phase 2 steps.

**Estimated effort**: 1 session.

---

## Phase 3: Feature Isolation & Incremental Expansion

> **Goal**: Take each major capability from the architecture docs, isolate it as a self-contained feature, and implement it one by one. Each feature is proposed → approved → implemented → tested → merged.

Order will be based on value and dependencies. Likely sequence:

| Priority | Feature | Source Doc | Why This Order |
|:---|:---|:---|:---|
| **3.1** | Feature Spec layer (L2 decomposition) | `lifecycle_layers.md` | Enables multi-layer workflows |
| **3.2** | Domain profiles for threshold calibration | `future_capabilities_reference.md` §19 | Quick win — just config |
| **3.3** | Custom rule paths (project-specific validators) | _(deferred from Step 8b)_ | `custom_rule_paths` table + dynamic loader; enables domain-specific rules (D01+) without core changes |
| **3.4** | Additional context providers (FileSearch, WebSearch) | `mvp_feature_definition.md` | Enhances drafting and review quality |
| **3.5** | Multi-model LLM support (dynamic routing) | `future_capabilities_reference.md` §9, §15 | Route prompts to best model per task by result/cost ratio (Gemini, Claude, Qwen, Mistral, OpenAI); interface already abstracted |
| **3.6** | Spec-to-code traceability | `future_capabilities_reference.md` §17 | Bidirectional linking |
| **3.7** | Automated spec decomposition | `future_capabilities_reference.md` §18 | Agent proposes, HITL approves |
| **3.8** | Constitution enforcement | `constitution_template.md` | Project-wide constraint checking |
| **3.9** | Smart scan exclusions (tiered) | _(inspired by PasteMax)_ | 3-tier file exclusion: binary exts, default patterns (.git, __pycache__), per-project overrides + `.specweaverignore` |
| **3.10** | File watcher (`sw watch`) | _(inspired by PasteMax)_ | Auto-re-validate specs on disk change; DX polish for iterative authoring |

**Process for each feature**:
1. Write an isolation proposal (what, inputs, outputs, interfaces, scope)
2. HITL approves the proposal
3. Implement with tests
4. Dogfood on SpecWeaver itself
5. Merge

---

## Phase 4: Advanced Capabilities

> **Goal**: The features from `future_capabilities_reference.md` that require significant engineering.

| Priority | Feature | Source |
|:---|:---|:---|
| **4.1** | Symbol index + anti-hallucination gate | `future_capabilities_reference.md` §11 |
| **4.2** | AST-based semantic chunking (RAG foundation) | `future_capabilities_reference.md` §3 |
| **4.3** | RAG context provider + rich Qdrant payloads | `rag_architecture.md` §1/§5, [Domain Brain proposal](domain_brain_hybrid_rag.md) Phase C |
| **4.4** | Tiered access rights (zero-trust knowledge) | `future_capabilities_reference.md` §1 |
| **4.5** | Agent isolation patterns (multi-agent review) | `future_capabilities_reference.md` §6 |
| **4.6** | Verification gates (mutation testing, assertion density) | `future_capabilities_reference.md` §13, §14 |
| **4.7** | Blast radius / locality enforcement | `future_capabilities_reference.md` §16 |
| **4.8** | Containerized deployment (Podman) | `mvp_feature_definition.md` |
| **4.9** | **Web UI + server mode** | _(new)_ — SpecWeaver as a daemon with REST/WebSocket API and browser-based UI for remote operation (tablet/mobile). Enables directing SpecWeaver from any device while it runs on a home/cloud server. |

---

## Phase 5: Domain Brain — Hybrid Graph + Vector RAG

> **Goal**: Persistent domain knowledge system that enables cross-service impact analysis, SLA-aware spec authoring, and automated architectural consistency enforcement.
> **Full proposal**: [Domain Brain — Hybrid Graph + Vector RAG Architecture](domain_brain_hybrid_rag.md)

| Priority | Feature | Proposal Phase |
|:---|:---|:---|
| **5.1** | Persistent topology graph (serialized JSON → FalkorDB) | Phase D.1 → D.2 |
| **5.2** | Event-driven knowledge graph (EDKG) — file/commit triggers update nodes/edges | Phase D |
| **5.3** | Hash-based garbage collection for graph nodes | Phase D |
| **5.4** | Hybrid RAG orchestration — graph-guided vector search | Phase C + D |
| **5.5** | Provenance tracking + trust levels for knowledge sources | Phase D |
| **5.6** | Socratic drafting flow — topology-aware questioning during `sw draft` | Phase A+B (seeds in Phase 2) |

> [!NOTE]
> Phases A (context-enriched prompts) and B (in-memory topology graph) are already scheduled in Phase 2 above. Phase 5 covers the persistent, event-driven extensions that add value only when managing large multi-service architectures (20+ services).

---

## Phase 6: External Validation

> **Goal**: SpecWeaver is used on a real project that isn't SpecWeaver itself.

- [ ] Identify a target project (e.g., the automatic trading system — 20 microservices, multi-tenant, multi-strategy)
- [ ] Run the full workflow: `sw init` → `sw draft` → `sw validate spec` → `sw implement` → `sw validate code` → `sw review code`
- [ ] Document the experience: what worked, what didn't, what's missing
- [ ] **Milestone**: SpecWeaver is **useful** on real-world projects.

---

## Timeline Estimate (Spare-Time + AI Agents)

```
Phase 1: MVP (Steps 1-6)     ████████████████████████████     (~8-12 sessions)  [Steps 1-5 ✅, Step 6 ⏸]
Phase 2: Flow Engine (7-14)   ████████████████████████████████ (~10-14 sessions)
Phase 3: Feature Expansion    ████████████████████████████████ (~open-ended, feature by feature)
Phase 4: Advanced             ████████████████████████████████ (~open-ended)
Phase 5: Domain Brain         ████████████████             (~when in-memory graph proves insufficient)
Phase 6: External             ████████                         (~2-3 sessions)
                              ─────────────────────────────────────────────
                              S1        S5        S10       S15        ...
```

> [!TIP]
> **Agent leverage**: Steps 2-3 (validation rules) are prime candidates for AI-assisted implementation — each rule is a small, self-contained function with clear inputs/outputs. Steps 4-5 (LLM features) require more human judgment on prompt design.

---

## Success Criteria

**MVP is PROVEN when you can:**
1. ✅ `sw init my-app --path .` registers and scaffolds the project
2. ✅ `sw validate spec some_spec.md` reports PASS/FAIL with findings
3. ✅ `sw draft greet_service` produces a real spec via HITL interaction
4. ✅ `sw implement greet_service_spec.md` generates code + tests
5. ✅ `sw validate code greet_service.py` checks syntax, tests, coverage
6. ✅ `sw review code greet_service.py` provides LLM semantic judgment

**Product is USEFUL when additionally:**
7. ✅ You've used it on SpecWeaver itself (dogfooding)
8. ✅ You've used it on an external project (trading system)
9. ✅ Features can be added without restructuring (interface extensibility confirmed)
10. ✅ Topology-aware spec authoring catches cross-service issues before code generation
11. ✅ Multi-project management: `sw projects`, `sw use`, `sw remove`, `sw update`, `sw scan`

---

## Superseded Document

This roadmap replaces the original `specweaver_roadmap.md` from flowManager, which described evolving the flowManager engine (recursive flow execution, atoms, sub-flows, state persistence, crash recovery). That approach was abandoned in favor of a fresh start — see [ORIGINS.md](../ORIGINS.md) for the full history.
