# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""MCP-like role interfaces for web operations.

Each interface class exposes ONLY the intents allowed for its role.
The LLM agent receives one of these — it physically cannot call
methods that don't exist on its interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.loom.tools.web.tool import WebTool, WebToolResult

if TYPE_CHECKING:
    from specweaver.llm.models import ToolDefinition

# ---------------------------------------------------------------------------
# Role-specific interfaces
# ---------------------------------------------------------------------------


class PlannerWebInterface:
    """Web interface for the Planner role.

    Allowed intents: web_search, read_url.
    """

    def __init__(self, tool: WebTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def web_search(self, query: str, **kwargs: object) -> WebToolResult:
        """Search the web."""
        return self._tool.web_search(query, **kwargs)  # type: ignore[arg-type]

    def read_url(self, url: str, **kwargs: object) -> WebToolResult:
        """Fetch and read a URL's content."""
        return self._tool.read_url(url, **kwargs)  # type: ignore[arg-type]


class ReviewerWebInterface:
    """Web interface for the Reviewer role.

    Allowed intents: web_search, read_url.
    """

    def __init__(self, tool: WebTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def web_search(self, query: str, **kwargs: object) -> WebToolResult:
        """Search the web."""
        return self._tool.web_search(query, **kwargs)  # type: ignore[arg-type]

    def read_url(self, url: str, **kwargs: object) -> WebToolResult:
        """Fetch and read a URL's content."""
        return self._tool.read_url(url, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

WebInterface = PlannerWebInterface | ReviewerWebInterface

_ROLE_INTERFACE_MAP: dict[
    str, type[PlannerWebInterface] | type[ReviewerWebInterface],
] = {
    "planner": PlannerWebInterface,
    "reviewer": ReviewerWebInterface,
}


def create_web_interface(
    role: str,
    *,
    api_key: str = "",
    engine_id: str = "",
) -> PlannerWebInterface | ReviewerWebInterface:
    """Create a role-specific web interface.

    Args:
        role: The agent's role ("planner", "reviewer").
        api_key: Google Custom Search API key.
        engine_id: Programmable Search Engine ID (cx).

    Returns:
        A role-specific interface with only the allowed methods.

    Raises:
        ValueError: If the role is unknown.
    """
    if role not in _ROLE_INTERFACE_MAP:
        msg = f"Unknown role: {role!r}. Known roles: {sorted(_ROLE_INTERFACE_MAP)}"
        raise ValueError(msg)

    tool = WebTool(role=role, api_key=api_key, engine_id=engine_id)

    interface_cls = _ROLE_INTERFACE_MAP[role]
    return interface_cls(tool)
