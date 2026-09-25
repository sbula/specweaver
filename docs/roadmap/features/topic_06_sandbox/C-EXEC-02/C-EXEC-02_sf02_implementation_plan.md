# C-EXEC-02 SF-02 — Pipeline Engine Integration

**Status**: APPROVED. Implemented 2026-07-14 (`0b9a5b29`). · **FRs owned**: FR-1, FR-5, FR-6, FR-7 ·
**Depends on**: SF-01, SF-03 (both committed) · Design: [C-EXEC-02_design.md](C-EXEC-02_design.md)
§Sub-features → SF-02

## Goal

Wire SF-01's `BashActionAtom` into the pipeline engine: `StepAction.BASH`/`StepTarget.SCRIPT`, a
`BashActionHandler` that wraps the Atom and maps its result to a `StepResult`, and integration tests
proving `RouterRule`/`GateDefinition`/`step_records` work end-to-end for a real bash step — with no
engine changes for the last three.

**Output**: a pipeline YAML with an `action: bash` step runs end-to-end, is routable, and its output
is readable by later steps.

## Where it plugs in

| Fact | Where |
|---|---|
| Success maps to `StepStatus.PASSED`. `StepStatus` has `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `SKIPPED`, `ERROR`, `WAITING_FOR_INPUT` — no `COMPLETED` (that is `GateCondition.COMPLETED`, a different enum; the design's FR-5 once conflated them). | `core/flow/engine/state.py:26-35` |
| `script`/`args`/`working_dir`/`timeout_seconds`/`env` live under `params:`, never as top-level `PipelineStep` fields — no step type has handler-specific first-class fields (cf. `new_feature.yaml`'s `run_tests`: `params: {kind: unit, coverage: true}`). `PipelineStep` has no `model_config`/`ConfigDict(extra=...)`, so Pydantic v2's default `extra="ignore"` applies: a step-level `script:` (instead of `params.script:`) is **silently dropped**. Documented in the guide (Q1), not fixed in code. | `models.py:198-217` |
| `StepAction` (lines 27-41) and `StepTarget` (lines 44-56) get `BASH`/`SCRIPT`. `VALID_STEP_COMBINATIONS` (lines 102-133) is a `frozenset[tuple[StepAction, StepTarget]]` — add `(StepAction.BASH, StepTarget.SCRIPT)`. `PipelineDefinition.validate_flow()` (lines 294-340) only tests set membership. | `core/flow/engine/models.py` |
| Handler template — `ValidateTestsHandler`, the closest "wrap an Atom, map `AtomResult` → `StepResult`" precedent (code below). `BashActionAtom.run()`'s `exports` (`exit_code`, `stdout`, `stderr`, `duration_seconds` — `sandbox/execution/core/atom.py:126-131`) become `StepResult.output` with **zero transformation**, which is what FR-6/FR-7 need. | `core/flow/handlers/validation.py:347-401` |
| `StepHandlerRegistry`: dict literal in `__init__` keyed by `(StepAction, StepTarget)`, e.g. `(StepAction.LINT_FIX, StepTarget.CODE): LintFixHandler()`; also `.register(action, target, handler)` for tests/extensions. `__all__` at lines 56-80. | `core/flow/handlers/registry.py:86-129` |
| `step_records: list[dict[str, Any]] \| None = None` (line 68); `_now_iso()` (lines 162-163); `_error_result(message, started_at) -> StepResult` (lines 166-172, maps to `StepStatus.ERROR`) — not needed, since `BashActionAtom.run()` never raises (FR-13). | `core/flow/handlers/base.py` |
| Router: `RouterEvaluator._get_nested_field()` walks dot-notation over `StepResult.output: dict[str, Any]`, called from `PipelineRunner._execute_loop()` as `self._router_evaluator.evaluate(router, result.output)`. `output.exit_code`/`output.stdout` are flat top-level keys, so `router: {field: "exit_code", ...}` works with no code change (FR-7). | `core/flow/engine/routers.py:41-51` |
| `step_records` refresh: `self._context.step_records = [r.model_dump() for r in run.step_records]`, before every `handler.execute()` — FR-6 needs no new plumbing. | `runner.py:317` |
| `tach.toml`: no change. `core.flow` already `depends_on` the whole `specweaver.sandbox` package; SF-03 added `execution.core`/`execution.core.atom.BashActionAtom` to the sandbox `expose` list. | `tach.toml` |
| `pipeline_engine_guide.md` is a chronological narrative (§1-§11), no "add a step type" checklist. §2 ("Designing Handlers") is stale (wrong `execute()` signature, nonexistent file layout) — out of scope. §6 ("Dynamic Flow Control — Routers") is the style to follow. | `docs/dev_guides/pipeline_engine_guide.md` |

`ValidateTestsHandler` shape to clone:

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

## Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/core/flow/engine/models.py` | `[MODIFY]` | Add `StepAction.BASH`, `StepTarget.SCRIPT`, `VALID_STEP_COMBINATIONS` entry |
| `src/specweaver/core/flow/handlers/bash_action.py` | `[NEW]` | `BashActionHandler` |
| `src/specweaver/core/flow/handlers/registry.py` | `[MODIFY]` | Import + register `BashActionHandler` |
| `tests/unit/core/flow/handlers/test_bash_action_handler.py` | `[NEW]` | Unit tests, mirrors `test_validate_tests_handler.py` |
| `tests/integration/core/flow/engine/test_bash_action_integration.py` | `[NEW]` | Real-YAML end-to-end tests: `step_records` propagation (FR-6), router dot-notation (FR-7) |
| `docs/dev_guides/pipeline_engine_guide.md` | `[MODIFY]` | New `## 12.` section for `action: bash` (Guide-1) |

