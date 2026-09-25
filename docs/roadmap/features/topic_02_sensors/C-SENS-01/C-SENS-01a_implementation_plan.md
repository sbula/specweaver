# C-SENS-01a — Architecture Cleanup

**Status**: Implemented in `5e013e6a` (2026-03-25) · Legacy: Feature 3.11a · Parent:
[C-SENS-01](C-SENS-01_implementation_plan.md)

## Goal

Pay the architectural debt of Features 3.10 and 3.11: align the tool-execution engine with the
Atom/Tool layer boundaries, and allow mid-loop injection for the LLM review/planning agents.

## Changes

### 1. `planning/` — Planner on `PromptBuilder`

Standard prompt construction, so auto-detected mentions and standards can be injected.

`planner.py` (`src/specweaver/planning/planner.py`):
- Remove `PLAN_SYSTEM_PROMPT` and `PLAN_USER_TEMPLATE` constants.
- Instantiate `PromptBuilder` inside `Planner.plan()`.
- Add the specification as a priority-1 file block.
- Insert context as Builder blocks instead of formatting `{extra_context}` strings.

### 2. `llm/` — callback hook in the tool-use loop

Orchestrators can scan intermediate responses and inject new context (like file mentions) between
tool rounds.

`adapters/base.py` (`src/specweaver/llm/adapters/base.py`):
- `generate_with_tools` accepts
  `on_tool_round: Callable[[list[Message]], Awaitable[list[Message]]] | None = None`. The callback
  returns *new* `Message` blocks, which the adapter appends; it does not mutate the list in place.

`adapters/gemini.py` (`src/specweaver/llm/adapters/gemini.py`):
- Inside `for round_num in range(max_tool_rounds):`, after appending tool results to `messages`:
  `if on_tool_round: await on_tool_round(messages)`.

### 3. `loom/` — Dispatcher and commons cleanup

`commons/research/` imported tools, violating the upward dependency rules. It is removed; the
executor becomes a Dispatcher at the `loom` root, and tool definitions live with their tools.

`dispatcher.py` (new, `src/specweaver/loom/dispatcher.py`):
- Rename `ToolExecutor` to `ToolDispatcher`.
- Factory Method `ToolDispatcher.create(boundary, allowed_tools: list[str])` keeps tool imports
  hidden from `flow/`.
- The factory instantiates *only* the requested tools (e.g., `['read_file', 'grep']`), not the
  whole suite.
- It loops over the instantiated tools to build the registry and definition list via a standard
  `Tool.definition()` method.

Deleted:
- `commons/research/executor.py` (`src/specweaver/loom/commons/research/executor.py`) — replaced by
  `dispatcher.py`.
- `commons/research/boundaries.py` (`src/specweaver/loom/commons/research/boundaries.py`) —
  `WorkspaceBoundary` functionality merges into `FolderGrant`.
- `commons/research/definitions.py` (`src/specweaver/loom/commons/research/definitions.py`) —
  definitions move into the tool implementations (e.g., `loom/tools/filesystem/search.py`,
  `loom/tools/web/search.py`).

`security.py` (new, `src/specweaver/loom/security.py`):
- `FolderGrant` extracted from `filesystem/models.py` into this central module, so the Dispatcher
  and non-filesystem tools can import it without crossing boundaries.
- `WorkspaceBoundary` path validation merged into `FolderGrant`.

`tools/filesystem/models.py` (`src/specweaver/loom/tools/filesystem/models.py`):
- `FolderGrant` supports secondary roots and the path verification formerly in `WorkspaceBoundary`.

### 4. `flow/` — handlers on the Dispatcher and the callback

`_review.py` (`src/specweaver/flow/_review.py`):
- Imports move from `loom.commons.research.executor` to `loom.dispatcher`.
- Pass `generate_with_tools` an `on_tool_round` callback closing over the `Reviewer` and
  `RunContext`. It scans the latest LLM message for mentions and appends
  `PromptBuilder.add_mentioned_files()` blocks to the message history.

`context.yaml` (`src/specweaver/flow/context.yaml`):
- Remove `loom/commons/research` from `consumes`.
- Add `loom/dispatcher` and `loom/tools/filesystem`, `loom/tools/web` to `consumes`.

## Tests

1. First update the test mocks by sed replacement:
   `specweaver.core.loom.commons.research...` → `specweaver.core.loom.dispatcher...`.
2. `pytest tests/unit/planning/` — the Planner outputs the correct structured JSON. (Spec size
   violations fail fast per the existing S03 limits.)
3. `pytest tests/unit/loom/` — `ToolDispatcher` handles dynamic tool registration.
4. `pytest tests/unit/flow/` and `pytest tests/unit/review/` — the `on_tool_round` callback works
   during tool loops.

Manual: run `sw review CODE features/login.md` where the spec references files only found by a tool
search, and watch the trace logs show mention injection between rounds.

## As built

Differs from the plan, noted 2026-09-25:

- The callback is synchronous: `on_tool_round: Callable[[int, list[Message]], None]` (round number +
  messages), applied by each adapter.
- The factory is `ToolDispatcher.create_standard_set(boundary, role, allowed_tools, ...)`.
- `WorkspaceBoundary` was not merged away; it sits beside `FolderGrant` in the security module.

**Since moved**: `loom/dispatcher.py` → `src/specweaver/sandbox/dispatcher.py`; `loom/security.py`
→ `src/specweaver/sandbox/security.py`; `planning/planner.py` →
`src/specweaver/workflows/planning/planner.py`; `llm/adapters/` →
`src/specweaver/infrastructure/llm/adapters/`; `flow/_review.py` →
`src/specweaver/core/flow/handlers/review.py`.
