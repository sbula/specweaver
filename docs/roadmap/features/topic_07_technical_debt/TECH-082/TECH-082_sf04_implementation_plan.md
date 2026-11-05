# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-04: Runner seams]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-04 — Runner seams
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf04_implementation_plan.md
- **Status**: APPROVED

## Scope

The runner's helper functions use one typed protocol instead of `runner: Any` and its private
fields; each handler output key the engine reads is named once. FRs: **FR-7, FR-8**. NFRs carried:
NFR-1, NFR-2, NFR-4. Kind: `refactor`. Depends on: none.

Today (re-measured 2026-11-05):

**FR-7.** 20 functions take `runner: Any` (`step_execution.py` 14, `session.py` 4, `approval.py:69`,
`fan_out.py:47`, `sandboxed_execution.py:58`). An AST scan of `core/flow/engine` finds 60 reads or
writes of another object's `_`-prefixed attribute, all on the runner:

| Module | Private members it touches |
|---|---|
| `step_execution.py` (39) | `_context`, `_emit`, `_log`, `_persist`, `_store`, `_pipeline`, `_registry`, `_gate_evaluator`, `_router_evaluator`, `_session_kept`; plus `getattr(runner, "_session_active", False)` at `:204,212` |
| `session.py` (16) | `_context` (read and rebound), `_emit`, `_persist`, `_store`, `_execute_loop`, `_session_active`, `_session_kept` (both written) |
| `approval.py` (4) | `_context`, `_emit`, `_log`, `_persist` |
| `sandboxed_execution.py` (1) | `_context` |

`PipelineRunner.__init__` (`runner.py:77-106`) never sets `_session_active` or `_session_kept`; only
`session.execute_run` does, so `step_execution` reads the first through `getattr(..., False)`.
`fan_out.run_fan_out` (`fan_out.py:46`) and `PipelineRunner._setup_sandbox_caches`
(`runner.py:144`) have no caller in `src/` or `tests/`.

**FR-8.** The engine reads five handler output keys as literals:

