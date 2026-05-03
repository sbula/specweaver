# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Context Assembler — fetches declared MCP resources before LLM generation.

This utility runs transparently within `flow` handlers. It parses the
frozen `TopologyContext` mapped by `TopologyGraph` for any `consumes_resources`
bindings and dynamically loads them by invoking the `MCPAtom`.

Because `MCPAtom` operates via synchronous standard I/O (async_ready: false),
it employs `asyncio.to_thread` to prevent starving the Flow Engine event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from specweaver.sandbox.mcp.core.atom import MCPAtom

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.base import RunContext

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


async def evaluate_and_fetch_mcp_context(context: RunContext) -> str | None:
    """Evaluate topology and fetch physical MCP resources lazily.

    Args:
        context: The pipeline RunContext containing the target boundary topology.

    Returns:
        A serialized YAML-like text block combining all text representations
        of the fetched resources. Returns None if zero resources were requested.
    """
    if not context.topology:
        return None

    servers = getattr(context.topology, "mcp_servers", None)
    resources = getattr(context.topology, "consumes_resources", None)

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

        # URI format expected: mcp://<server_name>/<resource>
        server_name = ""
        if uri.startswith("mcp://"):
            parts = uri[6:].split("/", 1)
            server_name = parts[0]
        else:
            snippets.append(f"{uri}:\n  |\n    ERROR: Invalid MCP URI format\n")
            continue

        server_config = servers.get(server_name)
        if not server_config:
            snippets.append(
                f"{uri}:\n  |\n    ERROR: Server '{server_name}' not found in topology bounds\n"
            )
            continue

        command = server_config.get("command")
        if isinstance(command, str):
            import shlex

            command = shlex.split(command)
        elif not isinstance(command, list):
            command = []

        args = server_config.get("args")
        if isinstance(args, list):
            command.extend(args)

        if not command:
            snippets.append(
                f"{uri}:\n  |\n    ERROR: Server '{server_name}' command configuration invalid\n"
            )
            continue

        env = server_config.get("env") or {}

        # Schedule the blocking subprocess IPC over a separate thread context
        content = await asyncio.to_thread(_sync_fetch, command, env, uri)
        snippets.append(f"{uri}:\n  |\n    " + content.replace("\n", "\n    "))
        snippets.append("\n")

    return "\n".join(snippets).strip()
