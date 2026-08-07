# Design: Context Loading Pipeline Refactoring

- **Feature ID**: TECH-006
- **Phase**: Technical Debt
- **Status**: COMPLETE
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_design.md

> [!IMPORTANT]
> **Direction update (2026-07-21, middle-way review):** the core of this design (delete misplaced CLI-layer
> helpers, call public Domain APIs, untangle the cross-interface spider-web) remains fully valid and
> compatible. However, any follow-up that would centralize constitution/standards **content loading inside
> the prompt factory** (the topic-doc "Highest-ROI" row) is **redirected**: under `C-INTL-06`
> (Envelope-vs-Content) + `C-FLOW-11` (agentic work units read mounted files), the destination is **domain
> loaders + canonical on-disk files** shared by both execution modes — not deeper factory centralization.

## Feature Overview

Feature TECH-006 eliminates **5 misplaced private helper functions** (in 2 copies = 6 total) from the CLI interface layer. These functions contain domain logic, infrastructure wiring, or string-dispatched repository calls that have nothing to do with the CLI. Because they are in the wrong layer, the REST API and 10+ CLI modules import them cross-interface, creating a massive spider web of forbidden boundary violations — including the REST API depending on the CLI. The fix: delete all 6 function definitions and replace them with direct calls to existing public Domain APIs. Key constraints: full backward compatibility, zero new modules, `tach check` compliance.

## Research Findings

### The 5 Functions To Delete (6 definitions)

| # | Function | Lives in (WRONG) | Why it's wrong | Replacement |
|---|----------|-----------------|----------------|-------------|
| 1 | `_load_constitution_content` | `workspace/project/interfaces/cli.py` | 2-line wrapper around existing domain API | Inline `find_constitution()` from `workspace/project/constitution.py` |
| 2 | `_load_standards_content` | `assurance/standards/interfaces/cli.py` | Wrapper that calls CLI singletons, then delegates to domain API | Direct `load_standards_content()` / `load_standards_content_async()` from `assurance/standards/loader.py` |
| 3 | `_require_llm_adapter` | `infrastructure/llm/interfaces/cli.py` | Wrapper around `load_settings()` + `create_llm_adapter()` with `typer.Exit` and a hardcoded fallback (`api_key="test-key"`) | Direct `load_settings()` + `create_llm_adapter()`. Hardcoded fallback is deliberately killed (security risk). |
| 4a | `_run_workspace_op` | `workspace/project/interfaces/cli.py` | String-dispatched generic sync wrapper. Not type-safe, not grep-friendly, not refactor-safe. | New typed `run_repo_op()` in `interfaces/cli/_core.py` |
| 4b | `_run_workspace_op` (DUPLICATE) | `core/config/interfaces/cli.py` | Second copy of the same anti-pattern | Same — replaced by `_core.run_repo_op()` |
| 5 | `_load_topology` + `_select_topology_contexts` | `graph/interfaces/cli.py` | Domain logic mixed with `console.print` output. Called by API endpoint (silent bug — Rich prints to nowhere). | New public facade in `assurance/graph/` |

### `_run_workspace_op` Replacement: Typed `run_repo_op()`

