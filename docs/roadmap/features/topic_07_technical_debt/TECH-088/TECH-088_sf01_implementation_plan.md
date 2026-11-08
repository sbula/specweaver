# Implementation Plan: Two Graph Engines in Two Homes [SF-01: The topology slot]
- **Feature ID**: TECH-088
- **Sub-Feature**: SF-01 — The topology slot
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_sf01_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-08)

## Scope

FR-1, FR-2, FR-3, FR-4 and FR-12. After SF-01, a run carries the module graph's three meanings in
three typed fields, filled by the run setup, and every reader reads its own field. `sw review`, code
generation and decomposition stop crashing on a project with module neighbours; a boundary's MCP
servers start; a spec whose module no `context.yaml` names logs one WARNING. SF-01 needs nothing
from SF-02..SF-04 and ships first; the user may push after it `[agreed 2026-11-08]`.

## The slot today (measured 2026-11-08)

| Reader | Expects | Gets from the run setup | Result on main |
|---|---|---|---|
| `review.py:190` `add_topology([context.graph.topology])` | one `TopologyContext` | `list[TopologyContext]` | `AttributeError` (probed) |
| `generation.py:283` same | one `TopologyContext` | a list | `AttributeError` (probed) |
| `decompose.py:74` `topology_contexts=[context.graph.topology]` | one `TopologyContext` | a list | the decomposer's `add_topology` gets a nested list |
| `decompose.py:252` `.impact_of(target_module)` | `TopologyGraph` | a list | `AttributeError` (probed) |
| `mcp_assembler.py:105-106` `getattr(…, "mcp_servers")` | `TopologyNode` | a list | `None`: no server starts (probed) |
| `review.py:68` → `ToolDispatcher` → `MCPExplorerTool(topology)` | `TopologyNode` | a list | review allows only `fs`, `ast`, `web`, so the MCP tool is never built here |
| `draft.py:161, :344` `isinstance(…, list)` | a list | a list | works |

## Commit boundaries

### CB-1 (interior): three typed fields, filled by the run setup — FR-1, FR-12

**Tests first:**
- `tests/integration/interfaces/run_setup/test_run_carries_the_module_graph.py` (FR-1). A project
  with two hand-written `context.yaml` files: `billing` consumes `payments`; `billing` declares one
  `mcp_servers` entry and one `consumes_resources` URI; the spec is `specs/billing_spec.md`.
  `build_run` gives `related_contexts` naming `payments`, `target_boundary.name == "billing"` with
  its servers and URI, and `module_graph.impact_of("payments") == {"billing"}`. A project with no
  `context.yaml` gives `None` in all three. Red: the fields do not exist.
- Same file (FR-1): a module with no neighbours still gets its `target_boundary` (MCP no longer
  needs neighbours). Red: the field does not exist.
- Same file (FR-12): `context.yaml` files exist but none is named `orphan` (spec
  `specs/orphan_spec.md`): exactly one WARNING record from `specweaver.interfaces.run_setup.builder`
  naming `orphan` and saying that topology context and MCP pre-fetch are off; no warning when
  there is no `context.yaml` at all, and none when the name matches. Red: no warning today.
- `tests/integration/core/flow/handlers/test_draft_keeps_its_contexts.py` (FR-2, draft half): a
  run from `build_run` on the `billing` project; the draft handler passes the drafter a list whose
  names are `{"payments"}`. **Green on main**: it pins the one path that works, before CB-2
  changes `draft.py`.
- `tests/unit/core/flow/run_state/test_graph_context_shapes.py` (FR-1): `GraphContext` refuses a
  list as `target_boundary` and as `module_graph` (pydantic `ValidationError`); accepts a
  `TopologyNode` and a `TopologyGraph`. Red: the fields do not exist.
- `tests/unit/test_graph_context_is_validated.py` (FR-1): no file under `tests/` builds a
  `GraphContext` with `model_copy(update=…)` (an AST walk: a `model_copy` call with an `update`
  keyword whose receiver ends in `.graph` or is a `GraphContext(...)` call). Red today: 18 call
  sites in 10 files (`test_decompose.py` 7, `test_skeleton_wiring.py` 3,
  `test_draft_feature_handler.py` 2, and one each in `test_base.py`, `test_scenario_handlers.py`,
  `test_scenario_pipeline_integration.py`, `test_orchestration_integration.py`,
  `test_dag_orchestration_integration.py`, `test_one_archetype.py`) `[agreed 2026-11-08]`.
  Mutant: one call site put back → the guard fails.
