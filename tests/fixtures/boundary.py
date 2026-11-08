# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real, frozen boundary for tests that hand the MCP tool its servers: never a mock."""

from __future__ import annotations

from typing import Any

from specweaver.graph.topology.topology import TopologyNode


def declared_boundary(servers: dict[str, dict[str, Any]] | None = None) -> TopologyNode:
    """A boundary named `demo` declaring `servers`, as one loaded from a `context.yaml` would be."""
    return TopologyNode(
        name="demo",
        level="module",
        purpose="A test boundary.",
        archetype="adapter",
        mcp_servers=servers or {},
    )
