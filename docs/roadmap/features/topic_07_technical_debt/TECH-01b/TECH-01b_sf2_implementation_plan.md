# Implementation Plan: Sandbox Domain Alignment [SF-2]
- **Feature ID**: TECH-01b
- **Sub-Feature**: SF-2 — Sandbox Domain Alignment
- **Design Document**: [TECH-01b_design.md](file:///c:/development/pitbula/specweaver/docs/roadmap/features/topic_07_technical_debt/TECH-01b/TECH-01b_design.md)
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Status**: COMPLETED

---

## 1. Research Notes

### 1.1 Class Inventory — Current State

All 16 tool/facade classes that need `BaseTool` conformance (14 from design + `QARunnerTool` + `ArchitectMCPInterface` needs `BaseTool` + delegating role):

| Class | File | Has `role`? | Has `definitions()`? | Notes |
|-------|------|------------|---------------------|-------|
| `FileSystemTool` | `filesystem/interfaces/tool.py:43` | ✅ property | ✅ | RBAC tool — uses `ROLE_INTENTS[self._role]` for gating |
| `ImplementerFileInterface` | `filesystem/interfaces/facades.py:40` | ❌ | ✅ delegates | Facade wrapping `FileSystemTool` |
| `ReviewerFileInterface` | `filesystem/interfaces/facades.py:95` | ❌ | ✅ delegates | Facade wrapping `FileSystemTool` |
| `DrafterFileInterface` | `filesystem/interfaces/facades.py:129` | ❌ | ✅ delegates | Facade wrapping `FileSystemTool` |
| `GitTool` | `git/interfaces/tool.py:105` | ✅ property | ✅ | RBAC tool — uses `ROLE_INTENTS[self._role]` for gating |
| `ImplementerGitInterface` | `git/interfaces/facades.py:43` | ❌ | ✅ delegates | Facade wrapping `GitTool` |
| `ReviewerGitInterface` | `git/interfaces/facades.py:81` | ❌ | ✅ delegates | Facade wrapping `GitTool` |
| `DebuggerGitInterface` | `git/interfaces/facades.py:115` | ❌ | ✅ delegates | Facade wrapping `GitTool` |
| `DrafterGitInterface` | `git/interfaces/facades.py:153` | ❌ | ✅ delegates | Facade wrapping `GitTool` |
| `ConflictResolverGitInterface` | `git/interfaces/facades.py:178` | ❌ | ✅ delegates | Facade wrapping `GitTool` |
| `WebTool` | `web/interfaces/tool.py:65` | ✅ property | ✅ | RBAC tool — uses `ROLE_INTENTS[self._role]` for gating |
| `CodeStructureTool` | `code_structure/interfaces/tool.py:75` | ✅ property | ✅ (`list[Any]`) | RBAC tool — return type needs fix → `list[ToolDefinition]` |
| `MCPExplorerTool` | `mcp/interfaces/tool.py:18` | ❌ | ❌ | Non-RBAC tool — returns `NO_ROLE`. Needs AD-6 topology refactor |
| `ArchitectMCPInterface` | `mcp/interfaces/facades.py:18` | ❌ | ✅ | Facade wrapping `MCPExplorerTool` — delegates `role` |
| `ProtocolTool` | `protocol/interfaces/tool.py:10` | ❌ | ✅ | Non-RBAC tool — returns `NO_ROLE`. Module-level imports need cleanup |
| `QARunnerTool` | `qa_runner/interfaces/tool.py:82` | ✅ property | ✅ | RBAC tool — added per HITL review |

### 1.2 Atom-Tool Dependency Audit

**Result: CLEAN.** No atom imports any tool. The architecture is correct everywhere:
- Tools wrap atoms (correct direction): `QARunnerTool.__init__(atom)`, `CodeStructureTool.__init__(atom)`
- `ProtocolTool` instantiates `ProtocolAtom()` inside its methods (same-domain, correct direction)
- No atom file anywhere imports from `*.interfaces.tool`

### 1.3 `role` Property — Resolved Design Decision

> [!IMPORTANT]
> **Decision: `NO_ROLE` sentinel constant on `BaseTool`.**
> `role` stays abstract on `BaseTool`. Tools without RBAC return `BaseTool.NO_ROLE` (`"no_role"`).
> This is semantically honest (explicit opt-out, not a fake role name), keeps the uniform contract,
> requires no SF-1 ABC changes, and enables future defensive code like `if tool.role != BaseTool.NO_ROLE`.

**Evidence:** 5 concrete use-case scenarios were evaluated. No current or near-future consumer
reads `role` on non-RBAC tools. The sentinel makes the opt-out explicit and greppable.

**Implementation pattern:**
- RBAC tools (`FileSystemTool`, `GitTool`, `WebTool`, `CodeStructureTool`, `QARunnerTool`): return their real agent role (e.g., `"implementer"`, `"reviewer"`)
- Non-RBAC tools (`ProtocolTool`, `MCPExplorerTool`): return `BaseTool.NO_ROLE`
- Facades wrapping RBAC tools: delegate `role` to `self._tool.role` (returns real role)
- Facades wrapping non-RBAC tools (`ArchitectMCPInterface`): delegate `role` to `self._tool.role` (returns `NO_ROLE`)

### 1.4 Registry `type: ignore` Markers

All 6 factory closures in `registry.py` have `# type: ignore[return-value]`. After SF-2 makes all tools inherit `BaseTool`, these are stale. **Remove all** (F-9 Option A).

### 1.5 External Dependencies

No new external dependencies. Tach baseline: 95 violations. SF-2 must not increase this.

---

## 2. Proposed Changes

### Component: Sandbox — Base

#### [MODIFY] [base.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/base.py)

**Change:** Add `NO_ROLE` class constant and update `role` docstring.

```python
class BaseTool(ABC):
    """Abstract base class representing an LLM-accessible sandbox tool.

    All sandbox tool facades must inherit this class. Role-based access
    control (RBAC) is enforced structurally by the facade layer (methods
    physically absent), so no `allowed_intents` property is required here.
    """

    NO_ROLE: str = "no_role"

    @property
    @abstractmethod
    def role(self) -> str:
        """The role this facade is configured for.

        Return BaseTool.NO_ROLE for tools without role-based access control.
        """

    @abstractmethod
    def definitions(self) -> list[ToolDefinition]:
        """Return the list of tool definitions for LLM registration."""
```

---

### Component: Sandbox — Filesystem Domain

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/filesystem/interfaces/tool.py)

