# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a prompt is told about a neighbouring module: its name, purpose, archetype and constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TopologyContext:
    """Structured context about a module for prompt injection.

    Produced by TopologyGraph.format_context_summary() and consumed
    by PromptBuilder.add_topology().
    """

    name: str
    purpose: str
    archetype: str
    relationship: str  # e.g. "direct dependency", "2-hop consumer"
    constraints: list[str] = field(default_factory=list)
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    consumes_resources: list[str] = field(default_factory=list)

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
