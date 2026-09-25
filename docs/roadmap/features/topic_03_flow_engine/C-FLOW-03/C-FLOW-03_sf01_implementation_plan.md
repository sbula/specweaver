# C-FLOW-03 SF-01 — Topological DAG Wave Generation

**Status**: COMPLETED · **FRs owned**: FR-1, FR-6 — wave scheduling and cascading aborts (recorded
2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-18-MIG`) · **Depends on**: none · Design:
[C-FLOW-03_design.md](C-FLOW-03_design.md) §Sub-Feature Breakdown → SF-01 · Feature ID 3.27

Proof and mutants: `tests/unit/core/flow/handlers/test_decompose.py`,
`tests/integration/core/flow/engine/test_dag_orchestration_integration.py`.

## Goal

A topological DAG filter in `OrchestrateComponentsHandler` sorts decomposed components into mutually
exclusive batches. No two components run in parallel if they share topology impact or one depends on
the other.

**Dynamic dispatch, not static waves** (HITL). `graphlib.TopologicalSorter` yields a component for
parallel execution the moment its upstream `depends_on` tasks finish. A
`currently_running_impacts` set blocks physical collisions: a ready component starts only if its
`impact_of` does not overlap any running component. This removes the "straggler stalls the wave"
problem.

## Changes

1. **[MODIFY] `src/specweaver/workflows/planning/decomposition.py`** — map components to the
   `TopologyGraph`:
   - `ComponentChange` gains `target_modules: list[str] = Field(default_factory=list, description="Exact names of the context.yaml modules this component modifies.")`.
   - A Pydantic `@field_validator('target_modules')` (or validation in the orchestrator) keeps it
     non-empty; the model cannot check against the real graph without context.
2. **[MODIFY] `src/specweaver/workflows/planning/decomposer.py`** — `_DECOMPOSE_INSTRUCTION_TEMPLATE`
   tells the LLM to output `dependencies` for logical order (e.g. "if component B uses a table
   created by component A, B depends on A") and `target_modules` from the provided TopologyContext
   list, spelled exactly as in context.yaml.
3. **[MODIFY] `src/specweaver/core/flow/_decompose.py`** — `OrchestrateComponentsHandler` runs a DAG
   instead of one bulk `asyncio.gather` list:
   1. **Register dependencies** in a `graphlib.TopologicalSorter`: if Component B lists `Component A`
      in `dependencies`, `sorter.add("Component B", "Component A")`.
   2. **Loop** `async` while `sorter.is_active()`.
   3. **Yield** via `sorter.get_ready()`: a component never yields until all its dependencies are
      `done()`. If A fails, `done()` is never called; B is skipped and marked an aborted downstream
      failure (FR-6).
   4. **Check collisions**: for each ready component, `TopologyGraph.impact_of(module)` over its
      `target_modules`, against the merged impacts of all running futures.
   5. Collision → waiting queue, retried next tick. No collision → `runner.run(pipeline, parent_run_id)`
      as a background `asyncio.create_task()` future.
   6. `PipelineRunner.fan_out` exists; either transition it or run standard `.run()` calls wrapped in
      `asyncio.Task`.

> [!CAUTION]
> Integrating `runner.run` independently means we bypass `fan_out` bulk tracking, taking over the
> responsibility inside `OrchestrateComponentsHandler`. The handler must manually gather all
> `run_id` results and format them into `sub_runs` output array for the state database.

Deferred: rate throttling (`asyncio.Semaphore()`) and `SW_PORT_OFFSET` go to SF-02 and SF-03.
SF-01 only builds the execution graph.

## Tests

- `test_integration_starvation_and_dependency_bubble_up`
- `test_integration_topological_collision_deferment`

## Decisions (HITL)

1. **Topology context arrives at decomposition**, before implementation. If the LLM under-reports,
   `TopologyGraph.impact_of` still resolves every downstream impact: a component the LLM says only
   touches `auth` also flags `api` if `auth` ripples into it.
2. **Stragglers:** `graphlib.TopologicalSorter.done()` notifications let any component whose
   dependencies are finished start at once, even while another task of the same "wave" still runs.

## As built

- `[x]` DAG Dispatcher implemented in `_decompose.py`.
- `[x]` Integration tests (`test_integration_starvation_and_dependency_bubble_up`, `test_integration_topological_collision_deferment`) implemented and passing.
- `[x]` Full Quality Gate passed.

**Since moved** (noted 2026-09-25): the handler lives at `src/specweaver/core/flow/handlers/decompose.py`.