**Change:** Add `BaseTool` inheritance to `FileSystemTool`.

```python
# Add import (near top)
from specweaver.sandbox.base import BaseTool

# Change class declaration (line 43)
class FileSystemTool(BaseTool):
```

No other changes — already has `role` property (line 69-72) and `definitions()` (line 79-82).

#### [MODIFY] [facades.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/filesystem/interfaces/facades.py)

**Change:** Add `BaseTool` inheritance and delegating `role` property to all 3 facade classes.

```python
# Add import (after existing imports, around line 23)
from specweaver.sandbox.base import BaseTool
```

For each of `ImplementerFileInterface` (line 40), `ReviewerFileInterface` (line 95), `DrafterFileInterface` (line 129):
```python
class ImplementerFileInterface(BaseTool):
    # existing __init__ unchanged

    @property
    def role(self) -> str:
        return self._tool.role

    # existing definitions() unchanged — already delegates
```

---

### Component: Sandbox — Git Domain

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/git/interfaces/tool.py)

**Change:** Add `BaseTool` inheritance to `GitTool`.

```python
# Add import
from specweaver.sandbox.base import BaseTool

# Change class declaration (line 105)
class GitTool(BaseTool):
```

No other changes — already has `role` property (line 121-124) and `definitions()` (line 131-135).

#### [MODIFY] [facades.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/git/interfaces/facades.py)

**Change:** Add `BaseTool` inheritance and delegating `role` property to all 5 facade classes.

```python
# Add import (after existing imports, around line 24)
from specweaver.sandbox.base import BaseTool
```

For each of `ImplementerGitInterface` (line 43), `ReviewerGitInterface` (line 81), `DebuggerGitInterface` (line 115), `DrafterGitInterface` (line 153), `ConflictResolverGitInterface` (line 178):
```python
class ImplementerGitInterface(BaseTool):
    # existing __init__ unchanged

    @property
    def role(self) -> str:
        return self._tool.role

    # existing definitions() unchanged
```

---

### Component: Sandbox — Web Domain

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/web/interfaces/tool.py)