| Key | Engine reads | Handlers write | Other readers |
|---|---|---|---|
| `plan` | `hydration.py:121` (already `DECOMPOSITION_PLAN_KEY`, `hydration.py:38`) | `decompose.py:105,121` (imports it) | — |
| `plan_path` | `hydration.py:145` | `generation.py:440` | — |
| `results` | `step_execution.py:482` | `validation.py:129,367`, `standards.py:90,100,122`, `arbiter.py:114,217` | `generation.py:68`, `interfaces/api/v1/implement.py:141`, `workflows/implementation/interfaces/cli.py:78`, `workflows/drafting/interfaces/cli.py:125`, `assurance/standards/interfaces/cli.py:98` |
| `verdict` | `gates.py:134`, `telemetry.py:64` | `review.py:444`, `arbiter.py:113,199,216`, `gates.py:125` (the engine's own RESERVE park) | `workflows/drafting/interfaces/cli.py:141` |
| `files_touched` | `handover.py:57` | **nothing** | — |

`pipeline_engine_guide.md:412-424` tells handler authors to return `files_touched`; no handler does,
so every saved handover has `files_touched: []`. The handover tests feed it by hand
(`test_handover.py`, `test_handover_persistence.py`).

## Decided by the user (Phase 4)

### F-1 (HIGH) How the protocol's members get public names — A `[agreed 2026-11-05]`

FR-7 forbids an engine module to read another object's `_` field, so the members the helpers use
need public names. 26 test files read the same fields today (`runner._context` 24 hits in 10 files,
`_registry` 11, `_store` 11, `_log` 9, `_pipeline` 6, `_execute_loop` 4, others ≤2).

- **A.** Rename the runner's members to public names: `context`, `pipeline`, `registry`, `store`,
  `on_event`, `gate_evaluator`, `router_evaluator`, `session_active`, `session_kept`, and the methods
  `persist`, `log_event`, `emit`, `execute_loop`. The protocol names exactly these. The test lines
  that read `runner._x` change to `runner.x`; NFR-1's exception names them. Pro: one name per member.
  Con: about 70 test lines change.
- **B.** Keep the private fields and add public properties and methods on top. Pro: no test edit.
  Con: two names for each of 13 members; the tests keep reading the private ones.

Chosen: **A**. A property over a private field the class never needs is a second name for one
thing; the tests read the runner's state on purpose and can read its public state. The design's
NFR-1 exception names these test edits.

### F-2 (HIGH) `files_touched` has a reader and no writer — A `[agreed 2026-11-05]`

FR-8 says the key is named in one module "both the engine and the writing handler import". There is
no writing handler, so the memory bank never learns which files a run wrote.

- **A.** The handlers that write a file add `files_touched: [<path relative to context.project_path>]`
  to their output: `_GenerationHandler` (`generation.py:222`, code and tests), the contract step
  (`generation.py:513`) and the scenario step (`scenario.py:150,227`). Relative to the handler's own
  `project_path`, so a path inside a session worktree is still right after the worktree goes. A file
  outside `project_path` (an `output_dir` elsewhere) is recorded as given (red/blue R1). One
  integration test drives a real generate step to the saved handover, red first. Behaviour change:
  the design's NFR-1 gets FR-8 added to its list of FRs that may change behaviour.
- **B.** Declare the key and add no writer. The guide keeps a promise nothing keeps; record the gap in
  `.agents/STATE.md` "Still missing".

Chosen: **A**. Three small writes make a delivered promise true (`D-INTL-06` FR-8, `B-INTL-09`
NFR-5: "files touched"). The design's NFR-1 now lists FR-8's `files_touched` writers as a behaviour
change.

> [!NOTE]
> Corrected in dev (2026-11-05): the scenario steps write no `files_touched`. Task memory reaches the
> next coder prompt, and a scenario file's name would tell the coder that a scenario side exists
> (`B-FLOW-01`). The writers are `generate+code`, `generate+tests` and `generate+contract`, which
> use the path the step chose (`output_path`), not the generator's return value.

## Findings settled without a user choice

### F-3 (MEDIUM) Where the protocol lives

New `core/flow/engine/runner_port.py`, beside `handler_port.py` (the same idea for handlers):
`class RunnerPort(Protocol)`, `@runtime_checkable`, naming the F-1 members with their types. All
types are `TYPE_CHECKING` imports (`PipelineDefinition`, `StateStore`, `HandlerLookup`,
`GateEvaluator`, `RouterEvaluator`, `RunContext`, `PipelineRun`), so it adds no import at run time
and no cycle. `context`, `session_active` and `session_kept` are plain attributes, not read-only
properties: `session.py` writes them (R3). `execute_run(self, …)` and `run_one_step(self, …)` in `runner.py` make mypy check that
`PipelineRunner` satisfies it.

### F-4 (MEDIUM) `__init__` sets both session flags

`PipelineRunner.__init__` sets `session_active = False` and `session_kept = False`.
`step_execution` reads `runner.session_active` directly; the two `getattr` calls go.

### F-5 (MEDIUM) Where the output keys live

New `core/flow/engine/step_outputs.py`: `PLAN`, `PLAN_PATH`, `RESULTS`, `VERDICT`, `FILES_TOUCHED`
(`Final[str]`), each with a one-line comment naming its value type. `DECOMPOSITION_PLAN_KEY` moves
here as `PLAN` (no alias, AD-6). Beside `state.py`, where `StepResult.output` is declared; the
handlers, `interfaces/api`, and the three CLI modules above already depend on `core.flow.engine` in
`tach.toml`, so no edge is added. `run_state` was rejected: the keys belong to `StepResult`, not to
`RunContext`, and `run_state` does not depend on the engine.

### F-6 (MEDIUM) The guards

- `tests/unit/core/flow/engine/test_runner_seams.py`: no engine module reads or writes another
  object's `_`-prefixed attribute (AST: `x._name` with `x` not `self`/`cls`, and `getattr`/`setattr`/
  `hasattr`/`delattr` with a literal `"_name"`); every engine function with a `runner` parameter
  annotates it `RunnerPort`; a fresh `PipelineRunner` is a `RunnerPort` and has both session flags
  `False`.
