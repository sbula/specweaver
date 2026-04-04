# Feature 3.11a Implementation Plan: Architecture Cleanup

The goal of this feature is to address the accumulated architectural debt from Features 3.10 and 3.11. This cleanup aligns the tool-execution engine with the established Atom/Tool layer boundaries and unlocks mid-loop injection capabilities for the LLM review/planning agents.

## Proposed Changes

---
### 1. `planning/`
Refactor the Planner to use `PromptBuilder` instead of raw string formatting. This standardizes prompt construction and allows the injection of auto-detected mentions and standards.

#### [MODIFY] planner.py(file:///c:/development/pitbula/specweaver/src/specweaver/planning/planner.py)
- Remove `PLAN_SYSTEM_PROMPT` and `PLAN_USER_TEMPLATE` constants.
- Instantiate `PromptBuilder` inside `Planner.plan()`.
- Add the specification as a priority-1 file block.
- Refactor the context insertion logic to use Builder blocks instead of formatting `{extra_context}` strings.

---
### 2. `llm/`
Expose a callback hook in the agentic tool-use loop so that orchestrators can scan intermediate responses and inject new context (like file mentions) between tool rounds.

#### [MODIFY] adapters/base.py(file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/base.py)
- Update `generate_with_tools` signature to accept `on_tool_round: Callable[[list[Message]], Awaitable[list[Message]]] | None = None`. (The callback will return *new* `Message` blocks, which the adapter appends, rather than mutating the list in place).

#### [MODIFY] adapters/gemini.py(file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/gemini.py)
- Inside the `for round_num in range(max_tool_rounds):` loop, after appending tool results to `messages`, add `if on_tool_round: await on_tool_round(messages)`.

---
### 3. `loom/` (The Dispatcher & Commons Cleanup)
Eliminate the `commons/research/` envelope, which violates upward dependency rules by importing tools. Promote the executor to a Dispatcher at the `loom` root. Decentralize tool definitions.

#### [NEW] dispatcher.py(file:///c:/development/pitbula/specweaver/src/specweaver/loom/dispatcher.py)
- Rename `ToolExecutor` to `ToolDispatcher`.
- Implement a Factory Method `ToolDispatcher.create(boundary, allowed_tools: list[str])` to keep tool imports hidden from `flow/`.
- The factory selectively instantiates *only* the requested tools (e.g., `['read_file', 'grep']`), avoiding the overhead of instantiating the entire tool suite for agents that don't need them.
- Loop over the instantiated tools to build the registry and definition list automatically via a standard `Tool.definition()` method.

#### [DELETE] commons/research/executor.py(file:///c:/development/pitbula/specweaver/src/specweaver/loom/commons/research/executor.py)
- Removed in favor of `dispatcher.py`.

#### [DELETE] commons/research/boundaries.py(file:///c:/development/pitbula/specweaver/src/specweaver/loom/commons/research/boundaries.py)
- `WorkspaceBoundary` functionality will be merged into `FolderGrant`.

#### [DELETE] commons/research/definitions.py(file:///c:/development/pitbula/specweaver/src/specweaver/loom/commons/research/definitions.py)
- Definitions will be moved directly into individual tool implementations (e.g., `loom/tools/filesystem/search.py`, `loom/tools/web/search.py`).

#### [NEW] security.py(file:///c:/development/pitbula/specweaver/src/specweaver/loom/security.py)
- Extract `FolderGrant` from `filesystem/models.py` into this central module so that the Dispatcher and other non-filesystem tools can import it without crossing boundaries.
- Merge the `WorkspaceBoundary` path-validation logic into `FolderGrant`.

#### [MODIFY] tools/filesystem/models.py(file:///c:/development/pitbula/specweaver/src/specweaver/loom/tools/filesystem/models.py)
- Enhance `FolderGrant` to support secondary roots and path verification logic previously found in `WorkspaceBoundary`.

---
### 4. `flow/`
Update the pipeline handlers to accommodate the ToolDispatcher changes and utilize the new adapter callback for injecting mention blocks.

#### [MODIFY] _review.py(file:///c:/development/pitbula/specweaver/src/specweaver/flow/_review.py)
- Update imports from `loom.commons.research.executor` to `loom.dispatcher`.
- Pass a `on_tool_round` callback closing over the `Reviewer` and `RunContext` to `generate_with_tools`. In the callback, perform mention scanning on the latest LLM message and append `PromptBuilder.add_mentioned_files()` blocks directly to the message history.

#### [MODIFY] context.yaml(file:///c:/development/pitbula/specweaver/src/specweaver/flow/context.yaml)
- Remove `loom/commons/research` from `consumes`.
- Add `loom/dispatcher` and `loom/tools/filesystem`, `loom/tools/web` to `consumes`. 

## Verification Plan

### Automated Tests
- `pytest tests/unit/planning/` to ensure Planner outputs the correct structured JSON. (Spec size violations will fail-fast per existing S03 limits).
- `pytest tests/unit/loom/` to verify `ToolDispatcher` properly handles dynamic tool registration.
- Explicitly update existing test mocks via sed replacement: `specweaver.loom.commons.research...` → `specweaver.loom.dispatcher...` before attempting to run tests.
- `pytest tests/unit/flow/` and `pytest tests/unit/review/` to verify the `on_tool_round` callback operates correctly during tool loops.

### Manual Verification
- Run `sw review CODE features/login.md` where the spec references files only known post-tool search, and observe the trace logs showing mention injection between rounds.
