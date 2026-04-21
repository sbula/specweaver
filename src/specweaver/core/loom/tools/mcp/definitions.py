# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from specweaver.infrastructure.llm.models import ToolDefinition, ToolParameter

LIST_SERVERS_DEF = ToolDefinition(
    name="list_servers",
    description="Returns a list of available Model Context Protocol (MCP) server integration names configured in the project topology.",
    parameters=[],
)

LIST_RESOURCES_DEF = ToolDefinition(
    name="list_resources",
    description="Explores external JSON-RPC boundaries by returning a list of addressable URIs available from a designated target MCP proxy server.",
    parameters=[
        ToolParameter(
            name="server_name",
            type="string",
            description="The exact target server name matching the context topology.",
            required=True,
        )
    ],
)

READ_RESOURCE_DEF = ToolDefinition(
    name="read_resource",
    description="Reads the physical state or schema payloads mapped to a specific MCP URI targeting an active server proxy.",
    parameters=[
        ToolParameter(
            name="server_name",
            type="string",
            description="The target server name.",
            required=True,
        ),
        ToolParameter(
            name="uri",
            type="string",
            description="The specific resource URI exposed by `list_resources`.",
            required=True,
        ),
    ],
)
