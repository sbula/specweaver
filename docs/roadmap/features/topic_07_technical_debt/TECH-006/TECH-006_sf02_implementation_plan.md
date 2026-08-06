# Implementation Plan: Context Loading Pipeline Refactoring [SF-02: Reduce RunContext God Object]
- **Feature ID**: TECH-006
- **Sub-Feature**: SF-02 — Reduce `RunContext` God Object
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_sf02_implementation_plan.md
- **Status**: APPROVED

## Research Notes

The design document's own "SF-02 Research" section (field-by-field map of all 32 fields — who
writes, who reads, existing comment-based grouping hints, the shallow-copy lifecycle trace) and its
Red/Blue report (2 cycles, 3 Critical/High fixes: `extra="forbid"`, per-group-atomic commits,
frozen sub-models) are the Phase 0-3 research for this plan — not repeated here in full. This
section adds only NEW, implementation-level facts found while turning that design into concrete
tasks.

**File placement**: the 6 new sub-model classes (`ModelAccess`, `IsolationPolicy`, `PlanContext`,
`GraphContext`, `RunHandle`, `AnalysisContext`) go in `core/flow/handlers/base.py`, alongside
`RunContext` itself (currently 258 lines). Considered moving them to a new sibling file instead —
rejected: `topic_07_technical_debt.md`'s TECH-015 entry explicitly flags `base.py` as *also* its own
target ("`RunContext`, `_now_iso`, `_error_result` and `_build_base_prompt` do not [belong in a
`base`]... coordinate with TECH-006, do not let the two collide") — TECH-015 hasn't started (🔴),
and preempting its own file-boundary decision by inventing a new file now risks exactly the
collision that note warns against. Keeping the sub-models alongside `RunContext` in the same file
they're extracted from is the smaller, most reversible move; TECH-015 can relocate all of it
together later, once, with full context.

**`AnalysisContext.analyzer_factory` typing**: `RunContext.analyzer_factory` is already `Any`
today specifically "to avoid import issues" (existing comment) — `AnalyzerFactoryProtocol` lives in
`workspace.context.analyzer_protocols`, which is NOT in `core.flow`'s `context.yaml` `consumes`
list. Existing precedent elsewhere in the codebase (`assurance/graph/hasher.py`,
`assurance/standards/discovery.py`) imports it only under `TYPE_CHECKING`. `AnalysisContext` keeps
the field `Any`-typed, matching current behavior exactly — introducing a real runtime import here
would be a NEW boundary question outside this ticket's scope, not something SF-02 decides.

**Pydantic `frozen=True` + nested nullable defaults**: verified directly that a frozen Pydantic v2
model's *own* fields can still be `None`-defaulted normally (frozen prevents attribute
*reassignment* post-construction, not `None` as a valid value) — no conflict with fields like
`IsolationPolicy.execution_root: Path | None = None`.

