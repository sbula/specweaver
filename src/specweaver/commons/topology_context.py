# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a run is told about the module graph: a neighbour's context, the target boundary, the graph.

The two protocols let a run carry the boundary and the graph without importing `graph`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from specweaver.commons.frozen import freeze


@runtime_checkable
class DeclaredBoundary(Protocol):
    """The boundary a run works in, as its `context.yaml` declares it.

    `consumes` is what tells it from a neighbour's `TopologyContext`, which also carries servers.
    """

    @property
    def name(self) -> str: ...
    @property
    def consumes(self) -> Sequence[str]: ...
    @property
    def mcp_servers(self) -> Mapping[str, Mapping[str, Any]]: ...
    @property
    def consumes_resources(self) -> Sequence[str]: ...


@runtime_checkable
class ModuleImpact(Protocol):
    """The module graph, as far as a run asks it: what a change to a module reaches."""

    def impact_of(self, module: str) -> set[str]: ...


@dataclass(frozen=True)
class TopologyContext:
    """Structured context about a module for prompt injection.

    Produced by TopologyGraph.contexts_for() and consumed
    by PromptBuilder.add_topology(). Shared by every step of a run, so frozen at every depth.
    """

    name: str
    purpose: str
    archetype: str
    relationship: str  # e.g. "direct dependency", "2-hop consumer"
    constraints: Sequence[str] = ()
    mcp_servers: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    consumes_resources: Sequence[str] = ()

    def __post_init__(self) -> None:
        for name in ("constraints", "mcp_servers", "consumes_resources"):
            object.__setattr__(self, name, freeze(getattr(self, name)))

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        """Return natively formatted topology XML block."""
        constraints_str = ", ".join(self.constraints) if self.constraints else "none"
        content = (
            f"  - {self.name} ({self.relationship}): "
            f"{self.purpose} [archetype={self.archetype}, "
            f"constraints={constraints_str}]"
        )
        if char_limit is not None:
            content = content[:char_limit] + "\n[truncated]"
        return f"<topology>\n{content}\n</topology>"

    def get_prompt_label(self) -> str:
        """Return the module name as label."""
        return self.name
