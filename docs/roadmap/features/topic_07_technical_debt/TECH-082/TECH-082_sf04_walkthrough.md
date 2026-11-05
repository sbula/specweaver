# Walkthrough: TECH-082 SF-04 — Runner seams

## CB-1: the runner protocol (FR-7, NFR-1, NFR-2, NFR-4)

**What changed**
- New `core/flow/engine/runner_port.py`: `RunnerPort` (`Protocol`, `runtime_checkable`) names what
  the runner's helpers use: `context`, `pipeline`, `registry`, `store`, `gate_evaluator`,
  `router_evaluator`, `session_active`, `session_kept`, `persist`, `log_event`, `emit`,
  `execute_loop`. Its imports are `TYPE_CHECKING` only.
- `PipelineRunner`: these members and `on_event` are public (F-1 A); `_log` is `log_event`.
  `__init__` sets `session_active = False` and `session_kept = False`.
- `step_execution.py` (14 functions), `session.py` (4), `approval.py`, `sandboxed_execution.py` take
  `runner: RunnerPort`; `getattr(runner, "_session_active", False)` is gone (2 sites). The `run: Any`
  and `step_def: Any` on the same signatures are `PipelineRun` / `PipelineStep`; two casts mypy now
  calls redundant are gone.
- Removed, no caller: `fan_out.run_fan_out` and `PipelineRunner._setup_sandbox_caches` (F-7).
- Tests (F-1 A, NFR-1 exception): 51 lines in 19 files. They read `runner.x` for `runner._x`; two fake
  runners (`SimpleNamespace(_store=…)`, `SimpleNamespace(_context=…)`) use the public names; one docstring no longer names `run_fan_out`. The
  runner's own helpers (`_save_handover`, `_finalize`, …) stay private, and so do their tests.
- Docs: `layer_isolation_and_di.md` (`RunnerPort` beside `HandlerLookup`), `pipeline_engine_guide.md`
  (the protocol), `scenario_pipelines.md` (the parent spawns sub-runners; `run_fan_out` was gone in
  practice), `domain_flow_engine.md` (`execute_loop`).

**Tests**
- `test_runner_seams.py` (7), red first: 63 private touches found in `approval`, `sandboxed_execution`,
  `session`, `step_execution`; 20 `runner: Any`; `runner_port` missing; no `session_active`. Green:
  no engine module touches another object's `_` field; every `runner` parameter is `RunnerPort`; a
  fresh runner is a `RunnerPort` with both flags off; `self._x` and dunders pass; `getattr`/`setattr`/
  `hasattr` with a `_` literal and `x._y` are found; `runner: Any` and an unannotated `runner` are
  found; an unparsable file is named.

**Mutants**
- 34 stale (B-FLOW-05 13, C-EXEC-06 4, D-EXEC-02 5, C-EXEC-08 3, TECH-087 3, D-INTL-06 2, and one each
  in B-FLOW-01, B-FLOW-07, D-UI-01, TECH-054, TECH-077, TECH-081) re-run before the refresh: all
  OBJECTED. 12 had their anchor text moved to the public names; 2 had their symbol renamed
  (`PipelineRunner.persist`, `PipelineRunner.execute_loop`). 0 stale.
- TECH-082 FR-7 campaign, 3 mutants, all OBJECTED: `session-flag-unset`, `private-read-back`,
  `helper-takes-any`.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `RunnerPort` | ✅ `test_runner_seams.py` (isinstance); mypy on `src/` | ✅ every engine integration test passes a real runner through the helpers | — |
| `PipelineRunner.__init__` flags | ✅ | ✅ `test_session_isolation.py` (a session step bypasses per-step isolation) | — |
| helpers typed `RunnerPort` (`step_execution`, `session`, `approval`, `sandboxed_execution`) | ✅ existing unit files | ✅ `test_session_isolation.py`, `test_session_reconcile.py`, `test_step_worktree_merge.py`, `test_runner_sandbox.py` | ✅ `test_api_gate_resumes_the_run_e2e.py`, `test_runs_keep_memory_e2e.py` |
| the guard | ✅ | — | — |

Composition: the helpers are only ever called by the runner; every integration run drives that pair
with a real `PipelineRunner`. Agreement: `HandlerLookup` is the same idea for handlers, a different
job; nothing else types the runner. No new test story: every branch touched is a rename, a removed
fallback (`getattr` default, now always set) or a removed dead function; the mutants show the guard
and the flag test fail when each comes back.

**Architecture**: `runner_port.py` sits in `core/flow/engine` beside `handler_port.py`; no run-time
import, no new tach edge, no cycle. `tach check` passes.

**Red/blue (7.5)**, 2 cycles
- R1 (LOW) `runner.context` is now public, so a handler holding `context.run.pipeline_runner` could
  rebind it. Handlers use only `spawn` and `run` (grep); the underscore never stopped them either.
- R2 (LOW) `isinstance(runner, RunnerPort)` checks only that the members exist. mypy checks their
  types on `src/` at every gate.
- R3 (LOW) `on_event` is public but not in the protocol: no helper reads it, only `spawn`.
- R4 (LOW) The guard scans only `core/flow/engine`; two private reads outside it remain
  (`handlers/scenario.py`, `core/flow/interfaces/cli.py`, plan D-3).
