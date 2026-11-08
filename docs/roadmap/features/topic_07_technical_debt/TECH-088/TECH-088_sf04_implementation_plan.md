# Implementation Plan: Two Graph Engines in Two Homes [SF-04: Names, the prompt source and frozen nodes]
- **Feature ID**: TECH-088
- **Sub-Feature**: SF-04 — Names, the prompt source and frozen nodes
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-088/TECH-088_sf04_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-08)

## Scope

FR-10, FR-11, FR-14 and FR-15, and the docs the design lists for this sub-feature. After SF-04, a
prompt source is recognised by its protocol, the names say what the code does, a loaded
`TopologyNode` cannot change at any depth `[agreed 2026-11-08]`, and no test stands a mock in for a
run's boundary `[agreed 2026-11-08]`. It is TECH-088's last sub-feature.

## Measured 2026-11-08

| Item | Where | Count |
|---|---|---|
| `hasattr` probe of a prompt source | `infrastructure/llm/prompt/adders.py:119` | 1; no test passes a mock source to `add_context` |
| `format_context_summary` | src 5 files (1 definition, 1 caller in `loader.py`, 3 docstrings), tests 3 files (16 calls) | — |
| `graph/lineage/repository.py` | imported by `graph/lineage/engine.py:7`; `tach.toml` exposes `lineage.repository` | 2 |
| `TopologyNode(...)` | src 2 (`_node_from`, `_auto_infer_missing`), tests 21 in 8 files | — |
| writes to a node's lists | src 0; tests 2 (`test_mcp_assembler.py:71, :79` call `.clear()`) | 2 |
| node-list asserts against list literals | 9 asserts in 5 test files | 9 |
| readers of a node's config | `mcp_assembler._resolve_mcp_command`, `sandbox/mcp/interfaces/tool.py:61-72`; both test `isinstance(…, list)` | 2 |
| mock boundaries for the MCP tool | `test_mcp_tool.py` (fixture), `test_mcp_loader_env_refused.py:33`, `test_mcp_explorer_guard.py:32`, `test_dispatcher_domain_conformance.py:34, :104`, `test_dispatcher_mcp_explorer_guard.py:31` | 6 sites, 5 files; `test_dispatcher.py:335` already uses a small honest class |

**A live defect found here.** `_resolve_mcp_command` (`mcp_assembler.py:74-84`) takes `command` out
of the server config and calls `command.extend(args)` on it, which changes the stored config. Run
2026-11-08: three calls give `['python', 'server.py']`, then `[…, 'server.py', 'server.py']`, then
three. A boundary that consumes two resources from one server starts the second with its `args`
twice. SF-01 made MCP run for real, so a user can hit this now.

## Commit boundaries

### CB-1 (interior): the protocol check and the names — FR-10, FR-11, docs

**Tests first:**
- `tests/unit/infrastructure/llm/prompt/test_prompt_source_by_protocol.py` (FR-10): a
  `TopologyContext` and a `FilePromptAdapter` are added as sources; an object with
  `get_prompt_content` but not `get_prompt_label` is refused with `TypeError`;
  `PromptContentSource` is `runtime_checkable`; no `hasattr(` is left in `adders.py`. Red: the
  protocol is not `runtime_checkable` and the `hasattr` is there.
- `tests/unit/test_the_old_names_are_gone.py` (FR-11): no `src/` or `tests/` file names
  `format_context_summary`, `specweaver.graph.lineage.repository` or
  `specweaver.graph.topology.changes` (an AST walk over imports, attribute names and strings, as in
  SF-02's guard); `graph/topology/topology.py` defines `contexts_for` and `graph/lineage/protocol.py`
  defines `LineageRepositoryProtocol`. Red: two of the three old names are there.

**Then the code:** `@runtime_checkable` on `PromptContentSource` and `isinstance` in `add_context`;
the two renames by script with `git mv`, tach's `lineage.repository` expose becoming
`lineage.protocol`; `graph/CLAUDE.md` rewritten for its 7 wrong claims; `graph/context.yaml` loses
`consumes: sandbox` if tach confirms the edge is unused.

**Mutants:** `isinstance` back to `hasattr`; the guard's AST walk ignores strings (the guard's own
test fails).

### CB-2 (interior): frozen nodes, and readers that take them — FR-14

**Tests first:**
- `tests/unit/graph/topology/test_frozen_node.py` (FR-14): a node loaded from a `context.yaml`
  with `consumes`, `exposes`, `forbids`, `constraints`, `consumes_resources`, `widens`,
  `operational` and an `mcp_servers` block whose server has a `command` list, an `args` list and
  an `env` map. Every one of these raises on a write: field assignment (`FrozenInstanceError`),
  `consumes.append`, `widens["x"] = …`, `mcp_servers["s"]["args"].append`,
  `mcp_servers["s"]["env"]["K"] = …`, `operational.max_latency_ms = …`. A node built in a test
  from plain lists ends up just as frozen. Red: nothing is frozen.
