# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""MCP Explorer Tool - Context mapping exploration via JSON-RPC."""

from __future__ import annotations

import logging
from typing import Any

from specweaver.commons import json
from specweaver.core.loom.commons.mcp.executor import MCPExecutor, MCPExecutorError
from specweaver.core.loom.tools.mcp.models import ToolResult

logger = logging.getLogger(__name__)


class MCPExplorerTool:
    """Tool for L2 Architect exploration of external MCP interfaces."""

    def __init__(self, context: Any) -> None:
        self.context = context
        self.ROLE_INTENTS = {
            "architect": frozenset({"list_servers", "list_resources", "read_resource"})
        }

    def _execute_mcp_query(
        self, server_name: str, method: str, params: dict[str, Any]
    ) -> ToolResult:
        """Helper to invoke a short-lived MCP bounds query."""
        if not self.context or not getattr(self.context, "topology", None):
            return ToolResult(status="error", message="Context Topology missing.")

        servers = getattr(self.context.topology, "mcp_servers", {})
        if server_name not in servers:
            return ToolResult(status="error", message=f"Unknown MCP server '{server_name}'.")

        server_config = servers[server_name]
        command = server_config.get("command")
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if not command:
            return ToolResult(
                status="error",
                message=f"MCP server '{server_name}' missing target executable command bounds.",
            )

        full_command = [*command, *args] if isinstance(command, list) else [command, *args]

        executor = None
        try:
            executor = MCPExecutor(command=full_command, env=env)

            # Protocol demands initialize -> list -> close
            init_payload = {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "specweaver-architect", "version": "1.0.0"},
            }
            executor.call_rpc(method="initialize", params=init_payload, timeout=5.0)
            executor.call_rpc(method="notifications/initialized", params={}, timeout=2.0)

            response = executor.call_rpc(method=method, params=params, timeout=10.0)
            result_data = response.get("result", {})
            return ToolResult(status="success", data=json.dumps(result_data))
        except MCPExecutorError as e:
            logger.warning("MCPExplorerTool execution failed for %s: %s", server_name, e)
            return ToolResult(status="error", message=f"Execution Error against {server_name}: {e}")
        finally:
            if executor:
                executor.close()

    def _intent_list_servers(self, inputs: dict[str, Any]) -> ToolResult:
        if not getattr(self.context, "topology", None) or not getattr(
            self.context.topology, "mcp_servers", None
        ):
            return ToolResult(status="success", data="[]")
        mcp_servers = self.context.topology.mcp_servers
        return ToolResult(status="success", data=json.dumps(list(mcp_servers.keys())))

    def _intent_list_resources(self, inputs: dict[str, Any]) -> ToolResult:
        server_name = inputs.get("server_name")
        if not server_name:
            return ToolResult(status="error", message="Missing server_name")
        return self._execute_mcp_query(server_name, "resources/list", {})

    def _intent_read_resource(self, inputs: dict[str, Any]) -> ToolResult:
        server_name = inputs.get("server_name")
        uri = inputs.get("uri")
        if not server_name or not uri:
            return ToolResult(status="error", message="Missing server_name or uri")
        return self._execute_mcp_query(server_name, "resources/read", {"uri": uri})