No change to `sandbox/execution/core/` (SF-01's files), `tach.toml`, or any `context.yaml`.

**`BashActionHandler`** implements `StepHandler`
(`async def execute(self, step: PipelineStep, context: RunContext) -> StepResult`), cloning
`ValidateTestsHandler`:

1. `started = _now_iso()`.
2. `atom = self._get_atom(context)` — lazy `BashActionAtom(cwd=context.project_path)`.
3. Build the `context: dict[str, Any]` for `atom.run()` straight from `step.params`: pass through
   whichever of `script`, `args`, `working_dir`, `timeout_seconds`, `env` exist — **verbatim**, no
   defaults, no validation. Validation is `BashActionAtom.run()`'s (`_validate_cheap()`, FR-13/AD-2);
   the handler stays thin (Q1).
4. `result = atom.run(context_dict)`.
5. `AtomStatus.SUCCESS` → `StepResult(status=StepStatus.PASSED, output=result.exports, started_at=started, completed_at=_now_iso())`.
6. Else (`AtomStatus.FAILED`) → `StepResult(status=StepStatus.FAILED, output=result.exports, error_message=result.message, started_at=started, completed_at=_now_iso())`.
7. No `try`/`except` — `BashActionAtom.run()` never raises (SF-01 FR-13).

`registry.py`: import `BashActionHandler`; add `(StepAction.BASH, StepTarget.SCRIPT): BashActionHandler()`
to the `_handlers` dict literal in `__init__`; add `"BashActionHandler"` to `__all__`.

## Tests

**Unit** — `test_bash_action_handler.py`, mirrors
`tests/unit/core/flow/handlers/test_validate_tests_handler.py:34-51`:

  ```python
  with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
      mock_get.return_value.run.return_value = AtomResult(status=AtomStatus.SUCCESS, message="...", exports={...})
      result = await handler.execute(_step(), _ctx(tmp_path))
  assert result.status == StepStatus.PASSED
  ```

| Test | FR | Asserts |
|------|-----|---------|
| `test_success_maps_to_passed` | FR-5 | Mocked `AtomResult(status=SUCCESS, exports={"exit_code": 0, "stdout": "hi", ...})` → `StepResult.status == StepStatus.PASSED`, `output == exports` |
| `test_failure_maps_to_failed` | FR-5 | Mocked `AtomResult(status=FAILED, message="...", exports={"exit_code": 3, ...})` → `StepResult.status == StepStatus.FAILED`, `error_message == result.message` |
| `test_params_passed_through_unchanged` | FR-1 | `step.params = {"script": "x.sh", "args": ["a"], "env": {"K": "V"}}` → the mock atom's `run()` got exactly these keys |
| `test_missing_params_key_not_defaulted_by_handler` | FR-1 | `step.params = {}` → handler calls `atom.run({})` without raising or defaulting |

**Integration** — `test_bash_action_integration.py`, mirrors
`tests/integration/core/flow/engine/test_feature_pipeline.py`: real YAML →
`PipelineDefinition.model_validate(data)` →
`PipelineRunner(pipeline, ctx, registry=registry, store=store)` → `asyncio.run(runner.run())` →
assert on `run.status`/`run.step_records`. Minimal `RunContext` = `project_path`+`spec_path`. The
`sample_project` fixture (`tests/integration/conftest.py:30-48`) copies a fixture tree into
`tmp_path`; the test writes `.specweaver/scripts/<name>.sh` there. No earlier test exercised
`RouterRule` end-to-end against a real `StepResult.output`.

| Test | FR | Asserts |
|------|-----|---------|
| `test_bash_step_runs_end_to_end` | FR-1 | One `action: bash` step, real fixture script in `.specweaver/scripts/` of the copied `sample_project`, run via `PipelineRunner` → `run.status == RunStatus.COMPLETED`, the step's `StepRecord.result.status == StepStatus.PASSED` |
| `test_downstream_step_reads_step_records` | FR-6 | Bash step, then a step whose handler reads `context.step_records` for the bash step's name → the prior `output.stdout` is visible |
| `test_router_branches_on_exit_code` | FR-7 | `router: {field: "exit_code", operator: eq, value: 0, target: "..."}`, script exits 0 → routes to the expected target, not the fallback |
| `test_router_branches_on_nonzero_exit` | FR-7 | Same router, script exits 1 → failure path |

**Coverage.** FR-1: enums + `VALID_STEP_COMBINATIONS`; `test_bash_step_runs_end_to_end`,
`test_params_passed_through_unchanged`. FR-5: `AtomStatus` → `StepStatus.PASSED`/`FAILED`;
`test_success_maps_to_passed`, `test_failure_maps_to_failed`. FR-6: no new code;
`test_downstream_step_reads_step_records`. FR-7: no new code; `test_router_branches_on_exit_code`,
`test_router_branches_on_nonzero_exit`. NFR-1 through NFR-10 and AD-1 through AD-6 belong to
SF-01's `BashActionAtom`.

## Decisions (audit)

**Q1 — load-time `params.script` validation for bash?** Chosen by the user: **Option A** — none in
this SF. `BashActionAtom`'s runtime check stays the only validation, as every step type's params are
opaque until a handler runs. The `params:`-nesting footgun (silently ignored top-level keys) is
documented in the new guide section. **TECH-011**
([`docs/roadmap/features/topic_07_technical_debt/TECH-011/TECH-011_design.md`](../../topic_07_technical_debt/TECH-011/TECH-011_design.md))
tracks load-time `params` validation for **all** step types; registered in `master_story_roadmap.md`.

Red/Blue review (2 cycles, converged, no plan changes):

- The `StepStatus.COMPLETED` error lived only in the design's FR-5 prose — SF-01's `atom.py` knows
  only `AtomStatus`. No code fix needed.
- `test_params_passed_through_unchanged` / `test_missing_params_key_not_defaulted_by_handler` test
  Q1's design decision on purpose: they stop a future "helpful" default in the handler from bringing
  back the validation Q1 rejected.
- No gate-specific integration test: `GateDefinition`'s `condition: all_passed`/`condition: completed`
  logic works on `StepResult.status` generically (`GateEvaluator.passes()`); the unit mapping tests
  and `test_bash_step_runs_end_to_end` (default gate) cover it.

Architecture check: `handlers/bash_action.py` imports
`specweaver.sandbox.execution.core.atom.BashActionAtom` the same way the `qa_runner`/`git`/
`code_structure`/`mcp` handlers import their Atoms; tach-legal via SF-03. One file per domain, like
`handlers/validation.py`/`handlers/lint_fix.py`. Validation stays in `BashActionAtom`, routing in
`RouterEvaluator`, state propagation in `PipelineRunner` — all untouched. Compatible with
`B-EXEC-01` (Podman) and `C-EXEC-04` (concurrent git merge).

**Out of scope**: fixing guide §2's stale handler signature; TECH-011; adding an `action: bash` step
to bundled pipelines (`new_feature.yaml`, `scenario_integration.yaml`, etc.) — a future adoption
benefit, not a retrofit.

## As built (2026-07-14)

As planned — no deviations from the sequence or Q1.

- `test_registry_resolves_bash_script_to_handler` added: the registry entry had only implicit
  coverage via the integration tests' real `StepHandlerRegistry()`.
- 3 hardcoded count assertions in `test_models.py` (`test_action_count`, `test_target_count`,
  `test_combination_count`) updated for the new enum values.
- Router tests: each branch's target step sits last in a 3-step pipeline, so the jump provably skips
  the other branch — adjacent branch steps would both run in sequence after the jump.
- `pipeline_engine_guide.md` §12 added; `subprocess_execution.md`'s stale "not yet implemented" note
  corrected.

Full suite: 5099 passed (unit 4532, integration 428, e2e 139), zero regressions.
ruff/mypy/C901/file-size/tach clean.

**Since moved** (noticed 2026-09-25): `RunContext` now lives in
`core/flow/handlers/run_context.py`. Line refs above are as of the plan's date.
