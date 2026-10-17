# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""WebTool — intent-based web search and URL reading.

Follows the same pattern as FileSystemTool and GitTool:
role-based intent gating with standardized result types.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlsplit

import httpx

from specweaver.sandbox.base import BaseTool

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition

logger = logging.getLogger(__name__)

TOOL_TIMEOUT_SECONDS = 10
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
#: Tavily takes 0 to 20; zero results is no search.
MAX_SEARCH_RESULTS = 20
#: How much of a page is read; the rest never leaves the network.
MAX_PAGE_BYTES = 2_000_000
MAX_REDIRECTS = 5


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


class WebTool(BaseTool):
    """Intent-based web operations with role-based access control.

    Args:
        role: The agent's role (determines which intents are allowed).
        api_key: The Tavily search key; without it there is no search.
    """

    def __init__(self, role: str, *, api_key: str = "") -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._role = role
        self._api_key = api_key

    @property
    def role(self) -> str:
        """The agent's role."""
        return self._role

    @property
    def web_enabled(self) -> bool:
        """Whether web search is available (has a key)."""
        return bool(self._api_key)

    # Intent methods

    def web_search(self, query: str, *, max_results: int = 5) -> WebToolResult:
        """Search the web through Tavily: a list of {title, snippet, url}."""
        self._require_intent("web_search")
        if not self.web_enabled:
            return WebToolResult(status="error", message="Web search has no key")
        count = min(max(max_results, 1), MAX_SEARCH_RESULTS)
        try:
            response = httpx.post(
                TAVILY_SEARCH_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"query": query, "max_results": count, "search_depth": "basic"},
                timeout=TOOL_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            items = response.json().get("results", [])[:count]
        except Exception as exc:
            logger.warning("web_search failed: %s", exc)
            return WebToolResult(status="error", message=str(exc))
        results = [
            {"title": i.get("title", ""), "snippet": i.get("content", ""), "url": i.get("url", "")}
            for i in items
        ]
        return WebToolResult(status="success", data=results)

    def read_url(self, url: str, *, max_chars: int = 10000) -> WebToolResult:
        """A public page as text: {url, content}, the url being where redirects ended."""
        self._require_intent("read_url")
        try:
            final_url, raw = _fetch_public(url)
        except Exception as exc:
            logger.warning("read_url failed: %s", exc)
            return WebToolResult(status="error", message=str(exc))

        content = _strip_html(raw)
        result: dict[str, Any] = {"url": final_url, "content": content}
        if len(content) > max_chars:
            result["content"] = content[:max_chars]
            result["truncated"] = True
            result["warning"] = f"Content truncated to {max_chars} characters"
        return WebToolResult(status="success", data=result)

    # Internal: role gating
    def definitions(self) -> list[ToolDefinition]:
        from specweaver.sandbox.web.interfaces.definitions import INTENT_DEFINITIONS
        from specweaver.sandbox.web.interfaces.tool import ROLE_INTENTS

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
# Public addresses only
# ---------------------------------------------------------------------------


class NotPublicError(ValueError):
    """The URL leads somewhere other than the public internet."""


def _check_public(url: str) -> None:
    """Refuse a URL that is not http(s), or whose host resolves to any non-public address."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise NotPublicError(f"only http and https URLs are read: {url!r}")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise NotPublicError(f"{parts.hostname} does not resolve: {exc}") from exc
    for info in infos:
        address = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if not address.is_global or address.is_multicast:
            raise NotPublicError(f"{parts.hostname} is not a public address ({address})")


def _fetch_public(url: str) -> tuple[str, str]:
    """Where the redirects ended and the page there, every hop checked before it is asked."""
    with httpx.Client(follow_redirects=False, timeout=TOOL_TIMEOUT_SECONDS) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _check_public(url)
            with client.stream("GET", url, headers={"User-Agent": "SpecWeaver/1.0"}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["Location"])
                    continue
                response.raise_for_status()
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) >= MAX_PAGE_BYTES:
                        break
                encoding = response.encoding or "utf-8"
                return url, body[:MAX_PAGE_BYTES].decode(encoding, errors="replace")
    raise NotPublicError(f"more than {MAX_REDIRECTS} redirects")


# ---------------------------------------------------------------------------
# HTML stripping helper
# ---------------------------------------------------------------------------


def _strip_html(html: str) -> str:
    """Strip HTML tags and convert to plain text.

    Uses html2text if available, falls back to regex.
    """
    try:
        import html2text  # type: ignore

        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # No line wrapping
        return str(h.handle(html)).strip()
    except ImportError:  # expected: html2text is optional; tags are stripped by regex
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
