# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tool definitions for web intents."""

from __future__ import annotations

from specweaver.llm.models import ToolDefinition, ToolParameter

WEB_SEARCH = ToolDefinition(
    name="web_search",
    description=(
        "Search the web for information. Returns titles, snippets, and URLs. "
        "Use this to find best practices, library documentation, or reference material."
    ),
    parameters=[
        ToolParameter(name="query", type="string", description="Search query string"),
        ToolParameter(
            name="max_results", type="integer",
            description="Maximum number of search results to return",
            required=False, default=5,
        ),
    ],
)

READ_URL = ToolDefinition(
    name="read_url",
    description=(
        "Fetch and read a URL's content, converting HTML to readable text. "
        "Use this to read documentation pages, blog posts, or reference material."
    ),
    parameters=[
        ToolParameter(name="url", type="string", description="URL to fetch and read"),
        ToolParameter(
            name="max_chars", type="integer",
            description="Maximum characters of content to return",
            required=False, default=10000,
        ),
    ],
)

INTENT_DEFINITIONS: dict[str, ToolDefinition] = {
    "web_search": WEB_SEARCH,
    "read_url": READ_URL,
}