**Change:** Add `BaseTool` inheritance to `WebTool`.

```python
# Add import
from specweaver.sandbox.base import BaseTool

# Change class declaration (line 65)
class WebTool(BaseTool):
```

No other changes — already has `role` property (line 88-91) and `definitions()` (line 195-199).

> [!NOTE]
> `PlannerWebInterface` and `ReviewerWebInterface` in `web/interfaces/facades.py` are NOT in the design doc's 14-class list. They are NOT registered in `get_standard_registry()` — the registry directly returns `WebTool`, not a web facade. Therefore they do NOT need `BaseTool` inheritance in SF-2. If needed later, the pattern is established.

---

### Component: Sandbox — Code Structure Domain

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/code_structure/interfaces/tool.py)

**Changes:**
1. Add `BaseTool` inheritance to `CodeStructureTool`.
2. Fix `definitions()` return type from `list[Any]` to `list[ToolDefinition]` (F-6 Option A).
3. Add `ToolDefinition` to the existing `TYPE_CHECKING` block.

```python
# Add import
from specweaver.sandbox.base import BaseTool

# Add to existing TYPE_CHECKING block (line 18-19)
if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

# Change class declaration (line 75)
class CodeStructureTool(BaseTool):

# Change definitions() return type (line 264)
def definitions(self) -> list[ToolDefinition]:
```

Already has `role` property (line 99-101).

---

### Component: Sandbox — MCP Domain

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/mcp/interfaces/tool.py)

**Changes (AD-6 + `BaseTool` + `NO_ROLE`):**
1. Add `BaseTool` inheritance.
2. Refactor `__init__` to accept `topology: Any = None` directly instead of `context: Any`.
3. Update all internal references from `self.context.topology` → `self._topology`.
4. Remove the `.context` attribute.
5. Add `role` property returning `self.NO_ROLE`.
6. Add `definitions()` method importing from `definitions.py`.

Full replacement for the class:

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.commons import json
from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.mcp.core.executor import MCPExecutor, MCPExecutorError
from specweaver.sandbox.mcp.interfaces.models import ToolResult

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition

logger = logging.getLogger(__name__)


class MCPExplorerTool(BaseTool):
    """Tool for L2 Architect exploration of external MCP interfaces."""

    def __init__(self, topology: Any = None) -> None:
        self._topology = topology
        self.ROLE_INTENTS = {
            "architect": frozenset({"list_servers", "list_resources", "read_resource"})
        }

    @property
    def role(self) -> str:
        return self.NO_ROLE

    def definitions(self) -> list[ToolDefinition]:
        from specweaver.sandbox.mcp.interfaces.definitions import (
            LIST_RESOURCES_DEF,
            LIST_SERVERS_DEF,
            READ_RESOURCE_DEF,
        )
        return [LIST_SERVERS_DEF, LIST_RESOURCES_DEF, READ_RESOURCE_DEF]
```

Internal method changes:
- `_execute_mcp_query`:
  - `if not self.context or not getattr(self.context, "topology", None):` → `if not self._topology:`
  - `servers = getattr(self.context.topology, "mcp_servers", {})` → `servers = getattr(self._topology, "mcp_servers", {})`
  - No other changes in this method (server_config, command, args, env logic stays)
- `_intent_list_servers`:
  - `if not getattr(self.context, "topology", None) or not getattr(self.context.topology, "mcp_servers", None):` → `if not self._topology or not getattr(self._topology, "mcp_servers", None):`
  - `mcp_servers = self.context.topology.mcp_servers` → `mcp_servers = self._topology.mcp_servers`
- `_intent_list_resources` and `_intent_read_resource`: unchanged (they call `_execute_mcp_query`)

#### [MODIFY] [facades.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/mcp/interfaces/facades.py)

**Changes:**
1. Add `BaseTool` inheritance and delegating `role` to `ArchitectMCPInterface`.
2. Update `definitions()` return type to `list[ToolDefinition]` and use `from __future__ import annotations`.
3. Add `create_mcp_interface` factory function.

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import BaseTool

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition
    from specweaver.sandbox.mcp.interfaces.tool import MCPExplorerTool

class ArchitectMCPInterface(BaseTool):
    """Role facade for the L2 Architect to survey available context mappings."""

    def __init__(self, tool: MCPExplorerTool) -> None:
        if "architect" not in tool.ROLE_INTENTS:
            raise MCPToolError("Architect role not configured on tool.")
        self._tool = tool

    @property
    def role(self) -> str:
        return self._tool.role

    def definitions(self) -> list[ToolDefinition]:
        return [
            LIST_SERVERS_DEF,
            LIST_RESOURCES_DEF,
            READ_RESOURCE_DEF,
        ]

    # existing intent methods and is_visible() unchanged


def create_mcp_interface(role: str, topology: Any = None) -> ArchitectMCPInterface:
    """Create a role-specific MCP interface facade.

    Args:
        role: The agent's role (only 'architect' is allowed for MCP).
        topology: The project's context topology server configuration.
    """
    if role != "architect":
        msg = f"Unknown role: {role!r}. Allowed: ['architect']"
        raise ValueError(msg)

    from specweaver.sandbox.mcp.interfaces.tool import MCPExplorerTool

    tool = MCPExplorerTool(topology=topology)
    return ArchitectMCPInterface(tool)
```