- `tests/unit/core/flow/engine/test_step_output_keys.py`: the five keys appear as a literal output key
  (dict key, `.get`/subscript/`in` argument) nowhere in `core/flow` outside `step_outputs.py`, nor in
  the four outside readers. Three non-output uses are allowed by name, each with its reason:
  `display.py` `"verdict"` (a `gate_result` event argument), `review.py` `_judge_conflicts`'s
  `model_copy(update={"verdict": …})` (a `ReviewResult` field), `drift.py` `"plan_path"` (a step
  param). The same helper finds f-strings and every literal form.

### F-7 (LOW) Two dead functions in the touched files go

`fan_out.run_fan_out` and `PipelineRunner._setup_sandbox_caches` have no caller. Typing them under
FR-7 would keep code nothing runs. They are removed; `fan_out.py`'s docstring is corrected.

### F-8 (LOW) Values stay literals

`gates.py:134` compares the verdict to `"accepted"`. That is a value, not a key (FR-8 names keys);
the engine may not import `workflows/review` (`ReviewVerdict`). It stays.

### F-9 (LOW) Two commit boundaries

CB-1 FR-7 (interior), CB-2 FR-8 (closes SF-04). They touch different lines; each is safe alone.

### Phase 3 (architecture), no violation

| Mechanism | `runner_port.py` | `step_outputs.py` |
|---|---|---|
| I/O & state | none | none |
| Execution | none | none |
| LLM | none | none |
| Dependencies | `TYPE_CHECKING` only, all inside `core/flow/engine` and `run_state` | none |
| Domain | the runner's seam (engine purpose: "runs a pipeline") | step results (same) |

No new tach edge, no cycle (both modules import nothing at run time). Zoom-out: `handler_port.py` is
the precedent for a port in the engine; no output-key module exists (`feedback.py` holds
`RunContext.feedback` keys, a different object).

## Decisions (no user choice needed)

### D-1 Mutants (NFR-4)

58 corpus records point at files this SF changes (B-FLOW-05 13, D-EXEC-02 5, C-EXEC-06 4, …). Only
those whose symbol body changes go stale. After each boundary's green step: `stale_mutants.py`,
re-run each stale one with the scratch rerun script, refresh only those that still object. New
campaign TECH-082 FR-7 / FR-8, listed per boundary.

### D-2 Which documents change

- `pipeline_engine_guide.md`: the runner protocol (§ on helpers), output keys from `step_outputs.py`,
  §11 `files_touched` names the writers (F-2 A).
- `layer_isolation_and_di.md`: `RunnerPort` beside `HandlerLookup`.
- `agent_memory_state_tracking.md:189`: which steps write `files_touched` (F-2 A).
- Plans, walkthroughs and analyses that name the old members stay as written.

### D-3 Out of scope

- Private reads outside the engine (`handlers/scenario.py` `ScenarioGenerator._extract_req_ids`,
  `core/flow/interfaces/cli.py` `_core._require_active_project`): FR-7 names the engine.
- Keys the engine does not read (`generated_path`, `findings`, …).

## Path List rows this SF owns

None of P-1..P-12. The seam this SF creates (F-2 A): a file-writing handler's output → the engine's
handover → the memory bank. It is proven at integration tier in CB-2.

## Commit Boundaries

### CB-1 (interior): the runner protocol — FR-7

