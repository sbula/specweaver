# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ToolDispatcher — dynamic facade for routing LLM intents to real tools.

Replaces the old ToolExecutor god-object. The Dispatcher accepts a list
of pre-configured interfaces (e.g., FileSystemInterface, WebInterface)
and automatically builds its registry from their public methods and definitions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition

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
    def create_standard_set(  # noqa: C901
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
            from specweaver.core.loom.security import AccessMode, FolderGrant
            from specweaver.core.loom.tools.filesystem.interfaces import create_filesystem_interface
            from specweaver.workspace.analyzers.factory import AnalyzerFactory

            exclude_dirs: set[str] = set()
            exclude_patterns: set[str] = set()
            for analyzer in AnalyzerFactory.get_all_analyzers():
                for ign in analyzer.get_default_directory_ignores():
                    exclude_dirs.add(ign.rstrip("/"))
                for pat in analyzer.get_binary_ignore_patterns():
                    exclude_patterns.add(pat)

            grants = []
            if role == "scenario_agent":
                # Strict FR-5a isolation: scenario agent cannot read src/ or tests/
                for root in boundary.roots:
                    grants.append(
                        FolderGrant(str(root / "scenarios"), AccessMode.FULL, recursive=True)
                    )
                    grants.append(FolderGrant(str(root / "specs"), AccessMode.READ, recursive=True))
                    grants.append(
                        FolderGrant(str(root / "contracts"), AccessMode.READ, recursive=True)
                    )
            elif role == "arbiter_agent":
                from specweaver.core.loom.security import ReadOnlyWorkspaceBoundary

                if isinstance(boundary, ReadOnlyWorkspaceBoundary):
                    for api_path in boundary.api_paths:
                        grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))
                else:
                    # Degraded fallback: treat all paths as read-only
                    for root in boundary.roots:
                        grants.append(FolderGrant(str(root), AccessMode.READ, recursive=True))
                    for api_path in boundary.api_paths:
                        grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))
            else:
                for root in boundary.roots:
                    grants.append(FolderGrant(str(root), AccessMode.FULL, recursive=True))
                for api_path in boundary.api_paths:
                    grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))

            # The first root acts as the cwd for relative paths. Fallback to api_paths if empty.
            cwd_path = boundary.roots[0] if boundary.roots else boundary.api_paths[0]
            fs_interface = create_filesystem_interface(
                role,
                cwd=cwd_path,
                grants=grants,
                exclude_dirs=exclude_dirs,
                exclude_patterns=exclude_patterns,
            )
            interfaces.append(fs_interface)

        if "ast" in allowed_tools or "codestructure" in allowed_tools:
            # Isolate AST dependencies
            from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom
            from specweaver.core.loom.commons.filesystem.executor import EngineFileExecutor
            from specweaver.core.loom.security import AccessMode, FolderGrant
            from specweaver.core.loom.tools.code_structure.tool import CodeStructureTool
            from specweaver.workflows.evaluators.loader import load_evaluator_schemas

            project_dir = boundary.roots[0] if boundary.roots else None
            schemas = load_evaluator_schemas(project_dir=project_dir)

            # Extract archetype dynamically to guarantee framework isolation
            active_archetype = "generic"
            plugins: list[str] = []
            if project_dir:
                try:
                    from specweaver.core.config.archetype_resolver import ArchetypeResolver

                    resolver = ArchetypeResolver(project_dir)
                    resolved_arch = resolver.resolve(project_dir / "stub")
                    active_archetype = resolved_arch if resolved_arch else "generic"
                    plugins = resolver.resolve_plugins(project_dir / "stub")
                except Exception:
                    pass

            # Atom executes locally reading files relative to project root
            atom = CodeStructureAtom(
                EngineFileExecutor(boundary.roots[0]),
                evaluator_schemas=schemas,
                active_archetype=active_archetype,
                plugins=plugins,
            )

            # Reuse exact read-only grant logic from fs
            grants = []
            for root in boundary.roots:
                grants.append(FolderGrant(str(root), AccessMode.FULL, recursive=True))
            for api_path in boundary.api_paths:
                grants.append(FolderGrant(str(api_path), AccessMode.READ, recursive=True))

            # Extract mathematically aggregated tool intent gates mapped by plugins (FR-3, FR-4)
            raw_intents = atom.active_evaluator.get("intents") or {}
            raw_hide = raw_intents.get("hide", []) if isinstance(raw_intents, dict) else []
            hidden_intents = raw_hide if isinstance(raw_hide, list) else [str(raw_hide)]

            ast_interface = CodeStructureTool(
                atom=atom, role=role, grants=grants, hidden_intents=hidden_intents
            )
            interfaces.append(ast_interface)

        if "web" in allowed_tools:
            # Provide WebTool directly if web search is enabled
            from specweaver.core.loom.tools.web.tool import WebTool

            # Note: The factory doesn't read env directly since it's a domain boundary.
            # but WebTool safely degrades if api_key isn't supplied (web_enabled=False).
            web_tool = WebTool(role=role)
            interfaces.append(web_tool)

        return cls(interfaces)
