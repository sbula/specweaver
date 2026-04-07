# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""ToolDispatcher — dynamic facade for routing LLM intents to real tools.

Replaces the old ToolExecutor god-object. The Dispatcher accepts a list
of pre-configured interfaces (e.g., FileSystemInterface, WebInterface)
and automatically builds its registry from their public methods and definitions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.llm.models import ToolDefinition

logger = logging.getLogger(__name__)


class ToolDispatcher:
    """Dispatches tool calls from the LLM to underlying tool interfaces.

    Args:
        interfaces: A list of configured tool interfaces (e.g., FileInterface).
    """

    def __init__(self, interfaces: list[Any]) -> None:
        self._interfaces = interfaces
        self._registry: dict[str, Any] = {}
        self._build_registry()

    def _build_registry(self) -> None:
        """Scan interfaces for intent methods and matching definitions."""
        for interface in self._interfaces:
            # Safely check if the interface exposes definitions
            if not hasattr(interface, "definitions"):
                continue

            for tool_def in interface.definitions():
                name = tool_def.name
                handler = getattr(interface, name, None)
                if handler and callable(handler):
                    self._registry[name] = handler
                else:
                    logger.warning(
                        "Interface %s declared definition for %r but no handler exists.",
                        interface.__class__.__name__,
                        name,
                    )

    def available_tools(self) -> list[ToolDefinition]:
        """Return all tool definitions available in this dispatcher."""
        defs = []
        for interface in self._interfaces:
            if hasattr(interface, "definitions"):
                defs.extend(interface.definitions())
        return defs

    async def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call by name with arguments.

        Args:
            name: Tool intent name (e.g., 'grep', 'web_search').
            args: Intent arguments.

        Returns:
            The normalized dictionary result for the LLM.
        """
        logger.debug("Tool call: %s(%s)", name, args)

        handler = self._registry.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}

        try:
            result = handler(**args)

            # Support for both raw dicts or generic ToolResult objects
            if hasattr(result, "status"):
                if result.status == "error":
                    return {"error": result.message}
                if hasattr(result, "data") and result.data is not None:
                    # Some tools returned wrapped list inside results
                    if isinstance(result.data, list):
                        return {"results": result.data}
                    if isinstance(result.data, dict):
                        return result.data
                    return {"result": result.data}
                return {"success": True, "message": result.message}

            return result  # type: ignore[no-any-return]
        except BaseException as exc:
            logger.warning("Tool %s failed: %s", name, exc)
            return {"error": f"Tool execution failed: {exc!s}"}

    @classmethod
    def create_standard_set(
        cls,
        boundary: Any,
        role: str,
        allowed_tools: list[str],
    ) -> ToolDispatcher:
        """Factory method to assemble standard tools for an agent.

        Args:
            boundary: The WorkspaceBoundary for the current execution.
            role: The agent's pipeline role ("reviewer", "planner", etc.).
            allowed_tools: List of tool subsets to enable (e.g., ["fs", "web"]).

        Returns:
            A configured ToolDispatcher encompassing all allowed intents.
        """
        interfaces: list[Any] = []

        if "fs" in allowed_tools or "filesystem" in allowed_tools:
            # Isolate imports so flow/ doesn't violate boundaries
            from specweaver.loom.security import AccessMode, FolderGrant
            from specweaver.loom.tools.filesystem.interfaces import create_filesystem_interface

            grants = []
            for root in boundary.roots:
                grants.append(FolderGrant(str(root), AccessMode.FULL, recursive=True))
            for api_path in boundary.api_paths:
                grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))

            # The first root acts as the cwd for relative paths
            fs_interface = create_filesystem_interface(role, cwd=boundary.roots[0], grants=grants)
            interfaces.append(fs_interface)

        if "ast" in allowed_tools or "codestructure" in allowed_tools:
            # Isolate AST dependencies
            from specweaver.loom.atoms.code_structure.atom import CodeStructureAtom
            from specweaver.loom.commons.filesystem.executor import EngineFileExecutor
            from specweaver.loom.security import AccessMode, FolderGrant
            from specweaver.loom.tools.code_structure.tool import CodeStructureTool

            # Atom executes locally reading files relative to project root
            atom = CodeStructureAtom(EngineFileExecutor(boundary.roots[0]))

            # Reuse exact read-only grant logic from fs
            grants = []
            for root in boundary.roots:
                grants.append(FolderGrant(str(root), AccessMode.FULL, recursive=True))
            for api_path in boundary.api_paths:
                grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))

            ast_interface = CodeStructureTool(atom=atom, role=role, grants=grants)
            interfaces.append(ast_interface)

        if "web" in allowed_tools:
            # Provide WebTool directly if web search is enabled
            from specweaver.loom.tools.web.tool import WebTool

            # Note: The factory doesn't read env directly since it's a domain boundary.
            # but WebTool safely degrades if api_key isn't supplied (web_enabled=False).
            web_tool = WebTool(role=role)
            interfaces.append(web_tool)

        return cls(interfaces)
