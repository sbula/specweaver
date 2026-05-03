# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Any

from specweaver.core.loom.tools.mcp.definitions import (
    LIST_RESOURCES_DEF,
    LIST_SERVERS_DEF,
    READ_RESOURCE_DEF,
)
from specweaver.core.loom.tools.mcp.models import MCPToolError
from specweaver.core.loom.tools.mcp.tool import MCPExplorerTool


class ArchitectMCPInterface:
    """Role facade for the L2 Architect to survey available context mappings."""

    def __init__(self, tool: MCPExplorerTool) -> None:
        if "architect" not in tool.ROLE_INTENTS:
            raise MCPToolError("Architect role not configured on tool.")
        self._tool = tool

    def definitions(self) -> list[Any]:
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
