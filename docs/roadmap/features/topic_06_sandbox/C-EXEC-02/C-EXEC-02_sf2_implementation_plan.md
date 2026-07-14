# Implementation Plan: Native CLI Action Nodes [SF-2: Pipeline Engine Integration]

- **Feature ID**: C-EXEC-02
- **Sub-Feature**: SF-2 — Pipeline Engine Integration
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_sf2_implementation_plan.md
- **Status**: APPROVED

## Scope

Wire SF-1's `BashActionAtom` into the pipeline engine: add `StepAction.BASH`/`StepTarget.SCRIPT` to the pipeline models, register a `BashActionHandler` that wraps the Atom and maps its result to a `StepResult`, and prove via integration tests that `RouterRule`/`GateDefinition`/`step_records` propagation work end-to-end for a real bash step — with no engine changes required for the last three (confirmed by research).

**FRs covered**: FR-1, FR-5, FR-6, FR-7.
**Inputs**: `BashActionAtom` from SF-1 (committed), existing `PipelineStep`/`StepHandlerRegistry`/`RunContext` machinery.
**Outputs**: A pipeline YAML file with an `action: bash` step runs end-to-end, is routable, and its output is readable by later steps.
**Depends on**: SF-1, SF-3 (both committed).

## Research Notes

- **Critical correction to the design doc**: FR-5 says step success maps to `StepStatus.COMPLETED` — **this enum value does not exist**. The real `StepStatus` (`core/flow/engine/state.py:26-35`) has `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `SKIPPED`, `ERROR`, `WAITING_FOR_INPUT` — every existing handler maps success to `StepStatus.PASSED`. (There is a *different*, real enum, `GateCondition.COMPLETED`, for gate conditions — easy to conflate with `StepStatus`, likely how the design doc's wording drifted.) This plan uses `StepStatus.PASSED` throughout.
- **`script`/`args`/`working_dir`/`timeout_seconds`/`env` live under `params:`, never as top-level `PipelineStep` fields** — corrects FR-1's imprecise wording. Confirmed with zero exceptions: `PipelineStep` (`models.py:198-217`) has no first-class fields for any handler-specific data across any existing step type; `new_feature.yaml`'s `run_tests` step demonstrates the same `params: {kind: unit, coverage: true}` nesting convention. `PipelineStep` has no `model_config`/`ConfigDict(extra=...)`, so Pydantic v2's default `extra="ignore"` applies — a step-level `script:` (instead of `params.script:`) is **silently dropped**, not rejected. Documented as a known footgun in the new dev-guide section (see Q1 resolution below); not fixed in code this SF.
- **`StepAction`/`StepTarget`/`VALID_STEP_COMBINATIONS`** (`core/flow/engine/models.py`): `StepAction` (lines 27-41) has no `BASH` member; `StepTarget` (lines 44-56) has no `SCRIPT` member. `VALID_STEP_COMBINATIONS` (lines 102-133) is a `frozenset[tuple[StepAction, StepTarget]]` — add `(StepAction.BASH, StepTarget.SCRIPT)` the same way as every other entry. `PipelineDefinition.validate_flow()` (lines 294-340)'s relevant check is a pure set-membership test against this frozenset — no logic changes needed beyond adding the tuple.
- **Exact handler template — `ValidateTestsHandler`** (`core/flow/handlers/validation.py:347-401`), the closest existing precedent for "wrap an Atom, map `AtomResult` to `StepResult`":
  ```python
  async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
      started = _now_iso()
      atom = self._get_atom(context)
      result = atom.run({...built from step.params...})
      if result.status.value == "SUCCESS":
          return StepResult(status=StepStatus.PASSED, output=result.exports,
                             started_at=started, completed_at=_now_iso())
      return StepResult(status=StepStatus.FAILED, output=result.exports,
                         error_message=result.message, started_at=started, completed_at=_now_iso())

  def _get_atom(self, context: RunContext) -> QARunnerAtom:
      from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom
      return QARunnerAtom(cwd=context.project_path)
  ```
  `BashActionAtom.run()`'s `exports` (`exit_code`, `stdout`, `stderr`, `duration_seconds` — `sandbox/execution/core/atom.py:126-131`) map directly to `StepResult.output` with **zero extra transformation** — this is exactly what FR-6/FR-7 need already present.
- **`StepHandlerRegistry`** (`core/flow/handlers/registry.py:86-129`): plain dict literal in `__init__`, keyed by `(StepAction, StepTarget)` tuple, e.g. `(StepAction.LINT_FIX, StepTarget.CODE): LintFixHandler()`. Also has a `.register(action, target, handler)` method (used by tests/extensions). New entry: `(StepAction.BASH, StepTarget.SCRIPT): BashActionHandler()`, imported at module top and added to `__all__` (lines 56-80).
- **`RunContext.step_records`/`_error_result`/`_now_iso`** (`core/flow/handlers/base.py`): `step_records: list[dict[str, Any]] | None = None` (line 68) confirmed. `_now_iso()` (lines 162-163) and `_error_result(message, started_at) -> StepResult` (lines 166-172, maps to `StepStatus.ERROR`) confirmed exact signatures — not needed by `BashActionHandler` itself since `BashActionAtom.run()` never raises (FR-13, SF-1), but available if ever needed.
- **`RouterRule`/`GateDefinition` — confirmed zero engine changes needed**: `RouterEvaluator._get_nested_field()` (`core/flow/engine/routers.py:41-51`) walks dot-notation purely against `StepResult.output: dict[str, Any]`, called from `PipelineRunner._execute_loop()` as `self._router_evaluator.evaluate(router, result.output)`. Since `output.exit_code`/`output.stdout` are already flat top-level keys, a `router: {field: "exit_code", ...}` rule works today with no code changes — confirms the design doc's FR-7 claim precisely.
- **`step_records` propagation — confirmed exact call site**: `runner.py:317`, `self._context.step_records = [r.model_dump() for r in run.step_records]`, refreshed immediately before every step's `handler.execute()` call — confirms FR-6's "no new plumbing" claim precisely.
- **`tach.toml` — no changes needed**: `core.flow` already `depends_on` the whole `specweaver.sandbox` package; SF-3 already added `execution.core`/`execution.core.atom.BashActionAtom` to the sandbox interface's `expose` list. The new `from specweaver.sandbox.execution.core.atom import BashActionAtom` in `bash_action.py` is already tach-legal.
- **Unit test template — `test_validate_tests_handler.py`** (`tests/unit/core/flow/handlers/test_validate_tests_handler.py:34-51`), exact mocking pattern:
  ```python
  with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
      mock_get.return_value.run.return_value = AtomResult(status=AtomStatus.SUCCESS, message="...", exports={...})
      result = await handler.execute(_step(), _ctx(tmp_path))
  assert result.status == StepStatus.PASSED
  ```
- **Integration test template — `test_feature_pipeline.py`** (`tests/integration/core/flow/engine/test_feature_pipeline.py`): real YAML → `PipelineDefinition.model_validate(data)` → `PipelineRunner(pipeline, ctx, registry=registry, store=store)` → `asyncio.run(runner.run())` → assert on `run.status`/`run.step_records`. Minimal `RunContext` only needs `project_path`+`spec_path`. `sample_project` fixture (`tests/integration/conftest.py:30-48`) copies a static fixture tree into `tmp_path` per test — a bash-step integration test creates `.specweaver/scripts/<name>.sh` there before running the pipeline. No existing test in this file exercises `RouterRule` end-to-end against a real `StepResult.output` — this SF's router integration test is new ground, following the same `PipelineRunner`-driven pattern.
- **`pipeline_engine_guide.md`**: no clean "add a new step type" checklist exists (the guide is a chronological narrative, §1-§11). §2 ("Designing Handlers") is stale/inaccurate (wrong `execute()` signature, references a nonexistent file layout) — fixing it is explicitly out of SF-2's scope (Guide-1 only calls for a *new* section, not an audit of existing ones). §6 ("Dynamic Flow Control — Routers") is the closest relevant precedent style to follow for the new section.

## Resolved: Q1 (Phase 4 open question)

**Resolved per user direction**: Option A — no bash-specific load-time `params.script` validation in this SF; `BashActionAtom`'s existing runtime check remains the only validation, consistent with every other step type's params being opaque until a handler runs. The `params:`-nesting footgun (silently-ignored top-level keys) is documented in the new dev-guide section instead of fixed in code.

**New ticket created**: **TECH-011** ([`docs/roadmap/features/topic_07_technical_debt/TECH-011/TECH-011_design.md`](../../topic_07_technical_debt/TECH-011/TECH-011_design.md)) tracks adding load-time `params` validation for **all** pipeline step types uniformly, as its own properly-designed feature — not a bash-specific special case. Registered in `master_story_roadmap.md`.

## Proposed Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/core/flow/engine/models.py` | `[MODIFY]` | Add `StepAction.BASH`, `StepTarget.SCRIPT`, `VALID_STEP_COMBINATIONS` entry |
| `src/specweaver/core/flow/handlers/bash_action.py` | `[NEW]` | `BashActionHandler` |
| `src/specweaver/core/flow/handlers/registry.py` | `[MODIFY]` | Import + register `BashActionHandler` |
| `tests/unit/core/flow/handlers/test_bash_action_handler.py` | `[NEW]` | Unit tests, mirrors `test_validate_tests_handler.py` |
| `tests/integration/core/flow/engine/test_bash_action_integration.py` | `[NEW]` | Real-YAML end-to-end tests: `step_records` propagation (FR-6), router dot-notation (FR-7) |
| `docs/dev_guides/pipeline_engine_guide.md` | `[MODIFY]` | New `## 12.` section for `action: bash` (Guide-1, now unblocked) |

