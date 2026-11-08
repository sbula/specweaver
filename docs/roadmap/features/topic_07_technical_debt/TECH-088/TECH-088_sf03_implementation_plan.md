# Implementation Plan: Two Graph Engines in Two Homes [SF-03: One library]
- **Feature ID**: TECH-088
- **Sub-Feature**: SF-03 — One library
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_sf03_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-08)

## Scope

FR-7, FR-8, FR-9 and FR-13. After SF-03, the module graph's engine runs on networkx, the library
the code graph already uses, and answers every question as it does today; the hand-written Tarjan
code is gone. Its protocol matches it, both engines cap a neighbourhood with one constant (still 5),
and the module graph is frozen once built. Two constraints from SF-01 hold: the engine keeps its
`threading.Lock` around every read and write, and nothing writes to the graph after the run setup
`[agreed 2026-11-08]`.

## Today's behaviour (measured 2026-11-08, `graph/topology/engine.py`)

| Question | Old engine | networkx alone | So the new engine must |
|---|---|---|---|
| `traverse("a")` on a↔b | `{a, b}`: the start is in it when it is on a cycle | `nx.descendants` → `{b}` | add the start back when a cycle returns to it |
| `neighbors_within("a", 1)` | `{b}`: the start removed (`:129`) | `nx.ego_graph` keeps the centre | remove the start |
| a missing node | an empty set for `get_forward`, `get_reverse`, `traverse`, `neighbors_within` | `NetworkXError` / `NodeNotFound` | check membership first |
| `cycles()` | each cycle sorted; a self-loop counts (`[['c']]`); no fixed outer order | `strongly_connected_components` + `nodes_with_selfloops` | sort each; count self-loops; order the outer list too |
| `neighbors_within(x, 0)` | empty | — | stay empty |
| depth 100 | capped at 5 (`:120`) | — | cap with the shared constant |
| `nodes` | a copy | — | stay a copy |

The dangling-edge skip (`engine.py:95`) cannot be reached: `add_edge` adds both ends. It goes.

## Commit boundaries

### CB-1 (interior): the engine on networkx — FR-7, FR-8, FR-9

**Tests first:**
- `tests/unit/graph/topology/test_topology_engine_answers.py` (FR-7): every row above, exact
  values, `cycles()` compared as a set of tuples. **Green against the old engine** — that is the
  point: it pins today's answers before the swap. The existing `test_topology_engine.py` checks
  only `len(cycles) > 0` for cycles; the new file gives the exact answers.
- `tests/unit/graph/topology/test_engine_protocol.py` (FR-8): for each protocol method,
  `inspect.signature` of `TopologyEngine`'s method equals the protocol's (names, defaults, kinds).
  Red today: the protocol says `traverse(start, forward)` and `neighbors_within(start,
  max_depth)`. A typed assignment `engine: TopologyEngineProtocol = TopologyEngine()` in the same
  file lets mypy check it too.
- `tests/unit/graph/test_one_depth_limit.py` (FR-9): `MAX_NEIGHBOURHOOD_DEPTH == 5` in
  `graph/core/engine/models.py`; a chain of 10 is cut at the constant in both engines
  (`neighbors_within` and `extract_subgraph`); no `min(depth, 5)` literal left in `src/` (grep).
  Red today: the constant does not exist.

**Then the code:**
1. `graph/core/engine/models.py`: `MAX_NEIGHBOURHOOD_DEPTH = 5`; `InMemoryGraphEngine.extract_subgraph`
   (`graph/core/engine/core.py:84`) uses it in place of its own `min(depth, 5)` (C4).
2. `graph/topology/engine.py`: a `networkx.DiGraph` behind the same `threading.Lock`; each method
   in the order of the table's last column. `_pop_scc`, `_is_cycle` and the Tarjan body go.
3. `graph/topology/topology.py`: `TopologyEngineProtocol` takes the engine's exact signatures.
4. `tach.toml`: `specweaver.graph.topology` gains `specweaver.graph` (the constant; `exact = true`
   allows the edge only now that it is used) `[agreed 2026-11-08]`; `graph/topology/context.yaml`
   consumes `specweaver/graph`.

**Mutants:** `traverse` drops the start on a cycle; `neighbors_within` keeps the start; a missing
node raises; `cycles()` drops self-loops; the constant set to 6; `extract_subgraph` back to its own
`min(depth, 5)` (the grep in `test_one_depth_limit.py` fails).

### CB-2 (closes SF-03, HITL): the frozen graph — FR-13

**Tests first:**
- `tests/unit/graph/topology/test_frozen_graph.py` (FR-13): a `TopologyGraph` built from nodes;
  then `add_node` and `add_edge` on its engine raise `FrozenGraphError`; every read still answers;
  a bare `TopologyEngine` not yet frozen still takes writes. And the graph's own state cannot
  change after building (the user, at Phase 5): changing the caller's `nodes` dict afterwards
  changes nothing in the graph; `graph.nodes` refuses an assignment (`TypeError`); `stale_nodes`
  is final once `from_project` returns, with no write to `graph._stale_nodes` after `__init__`.
  Red today: nothing freezes, `__init__` keeps the caller's dict, and `from_project` sets
  `_stale_nodes` after building (`topology.py:275`).
- `tests/integration/interfaces/run_setup/test_run_carries_the_module_graph.py` gains a case
  (FR-13): the module graph from `build_run` refuses `add_edge`. Red today.

**Then the code:**
1. `graph/topology/engine.py`: `freeze()`, and `FrozenGraphError` raised by `add_node` and
   `add_edge` once frozen; the protocol gains `freeze()`.