- Cycle 2: challenged R1 (does any code outside the engine write `session_active`/`session_kept`?):
  none in `src/`. Challenged the removal of `run_fan_out` (a public name of a module with no tach
  interface): no importer in `src/`, `tests/` or `scripts/`. No new finding above LOW.

## CB-2: output keys named once; the file-writing steps write `files_touched` (FR-8, NFR-1, NFR-2, NFR-4)

**What changed**
- New `core/flow/engine/step_outputs.py`: `PLAN`, `PLAN_PATH`, `RESULTS`, `VERDICT`, `FILES_TOUCHED`,
  each with its value type. `hydration.DECOMPOSITION_PLAN_KEY` moved here as `PLAN` (no alias, AD-6).
- Engine readers use the names: `hydration` (`PLAN`, `PLAN_PATH`), `step_execution` (`RESULTS`),
  `gates` (`VERDICT`, also its own RESERVE park), `telemetry` (`VERDICT`), `handover`
  (`FILES_TOUCHED`).
- Writers: `decompose`, `generation`, `validation`, `standards`, `arbiter`, `review`. Outside
  readers: `interfaces/api/v1/implement.py`, the implementation, drafting and standards CLIs, and
  `generation._extract_prompt_feedback`.
- F-2 A: `generate+code`, `generate+tests` (one code path) and `generate+contract` add
  `files_touched: [<path relative to context.project_path>]`, through `generation._touched`. A
  file outside the project is kept as given; a `..` path is resolved first. Corrected in dev: the
  scenario steps write none (task memory reaches the coder; `B-FLOW-01`), and the path is the one the
  step chose (`output_path`), not the generator's return value (a mocked generator returns a
  coroutine).
- Test edit (import only): `test_decomposition_artifacts_integration.py` imports `PLAN` from
  `step_outputs`.
- Docs: `pipeline_engine_guide.md` (the output keys; §11 names the writers and why the scenario steps
  are not), `agent_memory_state_tracking.md` (who writes `files_touched`).

**Tests**
- `test_step_output_keys.py` (6), red first (no module; 28 literal uses): the names carry the stored
  wire values; no key spelled by hand in `core/flow` or the four outside readers, four non-output uses
  allowed by (file, function, key); a named key passes; an allowed use passes only in its own function;
  every literal form is found; an unparsable file is named.
- `test_files_touched.py` (6), red first (no `_touched`): the contract step names
  `contracts/greeter_contract.py`; a failed one names nothing; a worktree file is relative to the
  worktree; a file outside is kept as given; a climbing path is not `../…`; the scenario handlers
  name no file.
- `test_files_touched_reach_handover.py` (2, integration), red first (`[]`): a real runner, registry,
  `GenerateCodeHandler` and memory database, only the model doubled; the written file is in the task's
  handover, relative, and exists; a failed generation records none.

**Mutants**
- 18 stale (B-FLOW-01 2, B-FLOW-05 1, B-FLOW-07 2, C-FLOW-11 2, C-VAL-05 1, D-INTL-03 1, D-INTL-08 4,
  TECH-077 1, TECH-078 1, TECH-082 3) re-run before the refresh: all OBJECTED. TECH-082 FR-12
  `verdict-from-a-fixed-name` re-anchored on `VERDICT:`. 0 stale.
- TECH-082 FR-8 campaign, 4 mutants, all OBJECTED: `plan-path-by-hand`, `results-key-renamed` (20
  tests), `files-touched-dropped`, `touched-not-relative`.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `step_outputs` names | ✅ | ✅ `test_decomposition_artifacts_integration.py` (writer and hydration agree on `PLAN`) | — |
| engine readers (`hydration`, `step_execution`, `gates`, `telemetry`, `handover`) | ✅ existing unit files | ✅ `test_seam_pins.py` (`PLAN_PATH`), `test_validation_results_persistence.py` (`RESULTS`), `test_files_touched_reach_handover.py` | ✅ `test_runs_keep_memory_e2e.py` |
| `_touched` and the writers | ✅ | ✅ `test_files_touched_reach_handover.py` | — |
| the guard | ✅ | — | — |

Composition: `files_touched` is written by a handler and read by the handover; the integration test
drives that pair with both real. Agreement: one key module; the decomposition test asserts writer and
reader agree.

**Architecture**: `step_outputs.py` imports nothing; every importer already depends on
`core.flow.engine` in `tach.toml`. `tach check` passes.

**Red/blue (7.5)**, 2 cycles
- R1 (MEDIUM, fixed) The plan named the scenario steps as writers; their file names would reach the
  coder through task memory. They write none, and a test pins it.
- R2 (LOW, fixed) The decomposition test imported `PLAN` under the old name; it uses `PLAN`.
- R3 (LOW) The agentic coder can write more files than its target; only the target is named. Under-
  reporting is the safe side for a memory of facts.
- R4 (LOW) The guard allows a non-output use by (file, function, key); another literal of that key in
  the same function would pass. The four functions are small.
- R5 (LOW) `gates.passes` still compares with the value `"accepted"` (plan F-8).
- Cycle 2: challenged R3 (does a missing file mislead the next agent?): the handover says which files
  the steps named, not all changes; the next step reads the tree. Challenged `_touched` on a symlinked
  project: both sides are resolved, so they agree. No new finding above LOW.