#### [MODIFY] [test_mcp_tool.py](file:///c:/development/pitbula/specweaver/tests/unit/sandbox/mcp/interfaces/mcp/test_mcp_tool.py)

**Changes:**
1. Refactor `mock_context` fixture to `mock_topology` returning a mock of the topology schema directly (exposing `mcp_servers`).
2. Update all `MCPExplorerTool(mock_context)` and `MCPExplorerTool(ctx)` constructor calls to pass the mock topology directly.
3. Clean up deleted attribute checks (e.g. `del ctx.topology`) in `test_execute_mcp_query_missing_topology` and replace with `MCPExplorerTool(topology=None)`.

---

### Component: Sandbox — Protocol Domain

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/protocol/interfaces/tool.py)

**Changes:**
1. Add `BaseTool` inheritance.
2. Add `role` property returning `self.NO_ROLE`.
3. Move `ToolDefinition` and `ToolParameter` imports under `TYPE_CHECKING` (F-7 Option A). Import at runtime inside `definitions()`.
4. Leave `ProtocolAtom` as module-level import (same domain, used at runtime).
5. Add `from __future__ import annotations`.

```python
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.protocol.core.atom import ProtocolAtom

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition

logger = logging.getLogger(__name__)


class ProtocolTool(BaseTool):
    """Native intent-based wrapper tool targeting Protocol extraction safely via the Atom layer."""

    @property
    def role(self) -> str:
        return self.NO_ROLE

    def definitions(self) -> list[ToolDefinition]:
        """Provides the schema for LLMs to invoke this tool."""
        from specweaver.infrastructure.llm.models import ToolDefinition, ToolParameter

        return [
            ToolDefinition(
                name="extract_schema_endpoints",
                description="Extracts structural backend intents out of OpenAPI, AsyncAPI, or gRPC definitions.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="The absolute or relative path to the OpenAPI, AsyncAPI, or Protocol Buffers definition file to extract.",
                        required=True,
                    )
                ],
            ),
            ToolDefinition(
                name="extract_schema_messages",
                description="Extracts data payload structures from API contracts.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="The absolute or relative path to the schema definition.",
                        required=True,
                    )
                ],
            ),
        ]

    # extract_schema_endpoints() and extract_schema_messages() — unchanged
```

---

### Component: Sandbox — QA Runner Domain

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/qa_runner/interfaces/tool.py)

**Change:** Add `BaseTool` inheritance to `QARunnerTool` (F-5 Option B).

```python
# Add import
from specweaver.sandbox.base import BaseTool

# Change class declaration (line 82)
class QARunnerTool(BaseTool):
```

No other changes — already has `role` property (line 97-100) and `definitions()` (line 161-165).

---

### Component: Sandbox — Dispatcher

#### [MODIFY] [dispatcher.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/dispatcher.py)

**Changes (AD-6):**
1. Remove `DummyContext` class (lines 238-240).
2. Refactor to use the `create_mcp_interface` factory function instead of instantiating the tool and facade manually, reducing coupling.

