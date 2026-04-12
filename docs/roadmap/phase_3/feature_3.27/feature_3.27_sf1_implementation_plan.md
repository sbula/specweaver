# Implementation Plan: Multi-spec pipeline fan-out [SF-1: Topological DAG Wave Generation]
- **Feature ID**: 3.27
- **Sub-Feature**: SF-1 — Topological DAG Wave Generation
- **Design Document**: docs/roadmap/phase_3/feature_3.27/feature_3.27_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.27/feature_3.27_sf1_implementation_plan.md
- **Status**: COMPLETED

## 1. Goal

Implement the Topological DAG filtering inside `OrchestrateComponentsHandler` to classify decomposed components into mutually exclusive batches. Ensure no components run in parallel if they share physical topology impacts or logically depend on each other.

> [!TIP]
> **Dynamic Dispatch vs Static Waves**: Based on HITL feedback, the engine will use a **Dynamic DAG Dispatcher** rather than strict sequential waves. Using `graphlib.TopologicalSorter`, components are dynamically yielded for parallel execution the exact millisecond their upstream `depends_on` tasks finish. To prevent physical collisions, the dispatcher will maintain a `currently_running_impacts` set. A ready component only starts if its topological `impact_of` does not overlap with any currently running component. This solves the "straggler stalls the wave" problem.

## 2. Code Changes

### [MODIFY] `src/specweaver/workflows/planning/decomposition.py`
Add explicit fields to map sub-components directly to the `TopologyGraph` and enforce chronological execution sequence.

#### Modifications:
- In `ComponentChange`, add `target_modules: list[str] = Field(default_factory=list, description="Exact names of the context.yaml modules this component modifies.")`.
- Add a Pydantic `@field_validator('target_modules')` (or handle validation in Orchestrator) to strictly ensure these aren't empty, though we can't fully validate against the real graph here without passing context to the model.

### [MODIFY] `src/specweaver/workflows/planning/decomposer.py`
Update the prompt to instruct the LLM on producing the required topological boundaries.

#### Modifications:
- In `_DECOMPOSE_INSTRUCTION_TEMPLATE`, explicitly command the LLM to output `dependencies` for logical sequencing (e.g. "if component B uses a table created by component A, B depends on A") and `target_modules` mapped accurately from the provided TopologyContext list.
- Ensure the prompt demands exact context.yaml spelling.

### [MODIFY] `src/specweaver/core/flow/_decompose.py`
Rewrite `OrchestrateComponentsHandler` to orchestrate parallel execution via standard DAG logic instead of a bulk `asyncio.gather` list.

#### Modifications:
- **Logical Dependency Registration**: Use Python's built-in `graphlib.TopologicalSorter`. Iterate over the `components` list. If Component B specifies `Component A` in its `dependencies` array (meaning a strict logical/temporal requirement like B using a table created by A), register this directly via `sorter.add("Component B", "Component A")`.
- **The Engine Loop**: Create an `async` while loop running `sorter.is_active()`.
- **DAG Yielding**: Call `sorter.get_ready()`. The Graphlib engine internally ensures a component *never* yields until all of its logical dependencies have marked themselves `done()`. If Component A fails, `done()` is never called, and Component B is safely skipped and marked as an aborted downstream failure (satisfying FR-6).
- **Evaluate Physical Collisions**: For each *logically ready* component yielded by the sorter, query `TopologyGraph.impact_of(module)` for all its `target_modules`. Compare this against a merged set of impacts for all currently running task futures.
- If it physically collides with an active component, push it into a waiting queue to try again on the next loop tick. If there is no collision, dispatch it via `runner.run(pipeline, parent_run_id)` as an independent background `asyncio.create_task()` future.
- Since `PipelineRunner.fan_out` already exists, we will transition it or parallelize standard `.run()` calls wrapped in `asyncio.Task`.

> [!CAUTION]
> Integrating `runner.run` independently means we bypass `fan_out` bulk tracking, taking over the responsibility inside `OrchestrateComponentsHandler`. The handler must manually gather all `run_id` results and format them into `sub_runs` output array for the state database.

## 3. Backlog / Deferred
- Rate throttling (`asyncio.Semaphore()`) and generic `SW_PORT_OFFSET` configuration will be built explicitly in SF-2 and SF-3. SF-1 purely structures the chronological execution graph.

## 4. Developer Notes & Hitl Feedback Answers

1. **Topology Context Phase**: Contexts are passed during *Decomposition* step (before implementation begins). If the LLM analysis isn't deep enough, `TopologyGraph.impact_of` mathematically protects us because it recursively resolves all downstream impacts anyway. If the LLM claims a component only modifies `auth`, but `auth` ripples into `api`, the Graph automatically flags `api` as impacted.
2. **Straggler Tasks holding up waves**: The standard wave design was modified precisely to fix this. We use `graphlib.TopologicalSorter.done()` notifications. If Wave A has a straggler, any component in Wave B that *only* depended on the finished tasks of Wave A will immediately start running, maximizing throughput.

> [!IMPORTANT]
> **End of Plan**. A new agent can take this document and immediately execute `[MODIFY] _decompose.py` against the Graphlib interface without missing any details.

## 5. Execution Results
- `[x]` DAG Dispatcher successfully implemented in `_decompose.py`.
- `[x]` Integrated tests (`test_integration_starvation_and_dependency_bubble_up`, `test_integration_topological_collision_deferment`) implemented and passing correctly.
- `[x]` Full Quality Gate passed autonomously.
