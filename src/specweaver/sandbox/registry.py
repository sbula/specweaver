# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tool registry for the sandbox environment.

Provides a decoupled way to register and instantiate sandbox tools,
avoiding circular dependencies and module-level imports of heavy domains.
"""

import logging
from collections.abc import Callable
from typing import Any

from specweaver.sandbox.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for sandbox tool factories."""

    def __init__(self) -> None:
        self._factories: dict[str, Callable[..., BaseTool]] = {}

    def register(self, name: str, factory: Callable[..., BaseTool]) -> None:
        """Register a tool factory under a specific name."""
        self._factories[name] = factory

    def create_tools(self, allowed_tools: list[str], **kwargs: Any) -> list[BaseTool]:
        """Create tool instances for the requested tool names.

        Missing or failing tool factories will log a warning and be skipped,
        rather than crashing the entire process.
        """
        tools: list[BaseTool] = []
        for name in allowed_tools:
            if name not in self._factories:
                logger.warning("Tool '%s' requested but not registered. Skipping.", name)
                continue

            try:
                tool = self._factories[name](**kwargs)
                tools.append(tool)
            except Exception as e:
                logger.exception("Failed to create tool '%s'. Skipping. Error: %s", name, e)

        return tools


def get_standard_registry() -> ToolRegistry:
    """Create a registry with standard sandbox tools pre-registered.

    Uses lazy imports within factory closures to prevent module-scope
    imports of domain dependencies, preserving boundaries and speeding up load times.

    Each factory closure cherry-picks only the kwargs it needs from
    the superset passed by create_tools(), ignoring the rest. This
    keeps ToolRegistry itself dumb (AD-7) while preventing TypeError
    crashes from incompatible factory signatures.
    """
    registry = ToolRegistry()

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

    registry.register("fs", create_fs)
    registry.register("filesystem", create_fs)
    registry.register("ast", create_ast)
    registry.register("codestructure", create_ast)
    registry.register("web", create_web)
    registry.register("mcp", create_mcp)
    registry.register("git", create_git)
    registry.register("protocol", create_protocol)

    return registry