No changes to `sandbox/execution/core/` (SF-1's own files), `tach.toml`, or any `context.yaml` — all boundary wiring is already in place from SF-3.

## `bash_action.py` — Implementation Sequence (pseudocode)

`BashActionHandler` implements the `StepHandler` protocol (`async def execute(self, step: PipelineStep, context: RunContext) -> StepResult`), cloning `ValidateTestsHandler`'s exact shape:

1. `started = _now_iso()`.
2. `atom = self._get_atom(context)` — lazy helper: `BashActionAtom(cwd=context.project_path)` (mirrors `ValidateTestsHandler._get_atom`'s lazy-construction style exactly).
3. Build the `context: dict[str, Any]` passed to `atom.run()` directly from `step.params` — pass through whichever of `script`, `args`, `working_dir`, `timeout_seconds`, `env` are present; do not fill in defaults or validate here (that's `BashActionAtom.run()`'s job, per FR-13/AD-2 from SF-1 — this handler must not duplicate that logic).
4. `result = atom.run(context_dict)`.
5. If `result.status == AtomStatus.SUCCESS`: return `StepResult(status=StepStatus.PASSED, output=result.exports, started_at=started, completed_at=_now_iso())`.
6. Else (`AtomStatus.FAILED`): return `StepResult(status=StepStatus.FAILED, output=result.exports, error_message=result.message, started_at=started, completed_at=_now_iso())`.
7. No `try`/`except` needed — `BashActionAtom.run()` never raises (SF-1's FR-13 guarantee); `BashActionHandler` inherits that guarantee for free by construction, not by re-implementing exception containment.

`registry.py` changes: import `BashActionHandler` from the new module; add `(StepAction.BASH, StepTarget.SCRIPT): BashActionHandler()` to the `_handlers` dict literal in `__init__`, in the same style as every existing entry; add `"BashActionHandler"` to `__all__`.

## Test Plan

### Unit (`test_bash_action_handler.py`, mirrors `test_validate_tests_handler.py`)

| Test | FR | Asserts |
|------|-----|---------|
| `test_success_maps_to_passed` | FR-5 | Mocked `AtomResult(status=SUCCESS, exports={"exit_code": 0, "stdout": "hi", ...})` → `StepResult.status == StepStatus.PASSED`, `output == exports` |
| `test_failure_maps_to_failed` | FR-5 | Mocked `AtomResult(status=FAILED, message="...", exports={"exit_code": 3, ...})` → `StepResult.status == StepStatus.FAILED`, `error_message == result.message` |
| `test_params_passed_through_unchanged` | FR-1 | `step.params = {"script": "x.sh", "args": ["a"], "env": {"K": "V"}}` → assert the mock atom's `run()` was called with exactly these keys, nothing added/removed/defaulted by the handler |
| `test_missing_params_key_not_defaulted_by_handler` | FR-1 | `step.params = {}` (no `script`) → handler still calls `atom.run({})` without raising or filling in a default — proves the handler doesn't duplicate `BashActionAtom`'s own validation (Q1's resolution) |

### Integration (`test_bash_action_integration.py`, mirrors `test_feature_pipeline.py`)

| Test | FR | Asserts |
|------|-----|---------|
| `test_bash_step_runs_end_to_end` | FR-1 | Real `PipelineDefinition` with one `action: bash` step, real fixture script written to `.specweaver/scripts/` in the copied `sample_project`, run via `PipelineRunner` → `run.status == RunStatus.COMPLETED`, the step's `StepRecord.result.status == StepStatus.PASSED` |
| `test_downstream_step_reads_step_records` | FR-6 | Two-step pipeline: bash step, then a step whose handler reads `context.step_records` for the bash step's name → asserts the prior step's `output.stdout` is visible |
| `test_router_branches_on_exit_code` | FR-7 | Bash step with a `router: {field: "exit_code", operator: eq, value: 0, target: "..."}` block, fixture script exits 0 → asserts the run routes to the expected target step, not the default/fallback |
| `test_router_branches_on_nonzero_exit` | FR-7 | Same router setup, fixture script exits 1 → asserts routing takes the failure path |

## FR / NFR Coverage

| ID | Covered by |
|----|-----------|
| FR-1 | `StepAction.BASH`/`StepTarget.SCRIPT`/`VALID_STEP_COMBINATIONS`; `test_bash_step_runs_end_to_end`, `test_params_passed_through_unchanged` |
| FR-5 | `BashActionHandler`'s `AtomStatus` → `StepStatus.PASSED`/`FAILED` mapping (corrected from the design doc's `COMPLETED` error); `test_success_maps_to_passed`, `test_failure_maps_to_failed` |
| FR-6 | No new code (existing `step_records` mechanism); `test_downstream_step_reads_step_records` |
| FR-7 | No new code (existing `RouterRule` mechanism); `test_router_branches_on_exit_code`, `test_router_branches_on_nonzero_exit` |

No NFRs or ADs are assigned to SF-2 — all of NFR-1 through NFR-10 and AD-1 through AD-6 belong to SF-1's `BashActionAtom` runtime behavior, already implemented and committed.

## Backlog (deferred, out of scope for SF-2)

- Fixing `pipeline_engine_guide.md` §2's stale handler-signature example — pre-existing inaccuracy, unrelated to adding the new §12 section.
- TECH-011 (load-time params validation for all step types) — its own future design, not this SF's job.
- Adding an `action: bash` example step to any of the bundled production pipelines (`new_feature.yaml`, `scenario_integration.yaml`, etc.) — the design doc's ROI section frames this as a future adoption benefit, not something SF-2 needs to retrofit now.

## Phase 5: Final Consistency Check

**5.0 Pre-check**: All 4 FRs assigned to SF-2 (FR-1, FR-5, FR-6, FR-7) are covered above. No NFRs/ADs assigned to this SF.

**5.1 Open questions**: None remaining — Q1 was resolved by explicit user direction (Option A + new TECH-011 ticket).

**5.1a Agent Handoff Risk**: A fresh agent starting only from this document has the exact existing handler to clone (`ValidateTestsHandler`, cited with line numbers), the exact enum/registry insertion points, confirmation that FR-6/FR-7 require zero engine code (only tests proving it), and the exact test templates to mirror for both unit and integration levels. The one thing to watch: `BashActionAtom.run()`'s `context` dict keys (`script`, `args`, `working_dir`, `timeout_seconds`, `env`) must be passed through from `step.params` **verbatim** — the handler must resist the temptation to add defaulting/validation logic that duplicates SF-1's `_validate_cheap()`, which is explicitly Q1's resolved design intent (keep the handler thin).

**5.2 Architecture and future compatibility**: No circular imports — `bash_action.py` imports `specweaver.sandbox.execution.core.atom.BashActionAtom`, already tach-legal per SF-3's boundary wiring, verified by the existing `qa_runner`/`git`/`code_structure`/`mcp` handlers importing their respective Atoms the identical way. Compatible with `B-EXEC-01` (Podman) and `C-EXEC-04` (concurrent git merge) — both were already confirmed compatible at the SF-1 design stage, and SF-2 doesn't change `BashActionAtom` itself, only wires it up.

**5.2a Architecture Principles**: **DDD** — stays within `core.flow`'s existing handler-per-domain convention (`handlers/bash_action.py`, one new file, matching `handlers/validation.py`/`handlers/lint_fix.py`). **KISS** — the handler is a thin, direct clone of an already-proven pattern; no new abstraction invented. **DRY** — reuses `ValidateTestsHandler`'s exact shape rather than inventing a new handler style; reuses `RouterRule`/`GateDefinition`/`step_records` entirely as-is (zero duplication of engine mechanics). **Hexagonal** — the handler is the adapter between the generic pipeline engine and `BashActionAtom`; no domain logic leaks into either direction. **Separation of Concerns** — the handler's only job is `AtomResult` ↔ `StepResult` translation; validation stays in `BashActionAtom` (SF-1), routing stays in `RouterEvaluator` (untouched), state propagation stays in `PipelineRunner` (untouched).

**5.3 Internal consistency**: All 6 proposed files are tagged correctly (2 `[NEW]`, 4 `[MODIFY]`... note: `bash_action.py` and the two new test files are `[NEW]`, `models.py`/`registry.py`/`pipeline_engine_guide.md` are `[MODIFY]` — 3 new, 3 modified). Every FR maps to a concrete code element and at least one test at the appropriate level (unit for the handler mapping logic, integration for the "zero engine changes" claims).

### Red/Blue Team Review (2 cycles run)

**Cycle 1**:
- 🔴 **HIGH**: The design doc's `StepStatus.COMPLETED` error — has this typo propagated anywhere else in the design doc or SF-1's already-committed code that would need a matching fix? **Blue**: Checked — SF-1's own code (`atom.py`) never references `StepStatus` at all (it only knows about `AtomStatus`, a different enum, correctly so per the design's own separation of concerns). The `StepStatus.COMPLETED` reference is isolated to the design doc's FR-5 prose and this plan's own correction — no code fix needed anywhere, just this plan's correct usage of `StepStatus.PASSED` going forward. VALID finding, already fully addressed by using the correct enum value throughout this plan.
- 🔴 **MEDIUM**: `test_params_passed_through_unchanged` and `test_missing_params_key_not_defaulted_by_handler` both assert "the handler doesn't add logic" — is this over-specified/testing an implementation detail rather than behavior? **Blue**: VALID — ACCEPTED as-is: this is deliberately testing a *design decision* (Q1's resolution: keep the handler thin, don't duplicate SF-1's validation), not an incidental implementation detail — a future maintainer adding "helpful" defaulting logic directly into the handler would be silently reintroducing the exact special-case validation Q1 explicitly rejected. The test is a guard against architectural drift, not overspecification.
- 🔴 **LOW**: Should the integration tests also cover a `gate:` block (not just `router:`), given `GateDefinition` is mentioned in SF-2's scope line? **Blue**: VALID, clarify: `GateDefinition`'s `condition: all_passed`/`condition: completed` logic already operates generically on `StepResult.status` (confirmed via `GateEvaluator.passes()`, checked in Phase 0 research) — no bash-specific behavior exists to test beyond what `test_success_maps_to_passed`/`test_failure_maps_to_failed` (unit level) and `test_bash_step_runs_end_to_end` (integration, implicitly exercises the default gate) already cover. Not adding a dedicated gate-specific integration test — would be redundant with existing coverage, not a real gap.

**Cycle 2**: Re-examined Cycle 1's responses plus a fresh pass — no new findings above the continuation threshold. Review converges.

**Corrections made**: None required further plan changes — all 3 Cycle 1 findings were either already correctly handled by the plan as written, or explicitly accepted as intentional (the "thin handler" tests) or non-gaps (gate coverage).

---

## HITL Gate — Approval Required

This plan is ready for your review. Summary: 3 new files, 3 modified files, all changes clone an already-proven existing handler pattern (`ValidateTestsHandler`) exactly, confirmed zero engine changes needed for FR-6/FR-7 (only tests proving it). One factual error caught and corrected from the design doc (`StepStatus.COMPLETED` → `PASSED`). Q1 resolved per your direction (Option A + new TECH-011 ticket, now registered). Red/Blue review ran 2 cycles, converged with no required plan changes.

Reply with approval to mark this plan `APPROVED` and proceed to the `dev` skill for SF-2's TDD implementation.

---

## Post-Implementation Notes (2026-07-14)

Implemented exactly as planned — no deviations from the pseudocode sequence or the Q1 resolution. One addition beyond the original Test Plan: Pre-Commit Phase 2 found that `registry.py`'s new dict entry had only implicit coverage (via the integration tests' use of a real `StepHandlerRegistry()`), so `test_registry_resolves_bash_script_to_handler` was added as a direct unit assertion.

- T1 (models.py enum/combination): as planned, plus 3 pre-existing hardcoded count assertions in `test_models.py` fixed proactively (`test_action_count`, `test_target_count`, `test_combination_count`) — would have silently regressed.
- T2 (`BashActionHandler`): as planned, exact clone of `ValidateTestsHandler`'s shape.
- T3/T4 (integration — end-to-end, `step_records`, router branching): as planned; confirmed zero pipeline-engine changes were needed. The router tests required placing each branch's target step last in a 3-step pipeline so the routing jump provably skips the other branch (adjacent branch steps would both execute sequentially after the jump — a detail not called out in the original plan's pseudocode, discovered during TDD).
- T5 (dev guide): `pipeline_engine_guide.md` §12 added; `subprocess_execution.md`'s stale "not yet implemented" note also corrected as a drive-by fix.

Full test suite: 5099 passed (unit 4532, integration 428, e2e 139), zero regressions. Pre-commit gate: ruff/mypy/C901/file-size/tach all clean.