| # | Task | Files |
|---|---|---|
| T1 red | `test_runner_seams.py`: the four checks of F-6 (red: 60 private reads, 20 `Any`, no `RunnerPort`, no flags) | tests |
| T2 green | `runner_port.py`; runner members public (F-1); `__init__` flags; helpers typed `RunnerPort` | `runner.py`, `step_execution.py`, `session.py`, `approval.py`, `sandboxed_execution.py`, `runner_port.py` |
| T3 | remove `run_fan_out`, `_setup_sandbox_caches` (F-7) | `fan_out.py`, `runner.py` |
| T4 | test lines `runner._x` → `runner.x` (F-1 A), only for the 13 members; `_save_handover`, `_finalize`, `_spend_budget`, `_flush_telemetry`, `_open_task`, `_current_run_id`, `_memory_task`, `_task_id` stay private and their tests do not change (R2) | ~26 test files |
| T5 | mutants (D-1); FR-7 campaign: `session-flag-unset` (drop the `__init__` flag), `private-read-back` (`runner._context`), `helper-takes-any` (one `runner: Any`) | corpus |

**Done when**: the guard is green; `mypy src/specweaver` is clean; each FR-7 mutant objects.

### CB-2 (closes SF-04, HITL): output keys named once — FR-8

| # | Task | Files |
|---|---|---|
| T6 red | `test_step_output_keys.py` (F-6); with F-2 A, `tests/integration/core/flow/engine/test_files_touched_reach_handover.py`: a real generate step, then the run's saved handover lists the file (red: empty) | tests |
| T7 green | `step_outputs.py`; engine readers (`hydration`, `step_execution`, `gates`, `telemetry`, `handover`); writers (`decompose`, `generation`, `validation`, `standards`, `arbiter`, `review`, `gates`); outside readers (4 files, `generation.py:68`) | as listed |
| T8 | F-2 A writers (`generation.py:222,513`, `scenario.py:150,227`) | handlers |
| T9 | mutants; FR-8 campaign: `plan-path-by-hand`, `results-key-renamed` (one writer spells it differently → the persistence test fails), `files-touched-dropped` (F-2 A); docs (D-2) | corpus, docs |

**Done when**: both tests green; each FR-8 mutant objects; `stale_mutants.py` reports none.

## Research Notes

- `PipelineRunner` is built at 15 top-level sites plus `spawn`; all pass keyword arguments, so
  renaming fields changes no constructor call.
- `context.run.pipeline_runner` (handlers `decompose.py`, `dual_pipeline.py`) uses only `spawn` and
  `run`, both public already.
- `core/flow/engine` has no `[[interfaces]]` entry in `tach.toml`; new modules need none.
- `GateEvaluator.evaluate` mutates `attempts`; unchanged.
- `MagicMock` runners in tests still satisfy any attribute read; the protocol is checked by mypy on
  `src/`, and at run time only by the `isinstance` test.
</content>
</invoke>

## Red/Blue (Phase 5), 2 cycles

- R1 (MEDIUM, fixed) F-2 A: `relative_to(project_path)` raises for a file written outside the project
  (`output_dir`). Such a file is recorded as given.
- R2 (MEDIUM, fixed) T4 did not say which private members stay. Only the 13 protocol members become
  public; the runner's own helpers stay private, and so do their tests.
- R3 (LOW, fixed) A read-only property in the protocol would make mypy refuse `session.py`'s writes.
  The three written members are attributes.
- R4 (LOW) The CB-2 integration test needs a model: it uses `tests/scripted_llm.py` (`doubled_llm`),
  no network.
- R5 (LOW) A test that patches an old name (`patch.object(PipelineRunner, "_persist")`) fails loudly
  with `AttributeError` after the rename, so no patch goes silent.
- R6 (LOW) `session.execute_run`'s `run: Any` and `execute_in_sandbox`'s `step_def: Any, run: Any` sit
  on the same lines T2 edits; they get `PipelineRun` / `PipelineStep`. mypy proves them.
- Cycle 2: challenged R1 (an absolute path reaches the next prompt through the memory bank): it is the
  user's own `output_dir`, already in their config; accepted. Challenged the F-6 guard (could it flag a
  legitimate `module._private` use later?): it names the line; the fix is a public name. No new
  finding above LOW.

## Backlog

None.