The string-dispatched `_run_workspace_op` cannot be replaced by inlining 5 lines × 20 call sites (that's 100 lines of boilerplate — a worse DRY violation). Instead, a **typed** replacement is added to `interfaces/cli/_core.py`:

```python
def run_repo_op(fn: Callable[[WorkspaceRepository], Awaitable[T]]) -> T:
    """Run a typed WorkspaceRepository operation synchronously (CLI only)."""
    db = get_db()
    async def _action() -> T:
        async with db.async_session_scope() as session:
            return await fn(WorkspaceRepository(session))
    return anyio.run(_action)
```

Call sites become type-safe one-liners:
```python
# Before (string dispatch, not type-safe):
active = _run_workspace_op("get_active_project")
proj = _run_workspace_op("get_project", name)

# After (typed lambda, IDE autocomplete, grep-friendly):
active = _core.run_repo_op(lambda r: r.get_active_project())
proj = _core.run_repo_op(lambda r: r.get_project(name))
```

### Cross-Interface Spider Web (complete violation count)

**`_load_constitution_content`** — 5 cross-interface imports (3 CLI + 2 API 🚨):
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`
- `interfaces/api/v1/review.py` 🚨, `interfaces/api/v1/implement.py` 🚨

**`_load_standards_content`** — 3 cross-interface imports:
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`

**`_require_llm_adapter`** — 4 cross-interface imports:
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`, `assurance/validation/interfaces/cli_drift.py`

**`_run_workspace_op`** — 6 cross-domain imports + 1 duplicate definition:
- **Definition 1** (workspace): `interfaces/cli/_core.py`, `interfaces/cli/main.py`, `infrastructure/llm/interfaces/cli.py`, `graph/interfaces/cli.py`, `assurance/validation/interfaces/cli.py`, `assurance/standards/interfaces/cli.py`
- **Definition 2** (config): used internally by `core/config/interfaces/cli.py`

**`_load_topology` / `_select_topology_contexts`** — 4 cross-interface imports (3 CLI + 1 API 🚨):
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`
- `interfaces/api/v1/implement.py` 🚨

**Total: 23 cross-interface import violations + 1 duplicate definition eliminated.**

### Blueprint References
- `docs/architecture/07_architectural_decision_records/adr_002_composition_root_vs_factories.md` — Confirms Composition Root stays at the Entry Point. TECH-009 was evaluated and cancelled.

### SF-02 Research: `RunContext`'s 32 Fields, Field-by-Field (2026-08-02)

Every field's writers, readers, and lifecycle were traced across the full codebase before proposing
any grouping (not just from the existing inline comments, though those turned out to be reliable
signal — `INT-US-09`, `C-EXEC-06`, and `INT-US-21 AD-1` are each an accurate preview of a real
cluster). Key structural finding: **construction is heterogeneous, not uniform** — there are 7
production construction sites (`sw run`, `sw resume`, `sw implement`, `sw review`, standards CLI,
drift CLI ×2, API ×3) and each passes a different subset of fields; several fields are never passed
at any production site at all.

**Lifecycle**: one canonical `RunContext` lives on `PipelineRunner._context` for the whole run
(`run_id`/`step_records`/`pipeline_runner` re-stamped every step iteration); `execute_run`
(`runner_utils.py`) does a **shallow `copy.copy`** for session-level worktree isolation (mutable
fields like `feedback`/`step_records` stay shared by reference with the original for the session's
duration); `execute_in_sandbox` does a **second shallow copy** per-step for per-step worktree
isolation when no session is active. `hydration.py` is the sole writer of `plan`/`decomposition`,
called once per successfully-advanced step and replayed on `resume()`.

**Field disposition** (32 total): 19 fields move into 6 new cohesive sub-models (FR-6), 3 are
deleted as confirmed-zero-reader dead weight (FR-8: `env_vars`, `step_records`, `pipeline_name`),
10 stay flat (AD-6) because they don't cluster cohesively with anything else by actual evidence:
`project_path`, `spec_path`, `db`, `output_dir`, `feedback`, `constitution`, `standards`,
`project_metadata`, `context_provider`, `settings`.

**Fields with real readers but NO production writer** (`stale_nodes`, `workspace_roots`, and
`settings` partially) are **kept, not deleted** — a reader consuming a field that's never populated
in production is a real, half-built feature gap (deleting the field would remove behavior a future
change might legitimately need), not dead code in the same sense as FR-8's three targets. Migrated
into their groups (`stale_nodes`/`workspace_roots` → `GraphContext`) or left flat (`settings`), but
whether/how to actually wire a writer for them is explicitly **out of scope** — see Non-Goals.

**Discovered but out of scope** (real findings, not fixed by SF-02 — see Non-Goals for disposition):
- `enforce_isolation` is only ever set by `sw run`/`sw resume`; `sw implement`, `sw review`,
  `standards`, `drift`, and the API all silently run with per-step worktree isolation permanently
  off regardless of the project's `[sandbox]` settings.
- `sw resume` never re-sets `topology`, unlike `sw run` (asymmetry, likely an oversight).
- `context.pipeline_runner` is reached into for its private `._context`/`._registry`/`._store`/
  `._on_event` internals by `decompose.py`/`dual_pipeline.py`'s fan-out — a layering violation that
  predates this ticket.
- `feedback` (dict) does double duty as two entangled message-passing patterns: loop-back feedback
  keyed by destination step name (written only by `gates.inject_feedback`) and a general-purpose
  scratch channel keyed by fixed semantic strings (`scenario_test_failures`, etc., written by
  `arbiter.py`/`review.py`/`scenario.py`/`validation.py`).
- API construction sites (`interfaces/api/v1/pipelines.py`) wire almost nothing (`project_path`,
  `spec_path`, `output_dir` only) — already a documented backlog item (`INT-US-09 Backlog` note at
  that file's own `pipelines.py:84-90`), not new.

## Functional Requirements

| # | FR | Action | Outcome |
|---|-----|--------|---------|
| FR-1 | Delete `_load_constitution_content` | Replace all 5 imports with inline `find_constitution()` calls | Zero cross-interface constitution imports |
| FR-2 | Delete `_load_standards_content` | Replace all 3 imports with direct `load_standards_content()` / `load_standards_content_async()` calls, passing `db` and `project_name` explicitly | Standards loading decoupled from CLI singletons |
| FR-3 | Delete `_require_llm_adapter` | Replace all 4 imports with direct `load_settings()` + `create_llm_adapter()` calls. Each CLI caller handles its own errors via `typer.Exit`. Hardcoded fallback (`api_key="test-key"`) is deliberately killed — security risk. | LLM wiring decoupled from CLI |
| FR-4 | Delete both copies of `_run_workspace_op` | Add typed `run_repo_op()` to `interfaces/cli/_core.py`. Replace all ~20 call sites across 8 modules with `_core.run_repo_op(lambda r: r.method())` (type-safe, grep-friendly, 1 line per call) | String-dispatch anti-pattern eliminated. Duplicate definition deleted. |
| FR-5 | Delete `_load_topology` + `_select_topology_contexts` | Add a small public facade in `assurance/graph/` for topology loading + selector execution. Replace all 4 imports. Remove `console.print` from domain logic. | Topology logic moved to domain layer. API silent-print bug fixed. |
| FR-6 | Introduce 6 cohesive nested sub-models on `RunContext`, grouping 19 of its 32 flat fields | `ModelAccess` (`llm`, `config`, `llm_router`); `IsolationPolicy` (`enforce_isolation`, `execution_root`, `session_isolation`, `allowed_paths`, `dal_level`); `PlanContext` (`plan`, `decomposition` — matches the existing AD-1 comment); `GraphContext` (`topology`, `stale_nodes`, `workspace_roots`, `api_contract_paths`); `RunHandle` (`run_id`, `pipeline_runner`, `task_id`); `AnalysisContext` (`analyzer_factory`, `parsers`). `RunContext` remains the ONE object every `StepHandler.execute()` receives — no handler signature change. | New fields land in one of 6 named homes instead of one flat 32-field bag; `RunContext`'s own top-level attribute count drops from 32 to ≤16. |
| FR-7 | Migrate every production call site of a moved field to its new nested path | `context.llm` → `context.model.llm`, `context.topology` → `context.graph.topology`, etc., across every handler, `runner.py`, `runner_utils.py`, `gates.py`, `hydration.py`, `staleness.py`, `sandbox/security.py` | Zero change to external CLI/API/pipeline behavior (NFR-1 preserved); a missed call site fails loudly (`AttributeError`) in tests, not silently at runtime |
| FR-8 | ~~Delete `env_vars`, `step_records`, `pipeline_name`~~ **Superseded during implementation — see FR-8a/b/c below.** The premise ("confirmed zero production readers for any of the three") held for only one of them. | — | — |
| FR-8a | Delete `env_vars` | Confirmed dead on arrival: introduced (`17ee01f5`, 2026-04-12) with a documented plan to inject it into spawned processes; that half was never built. `C-EXEC-02` later shipped an explicit per-step `env:` map that *deliberately* refuses this field, to stop secrets leaking into `stdout`/`step_records`. The need is met by a better design. | 1 field removed, no behavior change |
| FR-8b | Delete `pipeline_name` **and fix the bug it was hiding** | It had two real readers (`gates.py` RESERVE resource key, `runner_utils` worktree branch name) but **nothing ever set it**, so both always took their fallback. Consequence: every pipeline in a project contended for one shared lock `pipeline:default_pipeline`, so the RESERVE gate serialised *globally* instead of *per pipeline* — the opposite of its purpose. Both readers now take the name from `PipelineRun.pipeline_name`, which is always populated. Substituting the literal (as FR-8 originally directed) would have cemented the defect and erased the evidence. | 1 field removed; RESERVE gate serialises per pipeline as designed; worktree branches carry the real pipeline name |
| FR-8c | **Do NOT delete `step_records` — relocate it into `RunHandle`** | Not dead: it is the delivered mechanism of `C-EXEC-02` FR-6/AD-4 ("makes a completed bash step's `StepResult.output` readable by every later step … via the existing `RunContext.step_records` list"), with `test_downstream_step_reads_step_records` as its acceptance test. No *shipped handler* reads it, which is what the original research found — but a delivered story selected it as its state-propagation channel. Deleting it would withdraw a delivered FR. Moved to `context.run.step_records`; capability and tests intact. | Field leaves `RunContext`'s top level without losing a delivered capability |
| FR-9 | Shorten `model_post_init` | Extract `project_metadata` construction and `parsers` default-injection into two named, independently unit-testable private methods | `model_post_init` body materially shorter; both extracted behaviors independently testable without constructing a full `RunContext` |
| FR-10 | Preserve `PlanContext`'s hydration semantics | `plan`/`decomposition`'s existing `hydration.py` clear-on-`FAILED`/`ERROR` *values* are unchanged after the move into `PlanContext` — but per AD-8 (frozen sub-models), the *write mechanism* changes from direct field assignment to `context.plan_context = context.plan_context.model_copy(update={...})` at both `hydration.py` call sites | No behavior/value change to plan/decomposition invalidation; only the write mechanism changes |
| FR-11 | Preserve `RunHandle.pipeline_runner`'s fan-out access pattern | `decompose.py`/`dual_pipeline.py`'s existing (if architecturally smelly) access to `context.pipeline_runner` internals is unchanged after the move into `RunHandle` — redesigning the fan-out mechanism itself is explicitly OUT of scope (see Non-Goals) | No behavior change to fan-out sub-pipeline spawning |
| FR-12 | Set `extra="forbid"` on `RunContext` and all 6 new sub-models | Found in Phase 6 Red/Blue review (RED-1.1): Pydantic v2 defaults to `extra="ignore"` — verified empirically that constructing `Model(known=1, unknown=2)` silently drops `unknown` with zero error. Without this, a missed migration at a CONSTRUCTION call site (as opposed to an attribute-read site) would silently drop the old kwarg instead of raising, directly contradicting NFR-6. Confirmed safe to add: no production call site constructs `RunContext` via `**kwargs` unpacking (grepped, none found) — every construction site uses explicit keyword arguments. | Every missed migration — construction-time AND attribute-access-time — fails loudly with a `ValidationError`/`AttributeError`, never silently |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Compatibility | The refactoring SHALL NOT break any existing CLI commands or API endpoints. |
| NFR-2 | Architecture | The refactoring SHALL pass `tach check` with zero boundary violations. |
| NFR-3 | Architecture | No interface module SHALL import private helpers from another interface module. |
| NFR-4 | Architecture | No API module SHALL import from any CLI module. |
| NFR-5 | Minimal new code | Only 2 new public functions: `run_repo_op()` in `_core.py` and a topology facade in `assurance/graph/`. |
| NFR-6 | SF-02: Fail loudly, not silently | A missed migration SHALL fail loudly both at construction (`ValidationError` via FR-12's `extra="forbid"`) and at attribute access (`AttributeError` at the old flat path) — never a silent kwarg-drop or a silent `None`. |
| NFR-7 | SF-02: Field count | `RunContext`'s own top-level attribute count SHALL decrease from 32 to **≤15** after FR-6/FR-8. **Corrected during implementation:** this requirement originally said ≤16, a number derived from the field grouping alone without ever being checked against the project's own god-object gate (`scripts/check_class_health.py`, `MAX_ATTRIBUTES = 15`). At ≤16 the ticket would have declared success while the god-object detector still fired on the very file it targeted. Reaching 15 needed two further changes beyond the original design: `model_config` excluded from the metric (it is Pydantic's own configuration, present on every Pydantic model, so it lowered the real budget by one for those classes and told you nothing — fixed separately in `check_class_health.py`), and `constitution`/`standards` grouped into `GuidanceContent` (AD-9). |
| NFR-8 | SF-02: Shallow-copy safety | Found in Phase 6 Red/Blue review (RED-1.3): `copy.copy(context)` (used by `runner_utils.execute_run`/`execute_in_sandbox` for worktree isolation) shares every nested sub-model INSTANCE by reference between the original and the copy — mutating a sub-model field in place on the copy (e.g. `isolated.isolation.execution_root = x`) would corrupt the original too, unlike today's flat-field reassignment (safe under shallow copy). Per AD-8 (frozen sub-models, resolving RED-2.1), this is now enforced by the type system, not just convention: any attempted in-place mutation of a nested sub-model field raises `ValidationError` immediately, on a shallow-copied context or otherwise. Any isolated-copy update of a grouped field SHALL construct a new sub-model instance via `.model_copy(update={...})` and reassign the whole sub-model attribute. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Delete all 5 CLI wrappers (6 definitions) | Domain logic doesn't belong in the interface layer. Public APIs already exist. | No |
| AD-2 | Replace `_run_workspace_op` with typed `run_repo_op()` | Eliminates string-dispatch anti-pattern. Keeps DRY (1 helper, not 20 inlined copies). Type-safe, grep-friendly, IDE autocomplete. | No |
| AD-3 | Kill hardcoded LLM fallback | `api_key="test-key"` is a security risk and a silent behavior change. Proper error handling replaces it. | No |
| AD-4 | Add topology facade in `assurance/graph/` | Only function where the public API doesn't fully exist yet. Small facade wrapping `TopologyGraph.from_project()` + selector logic. | No |
| AD-5 | SF-02: Nested sub-models on `RunContext`, not a full breakup into separate handler parameters | Preserves `StepHandler.execute(step, context)`'s existing signature (NFR-1) — every handler keeps receiving ONE object. Composition via nested Pydantic models gives new fields a cohesive home without the much larger, riskier change of threading multiple typed parameters through every handler call site and the runner's dispatch logic. | No |
| AD-6 | SF-02: Keep `project_path`, `spec_path`, `db`, `output_dir`, `feedback`, `constitution`, `standards`, `project_metadata`, `context_provider`, `settings` flat (not grouped) | None of these cluster cohesively with another field by actual read/write evidence (research, below) — forcing a group for its own sake would trade one god object for several arbitrary ones. `project_metadata`/`parsers` remain computed-on-construction defaults (FR-9 only shortens how they're computed, not where they live). | No |
| AD-7 | SF-02 stays ONE sub-feature (not split into SF-02a/b/c…) despite exceeding Phase 4's default decomposition trigger (>5 FRs, >3 modules touched) | User's explicit choice (2026-08-02) — the six sub-model groups are independently self-contained enough to land as **separate commit boundaries within one sub-feature** rather than as separate named sub-features; the design doc doesn't fork, only the implementation plan's commit sequence does. | No — HITL-approved deviation from the skill's default heuristic, not a rule violation. |
| AD-9 | SF-02: `constitution` + `standards` grouped into `GuidanceContent`, overturning AD-6 for this pair (2026-08-07) | AD-6's criterion was right — "none of these cluster cohesively with another field by actual read/write evidence" — it was simply never applied to this pair, because the research traced the 19 fields being moved and gave the 10 left flat a blanket judgment. Applying AD-6's own test: **all 7 production construction sites set both fields, on adjacent lines, and none sets one without the other** (`core/flow/interfaces/cli.py:297,508`, `api/v1/implement.py:91,100`, `api/v1/review.py:71`, `workflows/implementation/interfaces/cli.py:244`, `workflows/review/interfaces/cli.py:321`). That is stronger co-occurrence than several groupings the design already approved. Note honestly: the attribute count also *required* one more grouping, and this was the only pair with real evidence — but the evidence stands on its own. | No — applies AD-6's stated criterion more carefully, rather than substituting a different one |
| AD-8 | SF-02: All 7 new sub-models are `frozen=True` | User's explicit choice (2026-08-06, Phase 6 HITL, resolving RED-2.1) — structurally closes the shallow-copy mutation bug class RED-1.3 found (any future direct `context.<group>.<field> = x` raises immediately instead of silently corrupting a shared instance), at the cost of `hydration.py`'s `plan`/`decomposition` writes changing from direct assignment to `context.plan_context = context.plan_context.model_copy(update={...})` (FR-10 updated accordingly — the resulting *value* is unchanged, the *write mechanism* is not). | No |

## Sub-Feature Breakdown

### SF-01: Delete All CLI Wrappers (Single Atomic Commit)
- **Scope**: Delete all 6 function definitions. Replace all 23 import sites. Add `run_repo_op()` to `_core.py`. Add topology facade to `assurance/graph/`. One atomic commit — all files touched in one pass to avoid merge conflicts.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5]
- **Affected files** (~15 files):
  - **Delete from**: `workspace/project/interfaces/cli.py`, `assurance/standards/interfaces/cli.py`, `infrastructure/llm/interfaces/cli.py`, `graph/interfaces/cli.py`, `core/config/interfaces/cli.py`
  - **Update imports**: `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`, `assurance/validation/interfaces/cli.py`, `assurance/validation/interfaces/cli_drift.py`, `interfaces/api/v1/review.py`, `interfaces/api/v1/implement.py`, `interfaces/cli/_core.py`, `interfaces/cli/main.py`
  - **Add to**: `interfaces/cli/_core.py` (run_repo_op), `assurance/graph/` (topology facade)
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_sf01_implementation_plan.md

### SF-02: Reduce `RunContext` God Object
- **Scope**: Finding 3 from the original topic-doc entry (RunContext god object) was documented but never incorporated into this design's FRs — SF-01 only ever covered Findings 1 & 2. `RunContext` (`core/flow/handlers/base.py`) has grown from the 23 fields the topic-doc entry named as the problem to 32 fields today, with a 68-line `model_post_init` handling parser injection, project-metadata construction, and config introspection as side effects. Per the 2026-07-21 direction update, the destination is NOT further centralization into the prompt factory — split `RunContext`'s responsibilities into 6 cohesive nested sub-models (AD-5/AD-6) so new fields have somewhere better to land than one shared bag, while `RunContext` itself stays the single object every handler receives.
- **FRs**: [FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-12]
- **Inputs**: `RunContext`'s current 32 fields and `model_post_init` body in `core/flow/handlers/base.py` (full field-by-field map in Research Findings, above).
- **Outputs**: `RunContext` reduced to ≤16 top-level attributes (10 flat + 6 sub-models); `model_post_init` shortened via two extracted private methods; 3 confirmed-dead fields removed; zero behavior change to any existing CLI command, API endpoint, or pipeline run.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_sf02_implementation_plan.md (not yet written)
- **Commit boundaries** (one sub-feature, AD-7 — the implementation plan owns the exact sequencing;
  revised by Phase 6 Red/Blue review, RED-1.2, from a purely-additive shape to per-group-atomic —
  see Red/Blue report below for why): each commit adds ONE group's sub-model, migrates **every**
  production and test call site for that group's fields, and **removes the corresponding old flat
  field(s) in the same commit** — never leaving an old and a new field alive for the same data
  across a commit boundary, which would let them silently diverge with nothing to catch it.
  1. `IsolationPolicy` — fully owned by `runner_utils.py`, the most self-contained group. Includes
     the RED-1.3 fix: any isolated-copy mutation of `execution_root` must construct a new
     `IsolationPolicy` via `.model_copy(update={...})`, never mutate the shared instance a shallow
     `copy.copy(context)` leaves referenced from both the original and the copy.
  2. `PlanContext` — owned by `hydration.py` (writer) + `generation.py`/`decompose.py` (readers),
     matches the existing AD-1 boundary exactly.
  3. `RunHandle` + `AnalysisContext` + `ModelAccess` — runner-injected identity, DI/AST tooling, and
     LLM wiring, each independently traced in research.
  4. `GraphContext` — `topology`/`stale_nodes`/`workspace_roots`/`api_contract_paths`, spans the
     most consumer files (5); done last since it has no other group's migration as a prerequisite
     but benefits from the pattern being proven on the earlier groups first.
  5. Delete the 3 dead fields (FR-8) + shorten `model_post_init` (FR-9) — cleanup after every
     consumer has moved off every flat field these commits touched.
- **Non-Goals** (real findings from research, explicitly deferred — not fixed by SF-02):
  - Redesigning `pipeline_runner`'s fan-out mechanism (the `decompose.py`/`dual_pipeline.py` reach into runner internals) — pre-existing layering smell, unrelated to field grouping.
  - Wiring a production writer for `stale_nodes`/`workspace_roots`/`settings` — real half-built-feature gaps (readers exist, no writer), not a decision this ticket makes.
  - Fixing `enforce_isolation`'s wiring asymmetry (only `sw run`/`resume` set it) or `sw resume`'s `topology`-reload asymmetry — real bugs, unrelated to field grouping.
  - Splitting `feedback`'s two entangled usage patterns into typed channels — real opportunity, deferred; `feedback` stays one flat dict field in SF-02.
  - Widening the API's near-empty `RunContext` construction (`interfaces/api/v1/pipelines.py`) — pre-existing, already tracked via that file's own `INT-US-09 Backlog` comment.
- **Note (2026-08-01)**: the roadmap blurb claiming this ticket "reduces RunContext from a 23-field God Object to a lean execution context" was never true — Finding 3 was never designed or built. SF-02 is the actual work needed to make that claim true.

## Execution Order

1. SF-01 — single atomic commit covering all 5 functions.
2. SF-02 — independent of SF-01, can start any time.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Delete All CLI Wrappers | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Reduce `RunContext` God Object | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: SF-01 and SF-02 both complete. `RunContext` went from 32 flat fields to
**15 top-level attributes** (10 flat + 7 frozen sub-models, minus the three groups' worth of
fields), and `scripts/check_class_health.py` no longer reports `handlers/base.py` at all — the
first time since that check existed. Landed as five per-group commits plus three supporting ones
(a metric fix, a comment rewrite, and the RESERVE-gate bug fix that FR-8b uncovered).
**Next step**: nothing outstanding for TECH-006. Both sub-features are committed and the ticket
can be closed once the roadmap entries are updated.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.

---
# Red/Blue Team Review Report — SF-02 Design

## Summary
- **Target**: TECH-006 SF-02 design (FR-6 through FR-12, AD-5/AD-6/AD-7, the 6-sub-model decomposition)
- **Cycles**: 2
- **Findings**: 5 (Cycle 1) + 2 (Cycle 2) = 7
- **Critical/High fixes applied**: 3

## Corrections Made
- **RED-1.1 (CRITICAL)**: Pydantic v2's default `extra="ignore"` means a missed migration at a
  RunContext *construction* call site (as opposed to attribute access) would silently drop the old
  kwarg with zero error — verified empirically (`Foo(a=2, b=999)` constructs fine, `b` vanishes).
  Added FR-12: `extra="forbid"` on `RunContext` and all 6 sub-models. Confirmed safe — grepped for
  any `RunContext(**...)` dynamic-kwargs construction in production; none exists, every site uses
  explicit keyword arguments.
- **RED-1.2 (HIGH)**: The original commit-boundary plan was purely additive (Commit 1: add all 6
  sub-models, old flat fields still present; later commits: migrate group-by-group). This creates a
  window, spanning multiple commits, where both the old and new field for the same data exist
  simultaneously with nothing keeping them in sync — a call site migrated to the new path and one
  still reading the old path would silently diverge, not fail loudly. Restructured: each commit now
  adds a group's sub-model, migrates every consumer, AND removes the old flat field(s) together —
  never leaving a stale duplicate alive across a commit boundary.
- **RED-1.3 (CRITICAL)**: `runner_utils.execute_run`/`execute_in_sandbox` use plain `copy.copy()`
  (verified: not Pydantic's `.model_copy()`) for worktree isolation — a **shallow** copy, meaning
  `copied.isolation` is the SAME `IsolationPolicy` instance as `original.isolation`, not a copy of
  it. Today's code (`isolated_context.execution_root = wt_path`) is safe under shallow copy because
  reassigning a flat attribute on the copy only rebinds it on the copy's own `__dict__`. After
  `execution_root` moves inside `IsolationPolicy`, the equivalent
  `isolated_context.isolation.execution_root = wt_path` would MUTATE THE SHARED INSTANCE, silently
  corrupting the original context's isolation state too. Added NFR-8: any isolated-copy mutation of
  a grouped field must construct a new sub-model via `.model_copy(update={...})` and reassign the
  whole attribute, never mutate a nested sub-model's field in place on a shallow-copied context.

## Accepted Risks / Cleared Checks
- **RED-1.4 (checked, cleared)**: Does moving fields into nested sub-models break any consumer that
  serializes the whole `RunContext` (`model_dump()`/`model_dump_json()`), expecting the old flat
  JSON shape? Grepped — zero matches anywhere in `src/`. RunContext is never serialized as a whole.
  Not a risk; no fix needed.
- **RED-1.5 (MEDIUM, accepted)**: `GraphContext` mixes fields with real production writers
  (`topology`, `api_contract_paths`) and fields with zero production writers today
  (`stale_nodes`, `workspace_roots`) in one sub-model — a future reader could assume all 4 are
  equally live. Accepted: the sub-model's own docstring will state which fields are currently
  always-`None` in production and why (real half-built feature, not dead code) — a documentation
  fix, not a structural one.

## Open Question (Cycle 2, HITL) — ✅ RESOLVED 2026-08-06: Option 1 (frozen), see AD-8

### 🔴 RED-2.1: Should the new sub-models be `frozen=True`?
**Category**: Robustness & Edge Cases (extends RED-1.3)
**Severity**: MEDIUM
**Finding**: NFR-8's fix (use `.model_copy(update=...)`, never mutate a nested sub-model field in
place) relies on developer discipline — nothing stops a *future* change from reintroducing the
exact shallow-copy bug RED-1.3 found by writing `context.isolation.execution_root = x` directly.
Making the 6 sub-models `frozen=True` would make direct mutation raise immediately, closing the bug
class structurally rather than by convention.
**Trade-off**: `hydration.py`'s current write pattern for `plan`/`decomposition`
(`context.plan = ...`, direct mutation) would ALSO need to become
`context.plan_context = context.plan_context.model_copy(update={"plan": ...})` if `PlanContext` is
frozen — a bigger call-site change than the isolation-copy scenario alone, and a change to FR-10's
"unchanged" contract (the resulting *value* stays identical, but the *write mechanism* changes).

**Options**:
1. **Frozen sub-models** — closes the bug class structurally; costs an extra rewrite of
   `hydration.py`'s two write sites (`plan`, `decomposition`) to use `model_copy`.
2. **Mutable sub-models (as originally proposed)** — smaller diff, relies on NFR-8 + code review /
   the tests this ticket adds to catch a future regression, not the type system.

**Recommendation**: Option 1 (frozen) — the two extra `hydration.py` call sites are cheap relative
to structurally eliminating an entire bug class that already bit this exact codebase once (this
review). **This is presented to the user as an open decision, not decided unilaterally — the
Phase 6 HITL gate below asks for it explicitly.**

**No further findings below the continuation thresholds in Cycle 2** (0 CRITICAL, 0 HIGH, 0 MEDIUM
beyond RED-2.1 itself, 0 LOW) — review complete.

*(End of Red/Blue Team Review Report)*