## Resolved Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| D-1 | Sub-model file placement | `core/flow/handlers/base.py`, alongside `RunContext` | See Research Notes — avoids preempting TECH-015's own file-boundary decision for this exact file. |
| D-2 | `AnalysisContext.analyzer_factory` typing | Stays `Any`, `TYPE_CHECKING`-only reference if needed for docs | Matches existing precedent and today's own reason for `Any` (avoid a new runtime import/boundary question outside SF-02's scope). |
| D-3 | Sub-model field defaults | Every sub-model field keeps its exact current default (`None`, `[]` via `default_factory`, `False`, etc.) — no default changes, only relocation | Zero behavior change is the whole point (NFR-1); changing a default is a behavior change hiding inside a "just move it" commit. |
| D-4 | Test file organization | **Corrected during this plan's own Phase 5 Red/Blue review** — `tests/unit/core/flow/handlers/test_base.py` (4 tests) and `test_base_analyzer_factory.py` (1 test) already exist and already exercise fields this SF moves or deletes. New sub-model tests EXTEND `test_base.py` (no new file); its 4 existing tests get updated in place, in the commit that touches their field(s) — see per-commit Test rows below for exactly which. `test_base_analyzer_factory.py`'s one test updates in Commit 3. | The original plan claimed "no dedicated test file — confirmed via glob" without actually running the glob; it was wrong. Extending existing coverage in place (not duplicating into a parallel file) is both more correct and the established convention. |
| D-5 | `GraphContext` docstring (RED-1.5 from the design's Red/Blue) | Class docstring explicitly states: "`stale_nodes` and `workspace_roots` currently have real readers but no production writer — a half-built feature seam, not dead code; do not assume every field here is populated in every run." | Resolves the design's accepted-risk finding at the point future readers will actually see it. |

## Proposed Changes (by commit boundary, per the design's already-approved sequencing)

### Commit 1 — `IsolationPolicy`
| File | Change |
|---|---|
| `core/flow/handlers/base.py` | Add `IsolationPolicy(BaseModel)` (`frozen=True`): `enforce_isolation: bool = False`, `execution_root: Path \| None = None`, `session_isolation: bool = False`, `allowed_paths: list[str] = Field(default_factory=list)`, `dal_level: Any = None`. Add `RunContext.isolation: IsolationPolicy = Field(default_factory=IsolationPolicy)`. Remove the 5 flat fields. Set `extra="forbid"` on both `RunContext.model_config` and the new sub-model's `model_config` (FR-12 — done once, here, applies to every subsequent commit's new sub-model too). |
| `core/flow/engine/runner_utils.py` | `apply_session_policy`, `execute_run`, `execute_in_sandbox`, `_dal_requires_isolation`, `resolve_should_isolate` — every read/write of the 5 fields becomes `context.isolation.<field>` / `context.isolation = context.isolation.model_copy(update={...})` (NFR-8 — the isolated-copy mutation of `execution_root` specifically). |
| `core/flow/interfaces/cli.py` | `sw run`/`sw resume` construction + post-construction writes (`enforce_isolation`, `llm_router` — no, `llm_router` is Commit 3; only `enforce_isolation` here) migrated. |
| `core/flow/engine/runner.py` | `self._context.dal_level = ...` (line 98) → `self._context.isolation = self._context.isolation.model_copy(update={"dal_level": ...})`. |
| `core/flow/handlers/validation.py`, `core/flow/handlers/bash_action.py` | `context.execution_root` → `context.isolation.execution_root` (2 real read sites). |
| Tests | Every `RunContext(...)` construction in `tests/` passing any of the 5 fields updated to `isolation=IsolationPolicy(...)`. `test_base.py::test_run_context_isolation_fields_default` updated in place (`context.execution_root`/`context.enforce_isolation` → `context.isolation.execution_root`/`context.isolation.enforce_isolation`). New in `test_base.py`: `TestIsolationPolicy` (frozen-mutation raises `ValidationError`, `model_copy` produces an independent instance leaving the original untouched — the direct NFR-8 regression test, using a real `execute_in_sandbox` call per the Test Plan below — and defaults match today's). |

### Commit 2 — `PlanContext`
| File | Change |
|---|---|
| `core/flow/handlers/base.py` | Add `PlanContext(BaseModel)` (`frozen=True`): `plan: str \| None = None`, `decomposition: str \| None = None`. Add `RunContext.plan_context: PlanContext = Field(default_factory=PlanContext)`. Remove `plan`/`decomposition` flat fields. Docstring keeps the existing AD-1 note (two distinct concepts, deliberately two fields) verbatim, updated only to reflect the new nesting. |
| `core/flow/engine/hydration.py` | Both writers (`plan`/`decomposition` set-on-success, clear-on-`FAILED`/`ERROR`) become `context.plan_context = context.plan_context.model_copy(update={...})` (AD-8/FR-10 — value unchanged, write mechanism changed). |
| `core/flow/handlers/generation.py`, `core/flow/handlers/decompose.py` | Reads (`context.plan`, `context.decomposition`) become `context.plan_context.plan`, `context.plan_context.decomposition`. |
| Tests | Construction-site updates. New in `test_base.py`: `TestPlanContext` + `hydration.py`'s existing tests re-verified for the same clear-on-failure behavior, now via `plan_context`. |

### Commit 3 — `RunHandle` + `AnalysisContext` + `ModelAccess`
| File | Change |
|---|---|
| `core/flow/handlers/base.py` | Add `RunHandle(BaseModel)` (`frozen=True`): `run_id: str \| None`, `pipeline_runner: Any = None`, `task_id: str \| None = None`. Add `AnalysisContext(BaseModel)` (`frozen=True`): `analyzer_factory: Any = None`, `parsers: Any = None`. Add `ModelAccess(BaseModel)` (`frozen=True`): `llm: Any = None`, `config: Any = None`, `llm_router: Any = None`. (Verified empirically: `Any`-typed fields need no `arbitrary_types_allowed` — none of the 6 new sub-models set it, only `RunContext` itself keeps its existing flag, untouched, matching D-3's "no incidental changes" rule.) Add all 3 `RunContext` attributes. Remove the 8 flat fields (`run_id`, `pipeline_runner`, `task_id`, `analyzer_factory`, `parsers`, `llm`, `config`, `llm_router`). `model_post_init`'s `parsers` default-injection (FR-9) moves to operate on `self.analysis.parsers`, via `self.analysis = self.analysis.model_copy(update={"parsers": ...})`. |
| `core/flow/engine/runner.py` | Step-loop stamping (`run_id`, `step_records` [deleted, Commit 5], `pipeline_runner`) → `self._context.run = self._context.run.model_copy(update={...})`. `DALResolver` init unaffected (that's `isolation.dal_level`, Commit 1). |
| `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`, `assurance/standards/interfaces/cli.py`, `assurance/validation/interfaces/cli_drift.py` | Construction-site kwargs for `llm`/`config`/`analyzer_factory` → `model=ModelAccess(llm=..., config=...)`, `analysis=AnalysisContext(analyzer_factory=...)`. `llm_router = ModelRouter(...)` assignment → `context.model = context.model.model_copy(update={"llm_router": ...})`. |
| `core/flow/handlers/decompose.py`, `core/flow/handlers/dual_pipeline.py` | `context.pipeline_runner` reads (FR-11, access pattern preserved) → `context.run.pipeline_runner`. |
| 9 handlers reading `llm`/`config` (`draft, decompose, arbiter, scenario, review, lint_fix, generation, standards, drift`) | `context.llm` → `context.model.llm`, `context.config` → `context.model.config` (widest fan-out of any group — mechanical but touches the most files). |
| Tests | `test_base.py::test_run_context_builds_project_metadata` and `::test_run_context_graceful_degradation` updated in place (`RunContext(llm=llm, config=config, ...)` → `RunContext(model=ModelAccess(llm=llm, config=config), ...)`). `test_base_analyzer_factory.py::test_run_context_accepts_analyzer_factory` updated (`analyzer_factory=dummy_factory` → `analysis=AnalysisContext(analyzer_factory=dummy_factory)`). Construction-site updates across the largest test-file set of any commit (9 handlers' worth). New in `test_base.py`: `TestRunHandle`, `TestAnalysisContext`, `TestModelAccess`. |

### Commit 4 — `GraphContext`
| File | Change |
|---|---|
| `core/flow/handlers/base.py` | Add `GraphContext(BaseModel)` (`frozen=True`): `topology: Any = None`, `stale_nodes: set[str] \| None = None`, `workspace_roots: list[str] \| None = None`, `api_contract_paths: list[str] \| None = None`. Docstring per D-5 (stale_nodes/workspace_roots have readers, no writer — real gap, not dead code). Add `RunContext.graph: GraphContext`. Remove 4 flat fields. |
| `core/flow/interfaces/cli.py` | `context.topology = topo_contexts` (`sw run` only, per design's noted asymmetry — `sw resume` unaffected, unchanged, still doesn't set it, per Non-Goals) → `context.graph = context.graph.model_copy(update={"topology": topo_contexts})`. |
| `core/flow/handlers/generation.py` | `context.api_contract_paths.append(...)` (the one in-place-mutation writer) → read-modify-`model_copy`-write pattern (`context.graph = context.graph.model_copy(update={"api_contract_paths": [*context.graph.api_contract_paths, str(output_path)]})`) — this is the one call site where frozen changes an *append* into a *replace*, not just a rename. |
| `core/flow/handlers/{decompose,review,mcp_assembler,context_assembler}.py`, `sandbox/security.py`, `core/flow/handlers/{scenario,lint_fix,validation}.py`, `core/flow/engine/staleness.py` | Reads of `topology`/`stale_nodes`/`workspace_roots`/`api_contract_paths` → `context.graph.<field>`. |
| Tests | Construction-site updates. New in `test_base.py`: `TestGraphContext` including the `api_contract_paths` append-pattern regression test. |

### Commit 5 — Delete dead fields + shorten `model_post_init`
| File | Change |
|---|---|
| `core/flow/handlers/base.py` | Delete `env_vars`, `step_records`, `pipeline_name` fields entirely (FR-8). Extract `model_post_init`'s `project_metadata` construction into `_build_project_metadata(self) -> ProjectMetadata` and the `parsers` default-injection into `_default_parsers() -> Any` (FR-9) — both private, both independently unit-testable without constructing a full `RunContext`. |
| `core/flow/engine/gates.py` | `context.feedback = {}` unaffected (flat, not moved). `pipeline_name` fallback (`gates.py:110`, `RESERVE` gate resource key) → literal `"default_pipeline"` (FR-8, confirmed always-taken fallback). |
| `core/flow/engine/runner_utils.py` | `isolated_context.env_vars = context.env_vars.copy()` (line 384) deleted outright — confirmed zero readers anywhere, this write itself has no purpose. `task_id`/`pipeline_name` fallback (line 359, worktree branch naming) → `context.run.task_id or context.run.run_id or "default"` for `task_id` (moved, kept); literal `"default_pipe"` for `pipeline_name` (deleted, per FR-8). |
| Tests | `test_base.py::test_run_context_env_vars` — this test's OWN name and purpose (proving `env_vars` and `pipeline_name` both round-trip through construction and `model_dump()`) is entirely about two fields FR-8 deletes. Deliberately removed, not "bent" — the docstring at removal states why: both fields it tested have zero production readers/writers of any real consequence (confirmed in design research), and the deletion IS the fix, not a workaround. New in `test_base.py`: `TestModelPostInitExtraction` (both extracted methods, independently, with the exact same computed output as before for representative inputs). |

## Test Plan (Adversarial Matrix)

1. **Happy path**: each sub-model constructs with its documented defaults; `RunContext()` with only
   `project_path`/`spec_path` still constructs successfully (all 6 sub-models default-factory to
   their own all-`None`/empty instance) — proves FR-6 doesn't regress the "most fields optional"
   contract every existing minimal-construction call site relies on.
2. **Boundary/Edge case**: `GraphContext.api_contract_paths`'s append-becomes-replace pattern
   (Commit 4) with 0, 1, and N existing entries. `IsolationPolicy`'s isolated-copy `model_copy`
   during a real (not mocked) `execute_in_sandbox` call, asserting the ORIGINAL context's
   `execution_root` is untouched after the isolated copy's is set (the exact NFR-8 regression this
   whole SF exists partly to prevent).
3. **Graceful degradation**: `model_post_init`'s `_default_parsers()` swallowing `BaseException`
   (existing behavior, re-verified unchanged post-extraction) when parser loading fails.
4. **Hostile/Wrong input**: constructing `RunContext(unknown_kwarg=1)` and `ModelAccess(bogus=2)`
   both raise `ValidationError` (FR-12); attempting `context.isolation.execution_root = Path("x")`
   directly (bypassing `model_copy`) raises `ValidationError` (frozen, AD-8) — the exact case RED-2.1
   worried a future regression could reintroduce, now impossible rather than merely discouraged.

## Phase 2 — Audit (condensed; design doc's Red/Blue already covered architecture/security/robustness in depth)

No NEW open questions beyond the design's own resolved decisions. Confirmed during this plan's
research: no additional external API/library involved (pure internal Pydantic model restructuring,
`pydantic` version already pinned and unchanged); no new `context.yaml` boundary crossed (D-2); no
new module created (D-1).

## Phase 3 — Architecture Verification

`core/flow/handlers/base.py` stays within `core.flow`'s own `context.yaml` boundary — no new
`consumes` entries needed for any of the 6 sub-models (all use `Any`-typed fields for anything that
would otherwise require a new cross-domain import, matching the codebase's own existing pattern for
this exact file). `tach check` re-run after each commit boundary (NFR-2, per the `dev` skill's own
per-commit gate) rather than assumed clean once at the end.

---
# Red/Blue Team Review Report

## Summary
- **Target**: TECH-006 SF-02 Implementation Plan
- **Cycles**: 2
- **Findings**: 3 (Cycle 1) + 1 (Cycle 2) = 4
- **Critical/High fixes applied**: 1

## Corrections Made
- **RED-1.1 (HIGH)**: The plan's Research Notes claimed `test_base_runcontext.py`'s target
  location had "no dedicated test file for `base.py` — confirmed via glob" — this glob was never
  actually run; it was asserted, not verified. Actually running it found **two existing files**:
  `test_base.py` (4 tests, 2 of which construct `RunContext` with fields this SF moves, 1 of which
  tests `env_vars`/`pipeline_name` — both fields FR-8 deletes) and `test_base_analyzer_factory.py`
  (1 test, constructs with `analyzer_factory=` — moves in Commit 3). Fixed D-4 and every affected
  commit's Test row: new sub-model tests extend `test_base.py` in place (no new file); the 3
  directly-affected existing tests are updated or (for the `env_vars`/`pipeline_name` one)
  deliberately removed with an explicit justification, in the commit that touches their field(s).
- **RED-1.2 (MEDIUM)**: The plan inconsistently applied `arbitrary_types_allowed=True` to 3 of the
  6 new sub-models (`RunHandle`, `ModelAccess`, `GraphContext`) and not the other 3, with no stated
  reason for the split. Verified empirically (direct Pydantic test) that `Any`-typed fields need no
  such flag at all — none of the 6 actually require it. Fixed: removed from all 6; only
  `RunContext` itself keeps its existing flag, untouched (consistent with D-3's "no incidental
  changes" rule).
- **RED-1.3 (verified, not a defect — confirms the design's central premise)**: Directly tested
  (not assumed) that `.model_copy(update={...})` on a `frozen=True` Pydantic model produces a new,
  independent instance, and that direct attribute mutation on a frozen instance raises
  `ValidationError` ("Instance is frozen") immediately. AD-8/NFR-8's entire mechanism depends on
  both of these being true — now empirically confirmed, not just assumed from Pydantic docs memory.

## Accepted Risks
- **RED-2.1 (Cycle 2, MEDIUM, accepted)**: Several of Commit 3's construction-site migrations are
  not simple token renames — `RunContext(llm=x)` → `RunContext(model=ModelAccess(llm=x))` wraps the
  value in a new constructor call, a *structural* change the refactor-safety gate's existing
  `_infer_token_rename_map` (built for TECH-005) cannot classify as safe (it only recognizes
  single-token substitutions, not value-wrapping). Whichever `--kind` this ticket declares to
  `scripts/tests.py`, a chunk of SF-02's test-file diffs will likely need the same kind of real,
  in-the-moment resolution TECH-005 hit (either a further gate extension or, more likely given
  precedent, accepting that construction-site test changes are exactly the kind of thing that
  SHOULD surface for human review rather than auto-clearing). Accepted: not solved speculatively
  here — the `dev` phase will discover the actual diffs and resolve this for real, the same way
  TECH-005's own gate issues were only found and fixed by running the real gate, not predicted in
  advance.

## Cycle Log
### 🔴 RED-1.1 / 🔵 BLUE-1.1 — see Corrections Made
### 🔴 RED-1.2 / 🔵 BLUE-1.2 — see Corrections Made
### 🔴 RED-1.3 / 🔵 BLUE-1.3 — VALID, VERIFIED — see Corrections Made
### 🔴 RED-2.1 / 🔵 BLUE-2.1 — see Accepted Risks

**Cycle 2** findings (0 CRITICAL, 0 HIGH, 1 MEDIUM < 5, 0 LOW) fall below every continuation
threshold — review complete.

*(End of Red/Blue Team Review Report)*
