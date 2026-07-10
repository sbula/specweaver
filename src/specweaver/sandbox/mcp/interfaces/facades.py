# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.mcp.interfaces.definitions import (
    LIST_RESOURCES_DEF,
    LIST_SERVERS_DEF,
    READ_RESOURCE_DEF,
)
from specweaver.sandbox.mcp.interfaces.models import MCPToolError

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition
    from specweaver.sandbox.mcp.interfaces.tool import MCPExplorerTool

logger = logging.getLogger(__name__)


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

    def list_servers(self, **kwargs: Any) -> Any:
        return self._tool._intent_list_servers(kwargs)

    def list_resources(self, **kwargs: Any) -> Any:
        return self._tool._intent_list_resources(kwargs)

    def read_resource(self, **kwargs: Any) -> Any:
        return self._tool._intent_read_resource(kwargs)

    def is_visible(self) -> bool:
        """Determines if this interface should be exported to the agent prompt."""
        return True


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
