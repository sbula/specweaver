# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The UI's Jinja environment and its markdown sanitiser — defined once.

`render_markdown` is a **sanitiser** and its allowed-tags set is an allowlist, so it must exist
exactly once: with two copies, tightening one leaves the other permissive, and which copy an
exploit meets depends on nothing more than which module rendered the page. `htmx.py` and
`routes.py` therefore share this environment, this sanitiser and this `markdown` filter rather than
building their own.
"""

from __future__ import annotations

from pathlib import Path

import bleach
import markdown
from fastapi.templating import Jinja2Templates

#: Tags markdown may emit that bleach does not allow by default. Structural and text-level only —
#: no `script`, no `iframe`, no `style`, and no attribute is added to bleach's own allowlist, so
#: event handlers like `onclick` are stripped.
_EXTRA_TAGS = frozenset(
    {
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "div",
        "span",
        "br",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    }
)

_templates_dir = Path(__file__).parent / "templates"

#: The one Jinja environment the UI renders through. Shared so the `markdown` filter below is
#: registered once rather than per module.
templates = Jinja2Templates(directory=str(_templates_dir))


def render_markdown(text: str | None) -> str:
    """Render markdown to HTML and sanitise it.

    Sanitised rather than trusted because the text is run output: LLM-authored, and in places
    user-supplied. `fenced_code` and `tables` are enabled, which is why `pre` and the table tags
    are on the allowlist — the extension and the allowlist have to agree or code blocks arrive
    stripped.
    """
    if not text:
        return ""
    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
    return str(bleach.clean(html, tags=bleach.ALLOWED_TAGS | _EXTRA_TAGS))


templates.env.filters["markdown"] = render_markdown