- `tests/fixtures/run_context.py`: `with_graph(context, **fields)` returns the context with a
  `GraphContext` built by `GraphContext.model_validate` from the old fields plus the new ones, so
  a wrong shape fails in the test that makes it. The 18 call sites use it.
- The existing tests that compare `graph.topology` (`test_build_run.py:120, :249`,
  `test_cli_and_api_agree.py:120`, `test_api_selector_and_new_feature.py:138-153`) compare
  `related_contexts` instead; the two-door tests also compare `target_boundary.name` and the
  module graph's node names (the graph has no `__eq__`).

**Then the code:**
1. `commons/topology_context.py`: two `runtime_checkable` protocols beside `TopologyContext`:
   one with `mcp_servers: dict[str, dict[str, Any]]` and `consumes_resources: list[str]`, one
   with `impact_of(module: str) -> set[str]`. Nothing else.
2. `GraphContext` (`core/flow/run_state/run_context.py:134`): `related_contexts`,
   `target_boundary`, `module_graph`, each `… | None = None`; `arbitrary_types_allowed=True` in its
   `model_config`. `topology` stays for now, so the readers keep working until CB-2.
3. `interfaces/run_setup/builder.py` `_topology` becomes one helper that loads the graph once and
   returns the three values; `build_run` fills the three fields and, for CB-1 only, `topology` with
   the related list as today. The FR-12 warning is logged there: a graph exists and has no node
   named `module_stem(request.spec_path)`.

**Mutants (into `TECH-088_mutants.json`):** `target_boundary` set to `None`; the FR-12 warning
removed; `module_graph` set to `None`.

### CB-2 (closes SF-01, HITL): every reader reads its own field — FR-2, FR-3, FR-4

**Tests first** (each builds its run with `build_run` on the `billing` project, never by hand):
- `tests/e2e/capabilities/assurance/test_review_prompt_names_its_neighbours_e2e.py` (FR-2):
  `sw review specs/billing_spec.md --project <dir>` with `doubled_llm` capturing the prompt;
  exit 0 and the prompt holds `payments (direct dependency)`. Red on main: the step fails with
  `AttributeError` and exits 1.
- `tests/integration/core/flow/handlers/test_generation_prompt_names_its_neighbours.py` (FR-2):
  `_generation_prompt(context, step, instructions=…)` holds the `payments` line. Red: `AttributeError`.
- `tests/integration/sandbox/mcp/test_mcp_servers_from_context_yaml.py` gains a case (FR-3): a run
  from `build_run` on a project whose target boundary declares the test server; the assembler's
  result holds the payload. Red: `None`. A second case: only the neighbour declares a server, the
  target none; the assembler returns `None` (target only, `[agreed 2026-11-08]`). Green on main for the wrong reason (the list has no attribute); it goes
  red if the assembler is pointed at the neighbours.
- `tests/integration/core/flow/handlers/test_decomposition_impact_from_the_graph.py` (FR-4):
  `_impacts_of("A", {"A": {"target_modules": ["payments"]}}, context)` is `{"A", "billing"}`; the
  decomposer receives a flat list of contexts. Red: `AttributeError`.
- The hand-built slots in `test_mcp_flow_e2e.py:139, :189`, `test_mcp_assembler.py:59`,
  `test_dag_orchestration_integration.py:128`, `test_base.py:454` and
  `test_draft_feature_handler.py:557` set the new field their reader uses.
- `tests/e2e/capabilities/assurance/test_topology_e2e.py`: the two review classes
  (`exit_code in (0, 1)`) are deleted; the new e2e replaces them. The scan tests and the
  no-`context.yaml` test stay.

**Then the code:**
1. `review.py:190`, `generation.py:283`: `add_topology(context.graph.related_contexts)` when set.
2. `decompose.py:74`: `topology_contexts=context.graph.related_contexts`; `decompose.py:252`:
   `context.graph.module_graph.impact_of(...)` when set.
3. `draft.py:161, :344`: `context.graph.related_contexts`.
4. `mcp_assembler.py:102-106`: read `context.graph.target_boundary`; no `getattr`.
5. `review.py:68` → `ToolDispatcher.create_standard_set(topology=…)` →
   `sandbox/registry.py:95` → `create_mcp_interface` → `MCPExplorerTool`: the parameter is typed
   with the boundary protocol and fed `target_boundary`; `tool.py:56, :104` read the attributes
   directly.
