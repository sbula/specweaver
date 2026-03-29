# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""WebTool — intent-based web search and URL reading.

Follows the same pattern as FileSystemTool and GitTool:
role-based intent gating with standardized result types.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.llm.models import ToolDefinition

logger = logging.getLogger(__name__)

TOOL_TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WebToolResult:
    """Result from a WebTool intent execution."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


# ---------------------------------------------------------------------------
# Role → allowed intents
# ---------------------------------------------------------------------------

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "planner": frozenset({"web_search", "read_url"}),
    "reviewer": frozenset({"web_search", "read_url"}),
    "implementer": frozenset({"web_search", "read_url"}),
    "drafter": frozenset({"web_search", "read_url"}),
}


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class WebToolError(Exception):
    """Raised when a WebTool operation is blocked by role or configuration."""


# ---------------------------------------------------------------------------
# WebTool
# ---------------------------------------------------------------------------


class WebTool:
    """Intent-based web operations with role-based access control.

    Args:
        role: The agent's role (determines which intents are allowed).
        api_key: Google Custom Search API key.
        engine_id: Programmable Search Engine ID (cx).
    """

    def __init__(
        self,
        role: str,
        *,
        api_key: str = "",
        engine_id: str = "",
    ) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._role = role
        self._api_key = api_key
        self._engine_id = engine_id

    @property
    def role(self) -> str:
        """The agent's role."""
        return self._role

    @property
    def web_enabled(self) -> bool:
        """Whether web search is available (has credentials)."""
        return bool(self._api_key and self._engine_id)

    # Intent methods

    def web_search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> WebToolResult:
        """Search the web using Google Custom Search API.

        Args:
            query: Search query string.
            max_results: Maximum number of results.

        Returns:
            WebToolResult with data=list of {title, snippet, url}.
        """
        self._require_intent("web_search")
        if not self.web_enabled:
            return WebToolResult(
                status="error",
                message="Web search not available (missing API credentials)",
            )

        import urllib.parse
        import urllib.request

        params = urllib.parse.urlencode(
            {
                "key": self._api_key,
                "cx": self._engine_id,
                "q": query,
                "num": min(max_results, 10),  # API max is 10
            }
        )
        url = f"https://www.googleapis.com/customsearch/v1?{params}"

        try:
            import json

            req = urllib.request.Request(url, headers={"User-Agent": "SpecWeaver/1.0"})
            with urllib.request.urlopen(req, timeout=TOOL_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results: list[dict[str, Any]] = []
            for item in data.get("items", [])[:max_results]:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "url": item.get("link", ""),
                    }
                )
            return WebToolResult(status="success", data=results)

        except Exception as exc:
            logger.warning("web_search failed: %s", exc)
            return WebToolResult(status="error", message=str(exc))

    def read_url(
        self,
        url: str,
        *,
        max_chars: int = 10000,
    ) -> WebToolResult:
        """Fetch and read a URL's content, converting HTML to text.

        Args:
            url: URL to fetch.
            max_chars: Maximum characters to return.

        Returns:
            WebToolResult with data={url, content}.
        """
        self._require_intent("read_url")

        import urllib.request

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SpecWeaver/1.0"})
            with urllib.request.urlopen(req, timeout=TOOL_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8", errors="replace")

            content = _strip_html(raw)

            result: dict[str, Any] = {"url": url, "content": content}
            if len(content) > max_chars:
                result["content"] = content[:max_chars]
                result["truncated"] = True
                result["warning"] = f"Content truncated to {max_chars} characters"
            return WebToolResult(status="success", data=result)

        except Exception as exc:
            logger.warning("read_url failed: %s", exc)
            return WebToolResult(status="error", message=str(exc))

    # Internal: role gating
    def definitions(self) -> list[ToolDefinition]:
        from specweaver.loom.tools.web.definitions import INTENT_DEFINITIONS
        from specweaver.loom.tools.web.tool import ROLE_INTENTS

        return [d for name, d in INTENT_DEFINITIONS.items() if name in ROLE_INTENTS[self._role]]

    def _require_intent(self, intent: str) -> None:
        """Raise if the current role doesn't have this intent."""
        if intent not in ROLE_INTENTS[self._role]:
            msg = (
                f"Intent {intent!r} is not allowed for role {self._role!r}. "
                f"Allowed: {sorted(ROLE_INTENTS[self._role])}"
            )
            raise WebToolError(msg)


# ---------------------------------------------------------------------------
# HTML stripping helper
# ---------------------------------------------------------------------------


def _strip_html(html: str) -> str:
    """Strip HTML tags and convert to plain text.

    Uses html2text if available, falls back to regex.
    """
    try:
        import html2text  # type: ignore[import-not-found]

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # No line wrapping
        return str(h.handle(html)).strip()
    except ImportError:
        # Fallback: basic regex tag removal
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
