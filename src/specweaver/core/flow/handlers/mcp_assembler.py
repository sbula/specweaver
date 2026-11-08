# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""MCP resource assembler — fetches declared MCP resources before LLM generation.

This utility runs transparently within `flow` handlers. It parses the
frozen `TopologyContext` mapped by `TopologyGraph` for any `consumes_resources`
bindings and dynamically loads them by invoking the `MCPAtom`.

Because `MCPAtom` operates via synchronous standard I/O (async_ready: false),
it employs `asyncio.to_thread` to prevent starving the Flow Engine event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.mcp.core.atom import MCPAtom, declared_command

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.core.flow.run_state.run_context import RunContext

logger = logging.getLogger(__name__)


def _sync_fetch(command: list[str], env: dict[str, str], uri: str) -> str:
    """Synchronous bridge to invoke the MCP Atom to bypass event loop deadlocks."""
    atom = MCPAtom(command=command, env=env)
    try:
        # First ensure initialization completes properly before fetching resources
        init_res = atom.run({"intent": "initialize"})
        if init_res.status != "SUCCESS":
            return f"ERROR init resource: {init_res.message}"

        # Pass read_resource intent synchronously
        result = atom.run({"intent": "read_resource", "params": {"uri": uri}})

        # Unpack the contents mapped from the Atom JSON-RPC interface wrapper.
        contents = result.exports.get("contents", [])
        if not contents:
            return f"No resource data returned for {uri}"

        # Combine all physical text payloads together, shredding out the protocol metadata.
        snippets = []
        for payload in contents:
            text_part = payload.get("text", "")
            snippets.append(str(text_part))

        return "\\n".join(snippets)
    except Exception as exc:
        logger.warning("MCP Assembler: Failed to fetch %s — %s", uri, exc)
        return f"ERROR fetching resource: {exc}"


def _resolve_mcp_command(
    uri: str, servers: Mapping[str, Mapping[str, Any]]
) -> tuple[list[str], dict[str, Any], str | None]:
    """`(command, env, error)` for one `mcp://<server>/<resource>` URI.

    `error` is non-None for each of the three ways a URI can fail to name a runnable server, and
    the caller renders it into the snippet, rather than the three refusals being three `continue`s
    inside the fetch loop.
    """
    if not uri.startswith("mcp://"):
        return [], {}, "Invalid MCP URI format"

    server_name = uri[6:].split("/", 1)[0]
    server_config = servers.get(server_name)
    if not server_config:
        return [], {}, f"Server '{server_name}' not found in topology bounds"

    try:
        command = declared_command(server_name, server_config)
    except ValueError as exc:
        return [], {}, str(exc)

    return command, dict(server_config.get("env") or {}), None


async def evaluate_and_fetch_mcp_context(context: RunContext) -> str | None:
    """Evaluate topology and fetch physical MCP resources lazily.

    Args:
        context: The pipeline RunContext containing the target boundary topology.

    Returns:
        A serialized YAML-like text block combining all text representations
        of the fetched resources. Returns None if zero resources were requested.
    """
    boundary = context.graph.target_boundary
    if boundary is None:
        return None

    servers = boundary.mcp_servers
    resources = boundary.consumes_resources

    if not servers or not resources:
        return None

    logger.debug(
        "MCP Assembler: Pre-fetching %d resources across %d server configurations...",
        len(resources),
        len(servers),
    )

    snippets: list[str] = ["# Pre-Fetched MCP Context Boundaries\n"]

    for uri in resources:
        logger.debug("MCP Assembler: Fetching %s...", uri)

        command, env, error = _resolve_mcp_command(uri, servers)
        if error is not None:
            snippets.append(f"{uri}:\n  |\n    ERROR: {error}\n")
            continue

        # Schedule the blocking subprocess IPC over a separate thread context
        content = await asyncio.to_thread(_sync_fetch, command, env, uri)
        snippets.append(f"{uri}:\n  |\n    " + content.replace("\n", "\n    "))
        snippets.append("\n")

    return "\n".join(snippets).strip()
