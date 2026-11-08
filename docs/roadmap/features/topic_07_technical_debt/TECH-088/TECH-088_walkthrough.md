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

## SF-02 CB-1 — one home (FR-5, FR-6)

**What moved.** `topology.py`, `loader.py`, `selectors.py`, `hasher.py` and `changes.py` (now
`changed_files.py`, FR-11's rename done here) went from `assurance/graph/` to `graph/topology/`, with
their 8 unit test files and one integration test file. `.tmp/move_topology.py` used `git mv` for 14
files and rewrote the old dotted and slash paths in 47 files: source, tests, scripts, the
`class_health.json` key, `TECH-004`'s two loader mutants and the boundary ledger. The 8 caller
manifests, three living docs, `TECH-082`'s corpus scope and `test_logging_rollout.py`'s
`from specweaver.assurance.graph import selectors` were fixed by hand; the script and the first guard
had both missed that last import form, and the guard now reads `from a import b` as `a.b`.
`assurance/graph/` holds `boundary_rule.py` and `context.yaml` only. No re-export.

**Tach.** `specweaver.graph.topology` depends on `workspace.analyzers` and `workspace.context`; the
boundary rule asks a reason for each in `widens`. `specweaver.graph` keeps its two edges and loses
`topology.engine` from its interface. `core.flow.handlers` and `workspace.project.interfaces` lose a
`specweaver.graph` edge that only the engine used; `sandbox` keeps `assurance.graph` for the rule
and gains `graph.topology`.

**The test rewrite touched only paths** (the user's check). Before any other test edit,
`.tmp/check_test_rewrite.py` read `git diff -M` over `tests/`: 33 changed test files, every removed
line equal to an added one once the paths were mapped, no file deleted. A changed assertion made it
fail; restored, it passed. Collected tests: 12,983 before and 12,983 after, the ids equal once the
moved paths were mapped. Only then were the 9 `Proves: TECH-088 FR-6` lines added; the check run
again lists exactly those lines, the new guard file and the new package's licence header. The
count is 12,984 now: the guard gained one case for the missed import form.

**Found at the gate.** The class-naming ratchet counts per top-level folder: 3 moved test classes now
count under `graph`. Re-frozen with `--update-naming-baseline`; every other folder's count fell,
none rose but `graph` (1 → 4, the move).

**Mutants.** FR-5: `caller-uses-the-old-home`. A re-export `assurance/graph/topology.py` put back by
hand also fails the guard.

**Gate.** Full suite 12,912 passed, 9 skipped; `tach`, `cb` 17/17, `doc` 14/14, `mypy` clean, no new
clone, 0 stale mutants.

## SF-03 CB-1 — the engine on networkx (FR-7, FR-8, FR-9)

**What changed.** `graph/topology/engine.py` holds a `networkx.DiGraph` behind the same lock; the
hand-written Tarjan code and the unreachable dangling-edge skip are gone. Three answers networkx
gives differently are written out: a traversal adds its start when a node it reaches points back at
it (or the start loops to itself); a neighbourhood drops its centre; a missing node answers empty.
`cycles()` sorts each cycle and the list. `TopologyEngineProtocol` now has the engine's signatures.
`MAX_NEIGHBOURHOOD_DEPTH = 5` in `graph/core/engine/models.py` is the one limit; the code graph's
`extract_subgraph` uses it too. `graph.topology` gains its `specweaver.graph` edge in tach, and
`graph`'s interface exposes the constant.

**Tests.** `test_topology_engine_answers.py` (13) was green against the old engine: it pins today's
answers. `test_engine_protocol.py` was red (`name` vs `node`, `start, max_depth` vs `module, depth`);
`test_one_depth_limit.py` was red (no constant, two `min(depth, 5)`).

**Mutants.** FR-7: `start-dropped`, `centre-kept`, `missing-raises`, `self-loops-dropped`. FR-8:
`protocol-renames-depth`. FR-9: `limit-plus-one` (a module constant cannot be a corpus symbol, so
the mutant sits where the engine reads it), `own-limit`.

## SF-03 CB-2 — the frozen graph (FR-13)

**What changed.** `TopologyEngine.freeze()` refuses every later write with `FrozenGraphError`; the
flag is set and read under the engine's lock. `TopologyGraph.__init__` copies the caller's `nodes`
into a `MappingProxyType`, adds the edges, expands `stale_seeds` (renamed from `stale_nodes`, since
`__init__` now expands them) by `impact_of`, stores the result as a `frozenset`, and freezes its
engine last. `from_project` computes the seeds first and writes nothing after `__init__`. The 7
`MagicMock()` engines in `test_tach_sync.py` are real `TopologyEngine()`s.

**Tests.** Red first: `test_frozen_graph.py` (no `FrozenGraphError`), the run-setup case in
`test_run_carries_the_module_graph.py`, and `test_no_mock_topology_engine.py` (the 7 sites). The
guard reads the engine by position or keyword, and through a name bound to a mock; its own test
feeds it all of them.

**Mutants.** FR-13: `freeze-noop`, `keeps-callers-dict`, `seeds-not-expanded`. A `MagicMock()`
engine put back in `test_tach_sync.py` fails the guard (run by hand; a test file is not a corpus
target).

**Limit, recorded.** The mapping is read-only, but each `TopologyNode` in it is a plain dataclass
whose lists can still be changed in place. No source does (grep 2026-11-08); freezing the node type
is wider than FR-13 and was not done here.

## SF-04 CB-1 — the protocol check and the names (FR-10, FR-11)

**What changed.** `add_context` checks `isinstance(text, PromptContentSource)`; the protocol was
already `runtime_checkable`, so the `hasattr` pair was the only defect. A bare `MagicMock` passed the
old probe and is refused now. `format_context_summary` is `contexts_for`, and
`graph/lineage/repository.py` is `protocol.py` (tach exposes `lineage.protocol`).
`graph/CLAUDE.md` is rewritten: two graphs, `graph.db` is persisted, the commands are named.
`graph/context.yaml` drops `consumes: specweaver/sandbox`: no file in `graph` imports it.

**Tests.** `test_prompt_source_by_protocol.py` (in `tests/unit/infrastructure/llm/`; the plan's
`prompt/` folder does not exist) was red on the mock and on the `hasattr` scan.
`test_the_old_names_are_gone.py` was red on the missing `contexts_for` and 24 uses of the old names;
its own test feeds it each spelling.

**Mutants.** FR-10: `probe-by-hasattr`. The guard's string check removed by hand: its own test
fails (a test file is not a corpus target).

## SF-04 CB-2 — a boundary that cannot change, and readers that never write it (FR-14)

**What changed.**
- `commons/frozen.py`: `freeze` turns dicts into a `FrozenMap`, lists and tuples into tuples, sets
  into frozensets, all the way down; immutable scalars stay; any other type raises `TypeError`.
  `FrozenMap` freezes every value in its constructor, so `copy` and `deepcopy` return it (the user,
  at Phase 4).
- `TopologyNode` and `OperationalMetadata` are `frozen=True`; `TopologyNode` and `TopologyContext`
  freeze their containers in `__post_init__`. `DeclaredBoundary`'s members are read-only properties.
  `topology_context.py` drops `from __future__ import annotations`: pydantic reads its field types
  at runtime, and the gate refused a `noqa` for it.
- `load_nodes` skips a `context.yaml` holding a value that cannot be frozen (a custom YAML tag), with
  a warning; the other nodes load.
- `declared_command(server_name, config)` in `sandbox/mcp/core/atom.py` is the one reading of
  `command` and `args`; both readers call it. A string `command` is one word; a spaced string is
  refused naming the list form; `str`/`bytes` `args` and non-string items are refused (the user,
  F1 C). It raises `ValueError`; the plan said "or an error message", and each reader already turns
  a `ValueError` into its own error shape.
- **User-visible:** the pre-fetch used to `shlex`-split a spaced `command` string; it now refuses it.
  The user guide says so. The explorer's "missing target executable command bounds" message is now
  "has no command".

**The live defect.** The pre-fetch wrote `args` into the stored config on every fetch. The new seam
test showed it reached the explorer too: after one pre-fetch, the explorer started `server.py`
twice. Red first in `test_both_readers_read_a_command_alike.py` (both readers, one config).

**Tests.** Red first: `test_frozen.py` (no module), `test_declared_command.py` (no function),
`test_frozen_node.py` (12 cases), the run-setup case in `test_run_carries_the_module_graph.py`, and
the three seam cases. Six asserts compare tuples now; the two `.clear()` tests build the boundary
they want through `with_graph`.

**Mutants.** FR-14: `nested-unfrozen`, `maps-skipped`, `context-unfrozen`, `args-as-characters`,
`spaced-string-split`, `resolver-writes-config`, `odd-leaf-crashes-load`. `TECH-072 FR-2
explorer-skips-runtime-guard` retargeted to the new call; its FR-3 and FR-8 mutants re-pinned.

**Accepted.** A `FrozenMap`'s private dict can be reached by reflection only, as a
`MappingProxyType`'s can. A node is unhashable, as it was before.

## SF-04 CB-3 — honest boundaries (FR-15)

**What changed.** `tests/fixtures/boundary.py` builds a real, frozen `TopologyNode` with the servers a
test wants. The plan counted 6 mock boundaries in 5 files; the guard found 8 builders (the
`test_mcp_tool.py` fixture and two local ones there, the explorer-guard helper, the loader-env
helper, two in the dispatcher conformance test, one in the dispatcher guard) feeding 19 calls. Each
uses `declared_boundary` now.

**Tests.** `test_no_mock_boundary.py` was red on the 19 calls. It reads `MCPExplorerTool`,
`create_mcp_interface` and `ToolDispatcher.create_standard_set` by position and keyword, and a mock
reached through a name, a fixture or a helper; its own test feeds it each spelling.

**Mutant.** A `MagicMock` boundary put back in `test_dispatcher_mcp_explorer_guard.py` fails the
guard (run by hand; a test file is not a corpus target).

**Closure.** `check_fr_coverage.py TECH-088`: 15 of 15 FRs planned and cited. `tests.py feature
TECH-088 --kind bugfix`: unit, integration and e2e green. README counts: 13,101 tests, 57 corpora,
1,499 mutants.
