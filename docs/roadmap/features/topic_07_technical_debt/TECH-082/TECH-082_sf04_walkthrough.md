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