```python
# Before (lines 233-244):
if "mcp" in allowed_tools and role == "architect":
    from specweaver.sandbox.mcp.interfaces.facades import ArchitectMCPInterface
    from specweaver.sandbox.mcp.interfaces.tool import MCPExplorerTool

    class DummyContext:
        def __init__(self, topo: Any) -> None:
            self.topology = topo

    mcp_tool = MCPExplorerTool(context=DummyContext(topology))
    mcp_interface = ArchitectMCPInterface(mcp_tool)
    interfaces.append(mcp_interface)

# After:
if "mcp" in allowed_tools and role == "architect":
    from specweaver.sandbox.mcp.interfaces.facades import create_mcp_interface

    mcp_interface = create_mcp_interface(role=role, topology=topology)
    interfaces.append(mcp_interface)
```

---

### Component: Sandbox — Registry

#### [MODIFY] [registry.py](file:///c:/development/pitbula/specweaver/src/specweaver/sandbox/registry.py)

**Changes:**
1. Remove all `# type: ignore[return-value]` comments from all 6 factory closures (F-9 Option A).
2. Update `create_mcp` closure: use `create_mcp_interface` facade factory function.

```python
def create_fs(**kwargs: Any) -> BaseTool:
    from specweaver.sandbox.filesystem.interfaces.facades import create_filesystem_interface
    return create_filesystem_interface(
        role=kwargs["role"],
        cwd=kwargs["cwd"],
        grants=kwargs["grants"],
        exclude_dirs=kwargs.get("exclude_dirs"),
        exclude_patterns=kwargs.get("exclude_patterns"),
    )

def create_ast(**kwargs: Any) -> BaseTool:
    from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureTool
    return CodeStructureTool(
        atom=kwargs["atom"],
        role=kwargs["role"],
        grants=kwargs["grants"],
        hidden_intents=kwargs.get("hidden_intents"),
    )

def create_web(**kwargs: Any) -> BaseTool:
    from specweaver.sandbox.web.interfaces.tool import WebTool
    return WebTool(role=kwargs["role"])

def create_mcp(**kwargs: Any) -> BaseTool:
    from specweaver.sandbox.mcp.interfaces.facades import create_mcp_interface
    return create_mcp_interface(role=kwargs["role"], topology=kwargs.get("topology"))

def create_git(**kwargs: Any) -> BaseTool:
    from specweaver.sandbox.git.interfaces.facades import create_git_interface
    return create_git_interface(role=kwargs["role"], cwd=kwargs["cwd"])

def create_protocol(**kwargs: Any) -> BaseTool:
    from specweaver.sandbox.protocol.interfaces.tool import ProtocolTool
    return ProtocolTool()
```

---

## 3. Verification Plan

### Automated Tests

File: `tests/unit/sandbox/test_registry.py`

**Changes to existing tests:**
- Remove `@pytest.mark.xfail` marker from `test_standard_registry_tools_are_basetool_instances` — it should pass after SF-2.

File: `tests/unit/sandbox/mcp/interfaces/mcp/test_mcp_tool.py`

**Changes to existing tests:**
- Update `mock_context` to `mock_topology` and rewrite tests to pass `topology` instead of context to `MCPExplorerTool`.

**New test class: `TestBaseToolConformance`** (F-8 Option B)

Parametrized across all tool classes that inherit `BaseTool`. Each test:
1. Instantiates the tool with mocked dependencies.
2. Asserts `isinstance(tool, BaseTool)`.
3. Asserts `tool.role` returns a string.
4. Asserts `tool.definitions()` returns a list.

Tools to parametrize:
- `FileSystemTool` — mock `FileExecutor`, role=`"implementer"`, grants=`[]`
- `GitTool` — mock `GitExecutor`, role=`"implementer"`
- `WebTool` — role=`"implementer"`
- `CodeStructureTool` — mock `CodeStructureAtom`, role=`"implementer"`, grants=`[]`
- `MCPExplorerTool` — topology=`None` → assert `tool.role == BaseTool.NO_ROLE`
- `ProtocolTool` — no args → assert `tool.role == BaseTool.NO_ROLE`
- `QARunnerTool` — mock `QARunnerAtom`, role=`"implementer"`

**New test: `TestNoRoleSentinel`**
- `test_no_role_constant_value` — `assert BaseTool.NO_ROLE == "no_role"`
- `test_no_role_tools_return_sentinel` — ProtocolTool and MCPExplorerTool return `NO_ROLE`
- `test_rbac_tools_return_real_role` — WebTool(role="implementer") returns `"implementer"`, not `NO_ROLE`

