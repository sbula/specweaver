# Walkthrough: TECH-088 — Two Graph Engines in Two Homes

## SF-01 CB-1 — three typed fields, filled by the run setup (FR-1, FR-12), `250ed9b3`

**What exists now.**
- `commons/topology_context.py`: two `runtime_checkable` protocols. `DeclaredBoundary` has `name`,
  `consumes`, `mcp_servers` and `consumes_resources`; `consumes` is what tells a boundary from a
  neighbour's `TopologyContext`, which also carries servers. `ModuleImpact` has `impact_of`.
- `GraphContext` has `related_contexts`, `target_boundary` and `module_graph`, with
  `arbitrary_types_allowed`. A list given as the boundary or the graph raises `ValidationError`
  where the run is built.
- `interfaces/run_setup/builder.py` `_graph_context` loads the graph once. The target boundary is
  the node named by the spec's module stem. No node by that name: one WARNING, and all three fields
  are `None`.
- `tests/fixtures/run_context.with_graph` rebinds a run's graph through `model_validate`; the 18
  test sites that used `model_copy(update=…)` go through it.

**Tests.** Red first: `test_run_carries_the_module_graph.py` (no fields, no warning) and
`test_graph_context_shapes.py`. `test_draft_keeps_its_contexts.py` was green on main on purpose: it
pins the one reader that worked. `test_graph_context_is_validated.py` was red with the 18 sites.

**Mutants.** FR-1: `no-target-boundary`, `no-module-graph`, `no-related-contexts`. FR-12:
`silent-orphan`. `TECH-077 FR-1 no-topology` was retargeted to `_graph_context`.

## SF-01 CB-2 — every reader reads its own field (FR-2, FR-3, FR-4)

**What changed.**
- `review.py` and `generation.py` pass `related_contexts` to `add_topology`, not a list inside a
  list. `decompose.py` hands the decomposer the same flat list and takes impact sets from
  `module_graph`. `draft.py` reads `related_contexts`.
- `mcp_assembler.py` reads `target_boundary`, never a neighbour's context, with no `getattr`.
- The sandbox MCP tool, its facade and the dispatcher type their `topology` parameter as
  `DeclaredBoundary`; the tool reads `mcp_servers` directly. Review feeds it `target_boundary`;
  review builds no MCP tool, so a user sees no change there.
- `GraphContext.topology` is deleted.

**Tests.** Each builds its run with `build_run`; each was red on main for the real reason:
- `test_review_prompt_names_its_neighbours_e2e.py`: `sw review` exited 1 with `AttributeError:
  'list' object has no attribute 'constraints'`. The two review classes of `test_topology_e2e.py`
  (`exit_code in (0, 1)`) are deleted in the same commit.
- `test_generation_prompt_names_its_neighbours.py`: the same `AttributeError`.
- `test_decomposition_impact_from_the_graph.py`: `'list' object has no attribute 'impact_of'`, and
  the decomposer got a list inside a list.
- `test_mcp_servers_from_context_yaml.py`: a run from the run setup started no server. The
  neighbour-only case was green on main for the wrong reason; the mutant
  `servers-from-a-neighbour` makes it fail.
- The guard now also catches `x = GraphContext(...)` then `x.model_copy(update=…)`.

**Found at the gate.** Three decomposition unit tests used a bare `MagicMock()` as the graph.
`runtime_checkable` checks with `getattr_static`, which does not see a mock's lazy attributes, so the
model refused it. They use a small `_Impacts` fake now: the refusal is the check working.

**Mutants.** FR-2: `review-drops-neighbours`, `generation-drops-neighbours`. FR-3:
`servers-from-a-neighbour`. FR-4: `impact-ignores-the-graph`, `decomposer-gets-no-contexts`.