6. `GraphContext.topology` is deleted; `test_graph_context_shapes.py` asserts it is not among
   `GraphContext.model_fields`.
7. In the same commit as the new e2e, the two review classes of `test_topology_e2e.py` go (A5).

**Mutants:** review adds no topology; the assembler reads the first related context instead of the
target; `_impacts_of` ignores the module graph.

## Research Notes

- **Pydantic and protocols** (probed 2026-11-08): a `runtime_checkable` protocol as a field type
  needs `arbitrary_types_allowed=True`; without it the model class fails to build
  (`PydanticSchemaGenerationError`). With it, a `TopologyNode` is accepted and a list is refused
  with `ValidationError`, so a wrong shape fails where the run is built, not in a handler.
- **Tach:** `core.flow.run_state` gains no edge (the protocols are in `commons`, a utility with
  `depends_on = []`). `interfaces.run_setup` already depends on `assurance.graph`;
  `core.flow.handlers` and `sandbox` reach the protocols through `commons`.
- **Step copies:** `sandboxed_execution.py:101` and `session.py:86` use `copy.copy(context)`; the
  three fields are shared, read-only after the run setup (SF-03 freezes the graph, FR-13).
- **Resume:** `sw resume` builds the run again, so FR-12's warning appears once per run start.
- **The TopologyNode key:** `select_topology_contexts(graph, module_stem(request.spec_path), …)`
  (`builder.py:215`) already uses the stem; the target boundary is `graph.nodes.get(stem)`.
- `TECH-077_sf01_implementation_plan.md:23` names `context.graph.topology.archetype`; no source reads
  it now (grep 2026-11-08). The plan is closed history and is not edited.

## Architecture (Phase 3)

| Change | Module | Archetype / rule | Verdict |
|---|---|---|---|
| two protocols | `commons` | `pure-logic`, `forbids: specweaver/*`; uses only `typing` | ok |
| three fields | `core.flow.run_state` | no new import beyond `commons` | ok |
| the three values, the warning | `interfaces.run_setup` | already reads the module graph | ok |
| readers | `core.flow.handlers`, `sandbox` | read `commons` types only | ok |

No new tach edge, no cycle, no new module.

## Decisions (Phase 4)

All eight proposals taken by the user `[agreed 2026-11-08]`:

- **A1** The fields are `related_contexts`, `target_boundary`, `module_graph`.
- **A2** CB-1 keeps `topology` beside them; CB-2 deletes it.
- **A3** `decompose.py:74` is fixed under FR-4.
- **A4** The e2e project uses hand-written `context.yaml` files.
- **A5** The two weak review classes of `test_topology_e2e.py` are deleted **in CB-2, in the same
  commit that adds the new `sw review` e2e**, never before it.
- **A6** The sandbox MCP tool's parameter is typed and fed `target_boundary`.
- **A7** FR-12's text: "No context.yaml names module '<stem>': topology context and MCP pre-fetch
  are off for this run."
- **A8** The two-door tests compare the module graph's node names.

## Consistency and red/blue (Phase 5), 2 cycles

- Every SF-01 FR has a test that builds its run with `build_run`: FR-1 and FR-12
  (`test_run_carries_the_module_graph.py`, `test_graph_context_shapes.py`), FR-2 (the e2e, the
  generation test, the draft test), FR-3 (two cases in `test_mcp_servers_from_context_yaml.py`),
  FR-4 (`test_decomposition_impact_from_the_graph.py`). NFR-1 holds: outside the slot only the test
  doubles change. NFR-2: no tach edge.
- Fixed: the guard "no `graph.topology` in `src/`" would match the module path
  `specweaver.graph.topology` once SF-02 moves the files; the guard asserts instead that
  `GraphContext.model_fields` has no `topology`.
- Fixed: the neighbour-only MCP case claimed "no server process starts", which it cannot observe;
  it asserts the assembler returns `None`, and the mutant "read the first related context" makes
  it fail.
- Fixed: FR-12's "exactly one WARNING" counts records whose message names the stem, so an unrelated
  selector warning cannot break it.
- Closed, not accepted (the user, at approval): `model_copy(update=…)` skips validation, so a test
  double could build a wrong shape. Tests build `GraphContext` through `with_graph`, which
  validates, and `test_graph_context_is_validated.py` fails on any `model_copy(update=…)` of it
  under `tests/` `[agreed 2026-11-08]`. `src/…/handlers/contract.py:74` copies the graph the same
  way to set `api_contract_paths`; it is outside the slot and the guard's scope, and stays.
