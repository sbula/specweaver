# Design: Two Graph Engines in Two Homes

- **Feature ID**: TECH-088
- **Phase**: Topic 07 (Technical Debt)
- **Status**: COMPLETE (signed off by the user, 2026-11-08)
- **Kind**: `bugfix` — the re-measure found a live defect in the topology slot (FR-1..FR-4); the
  rest is refactor
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`; 7 findings, grouped by
  root cause `[agreed 2026-10-22]`. Re-measured 2026-11-08 before this design.

## Feature Overview

TECH-088 gives SpecWeaver's graphs one home and one graph library. The module graph
(`TopologyGraph`, built from `context.yaml`) moves from `assurance/graph/` to `graph/topology/`,
which becomes a tach module of its own; only the boundary rule stays in `assurance`
`[agreed 2026-11-08]`. Its hand-written engine is rebuilt on networkx, the library the code graph
already uses, with today's behaviour pinned first. The two graphs stay two graphs: ADR-006 decision
4 keeps declared intent (`context.yaml`) apart from extracted reality (the code graph), so the goal
is one graph domain, one graph library and one depth limit, with one engine class per graph
`[agreed 2026-11-08]`. The run's topology slot, typed `Any`, holds four different things for four
readers; review and code generation crash on what the run setup really puts there, and MCP servers
are never started. That slot gets one typed field per meaning.

## The Defect (measured 2026-11-08)

| Finding | Measured |
|---|---|
| AG-1: two engines, two depth caps | `graph/topology/engine.py` (hand-written Tarjan, cap `min(depth, 5)` at :120) and `graph/core/engine/core.py` (networkx, cap `min(depth, 5)` at :84). The protocol `assurance/graph/topology.py:28` says `neighbors_within(start, max_depth)` and `traverse(start, forward)`; the engine has `neighbors_within(module, depth=1)` and `traverse(start, forward=True)`. The two classes share no method: names versus semantic hashes, file index, GraphML, DB load |
| AG-2: the graph in the wrong home | `TopologyGraph` and its loader, selectors and hasher live in `assurance/graph/` (`archetype: pure-logic`); 21 source files, 28 test files and 57 docs name them. `graph.db` has **no reader outside its own builder**: `build_target` reads it back (`graph/core/builder/orchestrator.py:257`) so a rebuild need not re-read every file, which is `B-SENS-02`'s "Done when". `B-SENS-09` is its first planned reader (ADR-006) |
| AG-17: one slot, four meanings | `GraphContext.topology: Any` (`core/flow/run_state/run_context.py:140`). The run setup stores `list[TopologyContext]` (`interfaces/run_setup/builder.py:208`); `draft.py:161` reads a list; `review.py:190` and `generation.py:283` wrap it in a second list; `decompose.py:252` calls `.impact_of` on it, as on a `TopologyGraph`; `mcp_assembler.py:105` and `sandbox/mcp/interfaces/tool.py:56` probe it with `getattr` for `mcp_servers`, as on a `TopologyNode`. Each test builds the shape its own reader wants (`test_mcp_servers_from_context_yaml.py:103` a node, `test_mcp_flow_e2e.py:139` one context) |
| AG-17: the live defect | Run 2026-11-08 with the slot the run setup builds: `_build_review_prompt` and `_generation_prompt` raise `AttributeError: 'list' object has no attribute 'constraints'`; `evaluate_and_fetch_mcp_context` returns `None`. So `sw review` and code generation fail on a project whose `context.yaml` gives the spec's module a neighbour, and a run never starts the servers `C-INTL-02` declares |
| AG-17: names | two `changes.py`, unrelated (`assurance/graph/changes.py` files changed since the hash cache; `sandbox/code_structure/core/changes.py` multi-file edits). The second `detect_language` is gone; one remains in `infrastructure/llm/prompt/constants.py:35` |
| AG-18: prompt text in the graph | partly fixed: `TopologyContext` moved to `commons/topology_context.py`. `TopologyGraph.format_context_summary` builds data, not text; `add_topology` renders it. `add_context` probes any source with `hasattr` (`infrastructure/llm/prompt/adders.py:119`), though `PromptContentSource` exists (`prompt/interfaces.py:8`) |
| AG-14: lineage spread out | `commons/lineage.py` (the tag text, read by 10 files, `infrastructure/llm` among them, which may not depend on `graph`) is in the right place. `graph/lineage/repository.py` holds the protocol and `store/lineage_repository.py` the repository: the file name says the opposite |
| AG-13, CW-22: the chunker | `workspace/analyzers/chunking.py` (528 lines) is `B-SENS-03` ✅, which feeds `A-SENS-02` and `B-FLOW-04`; no product caller yet |
| Docs | `graph/CLAUDE.md` says "no persistence layer", "spec/code relationships", "query engine", "lineage tracks how specs evolve", "cycles, paths, centrality", "interfaces depends on interfaces.cli" and "no side effects" — all 7 wrong. `graph/context.yaml` lists `consumes: sandbox`; tach has no such edge |

## Path List (`ADR-005`)

| # | Path | Span | Owner | Status |
|---|---|---|---|---|
| P-1 | `sw review` on a project whose `context.yaml` gives the spec's module a neighbour → the run setup → the review handler → the prompt names the neighbour | run setup, graph, handler, prompt | TECH-088 (FR-1, FR-2) | ⬜ |
| P-2 | code generation on the same project → the prompt names the neighbour | run setup, handler, prompt | TECH-088 (FR-2) | ⬜ |
| P-3 | a run whose target boundary declares MCP servers and resources → the run setup → the assembler starts them | run setup, handler, sandbox | TECH-088 (FR-3) | ⬜ |
| P-4 | decomposition with target modules → the impact set comes from the module graph | run setup, handler, graph | TECH-088 (FR-4) | ⬜ |
| P-5 | `sw graph build` twice → the second build reads `graph.db` back | graph | `B-SENS-02` (unchanged) | ✅ |
| P-6 | the sandbox boundary check and `sw scan` read the module graph from its new home | sandbox, workspace, graph | TECH-088 (FR-6) | ⬜ |

## Research Findings

### Codebase Patterns

- **Callers.** The moving files are named by 21 source files, 28 test files, 1 script and 57 docs;
  the move is mechanical and goes by script, as in `TECH-090` SF-04 CB-1.
- **Tach.** `specweaver.graph` depends on `infrastructure.database` and `workspace.ast.adapters`;
  `specweaver.assurance.graph` on `graph`, `workspace.analyzers` and `workspace.context`. The moved
  code needs those last two: `workspace.analyzers` at `hasher.py:29` and `topology.py:293-294`,
  `workspace.context` at `hasher.py:20` (a `TYPE_CHECKING` import). Simulated
  2026-11-08: a module `specweaver.graph.topology` with them has no cycle; it reaches only
  `analyzers`, `ast.parsers` and `context`. Its users (`sandbox`, `workspace.project`,
  `interfaces.run_setup`, `core.flow.handlers`, `core.flow.interfaces`) are not reached back.
- **Boundary ledger.** `known_boundary_violations.md` carries two DEFERRED rows for file reads in
  `pure-logic` (`hasher.py`, `topology.py`); they move with the files, unchanged in substance.
- **Engine behaviour, run 2026-11-08** on a↔b and a self-loop on c: the old `traverse("a")` gives
  `{a, b}` (the start is included on a cycle), `nx.descendants` `{b}`; the old `neighbors_within`
  drops the start (`engine.py:129`), `nx.ego_graph` keeps it; a missing node gives an empty set,
  networkx raises `NodeNotFound` or `NetworkXError`; `cycles()` gives each cycle sorted,
  `[['a','b'], ['c']]`, in no fixed outer order. The dangling-edge skip (`engine.py:95`) cannot be
  reached: `add_edge` adds both ends. Today's tests only check `len(cycles) > 0`.
- **Mutants.** `TECH-004_mutants.json` has 2 mutants on `assurance/graph/loader.py`; they are
  re-pinned at the new path. No corpus names `graph/topology/engine.py`.

### Red/Blue (Phase 6), 2 cycles

- Fixed: typing `GraphContext` with `TopologyGraph` would add a tach edge `core.flow.run_state` →
  `graph.topology`; the fields use protocols in `commons` (AD-4).
- Fixed: "the target boundary" was undefined; it is the node named by the spec's module stem, the
  key `select_topology_contexts` already uses (FR-1).
- Fixed: FR-4 hid that decomposition raises today; written down, so its test goes red for that
  reason.
- Accepted: FR-4 changes which components a decomposition holds back, because impact sets were
  never computed before; that is the delivered behaviour coming back, not a new one.
- Accepted: the shallow step copy shares the module graph. Its engine is frozen and holds a lock,
  its node mapping and stale nodes cannot change (FR-13), but **the nodes' lists are still mutable**:
  each `TopologyNode` is a plain dataclass, so `graph.nodes[x].consumes.append(...)` still works. No
  source does it (grep 2026-11-08). FR-14 (SF-04) closes it with a deep freeze; until SF-04 lands,
  this risk stands `[agreed 2026-11-08]`.

### External Tools

| Tool | Version | API surface | Stable | Notes |
|---|---|---|---|---|
| networkx | 3.6.1 (pinned, `pyproject.toml:40`) | `DiGraph`, `descendants`, `ancestors`, `strongly_connected_components`, `nodes_with_selfloops`, `ego_graph` | Y | already used by the code graph; no new dependency |

### Blueprint References

- ADR-006 decision 4 (one code graph; the module graph different in kind) and the Joern Code
  Property Graph it cites.

## Functional Requirements

| # | Requirement | Tier |
|---|---|---|
| FR-1 | The run setup SHALL fill `GraphContext` with three typed fields in place of `topology: Any`: the related modules' contexts (`list[TopologyContext]`), the target boundary (the node whose name is the spec's module stem, the key the selectors already use), and the module graph; each is `None` when the project has no `context.yaml` or no match; the target boundary does not need neighbours, so MCP no longer depends on the module having any. The two new types are protocols in `commons/topology_context.py`, beside `TopologyContext`, so `core.flow.run_state` gains no tach edge. **Seam** run setup → handlers | integration |
| FR-2 | `sw review` and code generation SHALL put each related module's line in the prompt on a project whose `context.yaml` gives the spec's module a neighbour, through the handler, from the run the run setup builds; drafting, which works on main, SHALL keep passing the same contexts to the drafter, pinned by a seam test written first and green on main | e2e (review), integration (generation, draft) |
| FR-3 | The MCP assembler and the sandbox MCP tool SHALL read `mcp_servers` and `consumes_resources` from the target boundary only, never from a neighbour's context `[agreed 2026-11-08]`, through FR-1's typed field, with no `getattr` probe; on a run built by the run setup, a declared server is started. **Seam** run setup → `C-INTL-02` | integration |
| FR-4 | Decomposition SHALL take a component's impact set from FR-1's module graph (`impact_of`); today a component with `target_modules` raises `AttributeError` on the list. **Seam** | integration |
| FR-5 | `TopologyGraph`, its loader, selectors, hasher and changed-files code SHALL live in `specweaver.graph.topology`, a tach module with `depends_on = [specweaver.graph, workspace.analyzers, workspace.context]` (`graph` for the depth constant only, added in SF-03 with it: tach's `exact = true` refuses an unused edge `[agreed 2026-11-08]`); `assurance.graph` SHALL hold only the boundary rule; no source imports a moved name from `assurance.graph` | unit (guard) |
| FR-6 | The sandbox boundary check, `sw scan`, `sw graph build` and the run setup SHALL read the module graph from its new home and answer as before | integration (existing) |
| FR-7 | `TopologyEngine` SHALL run on a networkx `DiGraph` and keep today's answers: `traverse` includes the start when it is on a cycle; `neighbors_within` excludes the start; a missing node gives an empty set; `cycles()` gives each cycle sorted and counts a self-loop. These tests are written first, green against the old engine | unit |
| FR-8 | `TopologyEngineProtocol` SHALL match `TopologyEngine`'s signatures, checked by mypy where the graph is built | unit (typed assignment) |
| FR-9 | Both engines SHALL cap a neighbourhood at one constant in `graph/core/engine/models.py`, still 5 | unit |
| FR-10 | `add_context` SHALL recognise a prompt source by `isinstance` against a `runtime_checkable` `PromptContentSource`, not by `hasattr` | unit |
| FR-11 | Names say what the code does: `format_context_summary` becomes `contexts_for`; the moved `changes.py` becomes `changed_files.py`; `graph/lineage/repository.py` becomes `graph/lineage/protocol.py` | unit (import guard) |
| FR-12 | When a project has `context.yaml` files but none names the spec's module stem, the run setup SHALL log one WARNING per run naming the stem and saying that topology context and MCP pre-fetch are off `[agreed 2026-11-08]` | integration |
| FR-13 | A `TopologyGraph` SHALL freeze itself at the end of building, so every module graph a run gets is frozen: a later `add_node` or `add_edge` raises `FrozenGraphError`, and a test proves it `[agreed 2026-11-08]` | unit, integration (through the run setup) |
| FR-14 | A `TopologyNode` and its `OperationalMetadata` SHALL NOT change once loaded: every list field is a tuple, every dict field is read-only, and the `mcp_servers` configs nested inside are read-only too, all the way down; a write raises `[agreed 2026-11-08]` | unit, integration (through the run setup) |
| FR-15 | No test SHALL stand a `MagicMock` in for a run's boundary where the sandbox MCP tool, its facade or the dispatcher reads `mcp_servers`; those tests use an honest fake of the `DeclaredBoundary` protocol, and a guard fails on a mock boundary `[agreed 2026-11-08]` | unit (guard) |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | related contexts | `select_topology_contexts(graph, module_name, selector_name=...)` → `list[TopologyContext] \| None` | read `assurance/graph/loader.py:90-104` |
| FR-1 | target boundary | `TopologyGraph.nodes[name]` → `TopologyNode` | read `topology.py:201`; used so in `test_mcp_servers_from_context_yaml.py:101` |
| FR-1 | module graph | `load_topology(project_root)` → `TopologyGraph \| None` | read `builder.py:212` |
| FR-2 | rendering | `PromptBuilder.add_topology(contexts: list[TopologyContext])` | read `adders.py:238`; ran it with a nested list: `AttributeError` |
| FR-3 | servers | `TopologyNode.mcp_servers`, `.consumes_resources` | read `topology.py:52-66`; ran the assembler with the real slot: `None` |
| FR-4 | impact | `TopologyGraph.impact_of(module) -> set[str]` | read `topology.py:331` |

## Non-Functional Requirements

| # | Requirement |
|---|---|
| NFR-1 | Outside FR-1..FR-4, nothing a user sees changes: the existing suite passes with only import paths and the renamed names changed **[proof: meta — rule about the diff]** |
| NFR-2 | `tach check` passes with no new cycle, and `specweaver.graph`'s own `depends_on` is unchanged **[proof: arch — tach gate, not pytest]** |

## External Dependencies

None new; networkx 3.6.1 is already pinned.

## Architectural Decisions

- **AD-1** One graph domain: the module graph moves to `graph/topology/`, its own tach module;
  `boundary_rule.py` stays in `assurance` `[agreed 2026-11-08]`.
- **AD-2** One graph library, one depth limit, two engine classes, one per graph (ADR-006 #4)
  `[agreed 2026-11-08]`.
- **AD-3** `graph/topology/` keeps `archetype: pure-logic`, and the two ledger rows for its file
  reads move with it; changing the archetype is not this ticket's question.
- **AD-4** `GraphContext` gets one field per meaning (FR-1); the three handlers that read a single
  object and the two that probe with `getattr` read their own field. The field types are protocols
  in `commons`, which `TopologyNode` and `TopologyGraph` satisfy, so the run state does not import
  `graph`. A step's `copy.copy(context)` shares the graph; its engine, node mapping and stale nodes are
  frozen, but the nodes' lists are still mutable (see the accepted risks).

## ROI Analysis

### Investment Cost
4 sub-features; one mechanical move by script, one engine swap behind pinned tests, one slot fix
with three seam tests and an e2e.

### Returns
- `sw review` and code generation stop failing on projects with module neighbours, and the
  neighbours reach the prompt (FR-2).
- `C-INTL-02`'s servers start on a real run (FR-3).
- `B-SENS-09` and `A-SENS-02` find the graphs in one place, on one library.

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| networkx answers differ from the old engine | high | medium | FR-7's tests, written first against the old engine |
| A moved import is missed | low | low | FR-5's guard; tach |
| A test double hides the slot shape again | medium | high | FR-1..FR-4 build their run through the run setup, not by hand |

### Refactoring Opportunities
The weak e2e `tests/e2e/capabilities/assurance/test_topology_e2e.py` (`exit_code in (0, 1)`) is
replaced by FR-2's e2e.

## Non-Goals

- The chunker (`B-SENS-03`) stays where it is; it moves once, to the home `A-SENS-02`'s design
  makes for retrieval `[agreed 2026-11-08]`.
- The code graph and `graph.db` stay (`B-SENS-02`, ADR-006); no reader is built here.
- The module graph and the code graph are not merged (ADR-006 #4) `[agreed 2026-11-08]`.
- `commons/lineage.py` stays: `infrastructure/llm` reads the tag text and may not depend on
  `graph`.
- The archetype of `graph/topology/` (AD-3).

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `src/specweaver/graph/CLAUDE.md`, `graph/context.yaml` | the 7 wrong claims and the stale `consumes` | ✅ Updated |
| `docs/architecture/02_bounded_contexts/domain_llm_and_telemetry.md` | `TopologyContext` lives in `commons` | ✅ Updated |
| `docs/architecture/06_lessons_and_future/known_boundary_violations.md` | the two rows at their new path | ✅ Updated |
| `docs/architecture/03_system_topology/module_dependency_graph.md` | `graph.topology` as a module | ✅ Updated |

## Sub-Feature Breakdown

### SF-01: The topology slot
- **Scope**: `GraphContext`'s three typed fields; the run setup fills them; review, generation,
  draft, decompose, the MCP assembler and the sandbox MCP tool read their own field.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-12]
- **Independent**: depends on no other sub-feature and ships first; the user may push after it
  closes, before SF-02..SF-04 `[agreed 2026-11-08]`
- **Inputs**: the run setup, today's handlers
- **Outputs**: a run that carries each meaning in its own field

### SF-02: One home
- **Scope**: the five files move to `graph/topology/`, by script; `specweaver.graph.topology` in
  tach; the moved `changes.py` renamed; mutants re-pinned; ledger rows moved.
- **FRs**: [FR-5, FR-6]; and FR-11's rename of the moved `changes.py` to `changed_files.py`,
  moved here from SF-04 so the file and its patch strings move once `[agreed 2026-11-08]`
- **Inputs**: SF-01's handlers (they import the moved types)
- **Outputs**: `graph/topology/` holding the module graph

### SF-03: One library
- **Scope**: FR-7's tests first, against the old engine; `TopologyEngine` on networkx; the
  protocol fixed; one depth constant.
- **Constraints** (SF-01's shared step copy relies on both): the rebuilt engine keeps its
  `threading.Lock` around every read and write; the module graph stays read-only after the run
  setup builds it, so nothing after the run setup calls `add_node` or `add_edge`. FR-13 enforces
  it: the graph freezes itself at the end of building, and a write after that raises
  `[agreed 2026-11-08]`.
- **FRs**: [FR-7, FR-8, FR-9, FR-13]
- **Inputs**: SF-02's home
- **Outputs**: the hand-written Tarjan code deleted

### SF-04: Names and the prompt source
- **Scope**: `isinstance` in `add_context`; the other two renames (`format_context_summary`, the lineage protocol file) and the guard for all three; the docs.
- **FRs**: [FR-10, FR-11, FR-14, FR-15]; FR-14 and FR-15 added by the user 2026-11-08, after
  SF-03 found the nodes' own lists still mutable
- **Inputs**: SF-02's home
- **Outputs**: names that say what the code does

## Execution Order

SF-01 → SF-02 → SF-03 → SF-04. SF-01 needs nothing from the others; SF-02 follows it only so the
move script also moves SF-01's new imports. SF-03 and SF-04 touch different files and could run in
either order; one session runs them in turn.

## Live Demo

```bash
# a project with two boundaries: billing consumes payments; specs/billing_spec.md
sw review specs/billing_spec.md
# before: the step fails with AttributeError: 'list' object has no attribute 'constraints'
# after:  the review runs, and its prompt carries "payments (direct dependency)"
```

Nightly: `tests/e2e/capabilities/assurance/test_review_names_its_neighbours_live_e2e.py` runs it
against Gemini. One try, at most two requests (`agent_turns = 2`), no retry (the user, 2026-11-08).
It asserts on the request, not on the model's words, and saves the first request to `.tmp/live/`.
First green run 2026-11-08, 8 minutes.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The topology slot | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | One home | SF-01 (order only) | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | One library | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | Names and the prompt source | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Grilling 2026-11-08** (the user): the chunker moves once, in `A-SENS-02`; the five files move to
`graph/topology/`, `boundary_rule.py` stays; the goal is one library and two engine classes. The
user then checked six findings against the code; the answers corrected "nothing reads `graph.db`"
to ADR-006's "no reader outside its own builder". The re-measure of AG-17 found the slot defect
(FR-1..FR-4). At the approval gate the user asked 8 more questions: the fix stays SF-01, first and
independent; no matching node logs a WARNING (FR-12); MCP servers come from the target boundary
only (FR-3); SF-03 keeps the lock and the read-only graph. **Design approved 2026-11-08** (the user), on the
condition that the read-only graph is enforced by a test (FR-13). **SF-01 plan approved 2026-11-08** (the user): tests
build `GraphContext` only through a validating helper, and a guard fails on `model_copy(update=…)`
of it under `tests/`. **SF-01 dev 2026-11-08**: CB-1 `250ed9b3`; CB-2 accepted by
the user 2026-11-08 — every reader reads its own field, the slot is deleted, and `sw review`,
generation and decomposition no longer crash on a project with module neighbours. **SF-02 plan approved
2026-11-08** (the user): one boundary; a diff check proves the test rewrite touched only paths. **SF-02 dev
2026-11-08**: accepted by the user — the module graph lives in `graph/topology/`; the test rewrite
touched only paths (diff check), and the collected tests were equal. **SF-03 plan approved 2026-11-08** (the
user): the graph freezes itself, copies its nodes and expands its stale seeds before the freeze; no
test builds it on a mock engine. **SF-03 dev 2026-11-08**: CB-1 `9861c95c`; CB-2 accepted by the user — the graph
freezes itself, copies its nodes read-only and expands its stale seeds before the freeze. **SF-04 plan
approved 2026-11-08** (the user): one command builder for both MCP readers; a string `command` is one
word, a spaced one is refused with the list form named; the read-only mapping freezes every value
when built. **SF-04 dev 2026-11-08**: CB-1 `a58b216a`, CB-2 `bf73d912`; CB-3 accepted by the user —
no test hands the MCP tool a mock boundary. **Live demo 2026-11-08** `981252d6`: green against Gemini, one try. **Signed off by the user 2026-11-08.**