- `tests/unit/commons/test_frozen.py` (FR-14, E3 and the user's condition): the read-only mapping
  built from a dict holding a nested list; the caller then appends to that list and sets a key in
  the dict, and the mapping is unchanged (it holds a tuple, not the caller's list). Every value
  inside is frozen at build time, so `copy.deepcopy` and `copy.copy` return the same object. A
  value of a type outside the allow-list (a `bytearray`, an object) raises `TypeError` at build
  time, so no mutable leaf can get in. Red: the module does not exist.
- `tests/unit/sandbox/mcp/core/test_declared_command.py` (FR-14, E2 and the user's condition): the
  one command builder both readers call. `command: "docker"` gives `["docker"]`;
  `command: "python server.py"` is refused with an error naming the fix
  (`use command: [python, server.py]`), never split, never characters; a tuple `command` and `args`
  give a new list; a `str` or `bytes` `args`, a `bytes` `command`, and a non-string item each give
  an error. Both readers are tested with the spaced string: the assembler's fetch snippet and the
  explorer's `ToolResult` carry the error, and no process starts. Red: the function does not exist.
- `tests/integration/sandbox/mcp/test_mcp_servers_from_context_yaml.py` gains two cases (FR-14,
  the seam with `C-INTL-02`): a boundary consuming two resources from one server starts it with
  the same command both times, and the stored config is unchanged; a frozen config from the run
  setup still starts its server. Red: the second command has the `args` twice (the defect above).
- `tests/integration/interfaces/run_setup/test_run_carries_the_module_graph.py` gains a case
  (FR-14, "through the run setup"): the run's `target_boundary` and each `related_contexts` entry
  refuse a write at every depth. Red: nothing is frozen.
- The 9 list-literal asserts compare tuples; the 2 `.clear()` tests build the empty node they want.

**Then the code:**
1. `commons/frozen.py` (E5): `freeze(value)` turns a dict into a read-only mapping of frozen
   values, a list or tuple into a tuple of frozen values, a set into a `frozenset`; an immutable
   scalar (`str`, `bytes`, `int`, `float`, `bool`, `None`, `date`, `datetime`) stays; anything else
   raises `TypeError`. A value already frozen comes back as it is. The read-only mapping is a small `Mapping` class, not a `MappingProxyType`:
   its constructor freezes every value into a private dict it never hands out, and only because of
   that it returns itself from `__copy__` and `__deepcopy__` (the user, at Phase 4).
2. `TopologyNode` and `OperationalMetadata` become `frozen=True` (`TopologyContext` already is,
   E4); in all three `__post_init__` freezes each container field through `freeze` (`object.__setattr__`). Fields
   are typed `tuple[str, ...]` and `Mapping[...]`, with `()` as the default.
3. `DeclaredBoundary` declares its four members as read-only properties typed `Sequence[str]` and
   `Mapping[str, Mapping[str, Any]]`: a frozen dataclass cannot satisfy a protocol whose members
   are settable (mypy).
4. `declared_command(server_config) -> list[str] | str` in `sandbox/mcp/core/atom.py`, beside
   `resolved_runtime_command`: the list, or an error message. Order: a `str` `command` must be
   one word (no whitespace), else the error names the list form; `bytes` is refused; any other `Sequence` is copied item by item, each item a
   `str`; then `args` the same way, except that a `str` `args` is refused too. Both readers call it
   (F1); `_resolve_mcp_command` no longer calls `command.extend`, and both pass `dict(env)` on, so
   nothing writes into the config.
5. `boundary_rule.py`'s helpers take `Sequence[str]` where they took `list[str]`.

**Mutants:** `freeze` skips nested values (a nested `args` list stays a list); `__post_init__`
skips `mcp_servers`; the resolver goes back to `command.extend(args)`; `declared_command` drops its
`str` check on `args` (characters reach the command); the whitespace check removed (a spaced
string reaches the process).

### CB-3 (closes SF-04, HITL): honest boundaries — FR-15

**Tests first:**
- `tests/unit/sandbox/test_no_mock_boundary.py` (FR-15): no call under `tests/` to
  `MCPExplorerTool(...)`, `create_mcp_interface(...)` or `ToolDispatcher.create_standard_set(...)`
  passes a `MagicMock`/`Mock` as `topology`, by keyword or through a name bound to one; its own test
  feeds it each spelling. Red: the 6 sites.

**Then the code:** the 6 sites use a real `TopologyNode` (it satisfies `DeclaredBoundary`), built by
a small helper in `tests/fixtures/` where several files need the same one.

**Mutant:** one mock boundary put back → the guard fails.

**Then the closure** (`specweaver-feature` Phase 4): `check_fr_coverage.py TECH-088`,
`tests.py feature TECH-088 --kind bugfix`, the README counts, the live demo, and the finished
message.

## Research Notes

- `copy.deepcopy` of a `MappingProxyType` raises `TypeError`. `PromptBuilder` deep-copies its blocks
  (`infrastructure/llm/prompt/builder.py:99`); a block keeps its source, and a `TopologyContext`
  added through `add_context` holds `mcp_servers` copied from a node (`dict(node.mcp_servers)`, a
  shallow copy whose inner configs would be frozen). E3 decides how this is handled; CB-2 probes it
  with a test first.
- `build_child_env(extra_env)` starts from an empty dict and merges `extra_env`
  (`sandbox/execution/child_env.py:68-78`), so a read-only `env` mapping works there once it is
  `dict(env)`.
- `MappingProxyType` raises `TypeError` on item assignment; a tuple has no `append`
  (`AttributeError`); a frozen dataclass raises `FrozenInstanceError` (a subclass of
  `AttributeError`).
- No source writes a node field or list (grep 2026-11-08); every source reader loops, sorts or
  unpacks.

## Architecture (Phase 3)

| Change | Module | Rule | Verdict |
|---|---|---|---|
| the freeze helper | `commons` (E5) | pure, no I/O, imports nothing | ok |
| frozen node | `graph.topology` | — | ok |
| readers taking sequences | `core.flow.handlers`, `sandbox` | no new import | ok |
| renames | `graph.topology`, `graph.lineage` | tach interface entry renamed | ok |

## Decisions (Phase 4)

The user took all eight proposals `[agreed 2026-11-08]`, with two conditions:

- **E1** The resolver's config write is fixed in CB-2 under FR-14, red first.
- **E2** Readers take any sequence and build a new list, **but `str` and `bytes` are never read as a
  sequence** (the user): a `str` `command` is one word, never split; a `str` or
  `bytes` `args` and a `bytes` `command` are refused. `test_declared_command.py` proves it.
- **E3** The read-only mapping returns itself from `copy.deepcopy` **only because its constructor
  freezes every value recursively** (the user): no mutable leaf can exist inside.
  `test_frozen.py` builds one from a dict with a nested list, changes the list, and sees no change.
- **E4** `TopologyContext` is frozen the same way.
- **E5** `freeze` lives in `commons/frozen.py`.
- **E6** `contexts_for`, `graph/lineage/protocol.py`.
- **E7** A source with only one of the two methods raises `TypeError`.
- **E8** `graph/CLAUDE.md` rewritten; `consumes: sandbox` dropped if unused; the legacy map stays.

## Consistency and red/blue (Phase 5), 2 cycles

- Every SF-04 FR has a test: FR-10 (`test_prompt_source_by_protocol.py`), FR-11
  (`test_the_old_names_are_gone.py`), FR-14 (`test_frozen.py`, `test_frozen_node.py`,
  `test_declared_command.py`, two integration files), FR-15 (`test_no_mock_boundary.py`). NFR-2:
  `commons` stays `depends_on = []`; `declared_command` sits in `sandbox.mcp.core`, which
  `core.flow.handlers` already imports (`mcp_assembler.py:20`): no new tach edge.
- Fixed: `DeclaredBoundary` had settable members; a frozen dataclass does not satisfy that under
  mypy. Step 3 makes them read-only properties.
- Fixed: FR-14 says "integration (through the run setup)"; the run-setup case was missing.
- Checked: pydantic keeps a `TopologyContext` in `GraphContext.related_contexts` as the same object,
  tuples and read-only mapping intact (run 2026-11-08); it does not rebuild it into lists.
- Checked: no source serialises a node or a `TopologyContext` (`json.dumps` grep 2026-11-08);
  `tool.py:108` dumps only the server names.
- Accepted: `declared_command` refuses an item that is not a `str` (`args: [8080]`). Such a config
  never ran: the process start fails on it today.
- Accepted: the private dict inside the read-only mapping can be reached by reflection only, as a
  `MappingProxyType`'s can.
- **F1 (the user, C)** One function, `declared_command`, for both readers. A string `command`
  must be a single word; a command with arguments must be a list. A string with whitespace is
  refused with an error naming the fix (`use command: [python, server.py]`); both readers are tested
  `[agreed 2026-11-08]`. **User-visible change:** the assembler used to split such a string by
  `shlex`; it now refuses it. Checked 2026-11-08: no doc, fixture or test uses a spaced string (the
  docs use `command: "docker"` or a list); a path with a space must use the list form.