**New test: `TestFacadeConformance`**
- Parametrized across facade classes. Each creates a facade from a mocked inner tool.
- Asserts `isinstance(facade, BaseTool)`.
- Asserts `facade.role == inner_tool.role` (delegation works).

**New tests for AD-6:**
- `test_mcp_explorer_accepts_topology_directly` — `MCPExplorerTool(topology=mock_topo)._topology is mock_topo`.
- `test_mcp_explorer_no_dummy_context` — grep dispatcher.py source for `DummyContext`, assert not found.

### Manual Verification

1. Run registry and MCP tests (expect all green, 0 xfail):
   `uv run pytest tests/unit/sandbox/test_registry.py tests/unit/sandbox/mcp/ -v`

2. Run full sandbox test suite (expect no regression):
   `uv run pytest tests/unit/sandbox/ -v`

3. Run tach check (must stay at ≤95 violations):
   `uv run tach check 2>&1 | Select-String "FAIL" | Measure-Object`

---

## 4. Commit Boundaries

### Single Commit: SF-2 Sandbox Domain Alignment

All changes are a single cohesive unit:

**Core tools (`BaseTool` inheritance):**
- `base.py` — add `NO_ROLE` constant + docstring update
- `filesystem/interfaces/tool.py` — `FileSystemTool(BaseTool)`
- `git/interfaces/tool.py` — `GitTool(BaseTool)`
- `web/interfaces/tool.py` — `WebTool(BaseTool)`
- `code_structure/interfaces/tool.py` — `CodeStructureTool(BaseTool)` + return type fix
- `qa_runner/interfaces/tool.py` — `QARunnerTool(BaseTool)`
- `mcp/interfaces/tool.py` — `MCPExplorerTool(BaseTool)` + AD-6 topology refactor + `NO_ROLE` + `definitions()`
- `protocol/interfaces/tool.py` — `ProtocolTool(BaseTool)` + `NO_ROLE` + import refactor

**Facades (`BaseTool` inheritance + role delegation):**
- `filesystem/interfaces/facades.py` — 3 facades: `(BaseTool)` + `role` property
- `git/interfaces/facades.py` — 5 facades: `(BaseTool)` + `role` property
- `mcp/interfaces/facades.py` — `ArchitectMCPInterface(BaseTool)` + `role` property + `create_mcp_interface` factory

**Infrastructure:**
- `dispatcher.py` — remove `DummyContext`, use `create_mcp_interface` factory instead of manual tool/facade instantiation.
- `registry.py` — remove all `type: ignore[return-value]`, update `create_mcp` closure

**Tests:**
- `test_registry.py` — remove xfail, add `TestBaseToolConformance`, `TestNoRoleSentinel`, `TestFacadeConformance`, AD-6 tests
- `test_mcp_tool.py` — refactor tests to use `mock_topology` and topology constructor argument.

---

## 5. Resolved HITL Decisions Log

| # | Finding | Resolution |
|---|---------|------------|
| F-1 | ProtocolTool missing `role` | `NO_ROLE` sentinel — returns `BaseTool.NO_ROLE` |
| F-2 | MCPExplorerTool missing `role`/`definitions()` | `NO_ROLE` sentinel + add `definitions()` from definitions.py |
| F-3 | AD-6 topology refactor | Option A — clean break, `topology: Any = None` parameter |
| F-4 | Facades missing `role` | Delegate: `return self._tool.role` (inherits real role or `NO_ROLE`) |
| F-5 | QARunnerTool scope | Option B — include it, already conformant |
| F-6 | CodeStructureTool return type | Option A — fix to `list[ToolDefinition]` |
| F-7 | ProtocolTool import cleanup | Option A — `TYPE_CHECKING` guard for `ToolDefinition`/`ToolParameter` |
| F-8 | Test strategy | Option B — parametrized `TestBaseToolConformance` + `TestFacadeConformance` |
| F-9 | Registry `type: ignore` | Option A — remove all stale markers |
| F-10 | Dev guide update | Option B — defer to pre-commit phase |
| F-11 | Dispatcher Coupling | Use `create_mcp_interface` in dispatcher to prevent manual instantiation |