2. `TopologyGraph.__init__` copies `nodes` and exposes it read-only: `graph.nodes` is a
   `MappingProxyType` over the copy, not a fresh `dict` (the user, at Phase 5). No caller changes
   the dict it gets today (grep 2026-11-08).
3. The stale nodes are final when `__init__` ends (the user, at Phase 5, D1 A): `__init__`'s
   parameter `stale_nodes` becomes `stale_seeds`, because `__init__` now expands it; after adding
   the edges it sets the stale nodes to the seeds plus `impact_of` each seed. `from_project`
   computes the seeds, passes them, and writes nothing after `__init__`. Callers of the keyword:
   `from_project` and `test_topology_staleness.py:28, :36`; the `stale_nodes` property keeps its
   name `[agreed 2026-11-08]`.
4. `TopologyGraph.__init__` freezes its engine last, after the nodes, edges and stale nodes (C1).

- No test builds a module graph on a bare `MagicMock()` engine (the user, at Phase 5): `freeze()`
  on a mock does nothing, so such a test proves nothing about FR-13. One file does today:
  `tests/unit/workspace/project/test_tach_sync.py`, 7 sites (`:45`, `:87`, `:124`, `:149`, `:156`,
  `:205`, `:236`); each gets a real `TopologyEngine()`. The other hits of the search are not module
  graph engines: `test_cli_lineage.py`'s `mock_engine` is a `LineageEngine`, and
  `test_cli_graph.py:23` patches `load_topology`. `test_topology_staleness.py` already uses real
  engines. A guard, `tests/unit/graph/topology/test_no_mock_topology_engine.py`, fails on a
  `TopologyGraph(...)` or `TopologyGraph.from_project(...)` call under `tests/` whose engine
  argument is a `MagicMock(...)` or `Mock(...)` call or a name bound to one, such as
  `engine = MagicMock()` then `TopologyGraph(nodes, engine)` (an AST walk, as in SF-01's guard; the
  user, at approval). The guard's own test feeds it both spellings, positional and keyword. Red
  today: the 7 sites `[agreed 2026-11-08]`.

**Mutants:** `freeze()` does nothing → both tests fail; `__init__` keeps the caller's dict → the
copy test fails; one `MagicMock()` engine put back → the guard fails.

## Research Notes

- `networkx` 3.6.1 (`pyproject.toml:40`): `descendants(G, n)` excludes `n`;
  `strongly_connected_components(G)` yields sets; `nodes_with_selfloops(G)`; `ego_graph(G, n,
  radius, undirected=True)` includes `n`; a missing node raises `NetworkXError` from `successors`
  and `NodeNotFound` from `ego_graph` (run 2026-11-08).
- Only `TopologyGraph.__init__` writes to the engine (`topology.py:189, :194`); `from_project`
  infers missing manifests into `nodes` before it builds the graph (`:254-265`), so freezing at the
  end of `__init__` blocks no current writer.
- No source prints `cycles()`; its outer order reaches no user. Sorting it makes it deterministic.
- 100 call sites build `TopologyEngine()` (src and tests); its constructor does not change.

## Architecture (Phase 3)

| Change | Module | Rule | Verdict |
|---|---|---|---|
| networkx in the module graph's engine | `graph.topology` (`pure-logic`) | a library with no I/O, already a dependency | ok |
| the constant | `graph.core.engine.models` (`pure-logic`), already exposed in tach | read by `graph.topology` (sibling, downward to core) | ok |
| `FrozenGraphError` | `graph.topology.engine` | — | ok |

No cycle: `specweaver.graph` imports nothing from `graph.topology` (grep 2026-11-08).

## Decisions (Phase 4)

All six proposals taken by the user `[agreed 2026-11-08]`; at Phase 5 the user widened C1 to the
graph's own state (nodes and stale nodes, below), chose D1 A with the parameter renamed, and closed
the mock-engine gap:

- **C1** `TopologyGraph.__init__` freezes its engine once the nodes and edges are in; the design's
  FR-13 says so now.
- **C2** A write after the freeze raises `FrozenGraphError`, defined in `graph/topology/engine.py`.
- **C3** The integration test reaches the engine through `TopologyGraph._engine`.
- **C4** `MAX_NEIGHBOURHOOD_DEPTH` in `graph/core/engine/models.py`; `TopologyEngine.neighbors_within`
  **and** `InMemoryGraphEngine.extract_subgraph` both use it, and neither keeps its own 5 (the
  user, at Phase 4).
- **C5** `cycles()` returns its outer list sorted.
- **C6** The unreachable dangling-edge skip is deleted.

## Consistency and red/blue (Phase 5), 2 cycles

- Every SF-03 FR has a test: FR-7 (`test_topology_engine_answers.py`), FR-8
  (`test_engine_protocol.py` and mypy), FR-9 (`test_one_depth_limit.py`), FR-13
  (`test_frozen_graph.py`, the run-setup case). NFR-1 holds: FR-7 pins the old answers first.
- Fixed: FR-7's tests are green against the old engine by design, so they cannot show a red; what
  shows they can fail is the five CB-1 mutants run against the new engine. The plan says so instead
  of calling them red-first.
- Checked: a freeze at the end of `__init__` would break a caller that builds two graphs on one
  engine. None does: every `TopologyGraph(...)` and `from_project(...)` in `src/` and `tests/` gets a
  fresh `TopologyEngine()` or a `MagicMock()` (grep 2026-11-08); the full suite confirms it.
- Checked: the freeze flag is read and set under the same lock as the writes, so a write racing the
  freeze either lands before it or raises.
- Checked: a `networkx.DiGraph` is not thread-safe on its own; every method keeps the lock, as the
  SF-01 constraint requires, and returns copies, never the graph's own sets.
