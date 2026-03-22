# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""UI Requirement Extraction for Planning phase (3.6b)."""

from __future__ import annotations

import re


class UIRequirements:
    """Extracted UI requirements from a spec."""

    def __init__(self, description: str) -> None:
        self.description = description


_SECTION_RE = re.compile(
    r"^##\s+(?:Protocol|Contract)\s*\n(.*?)(?=\n##\s|\Z)",
    re.MULTILINE | re.IGNORECASE | re.DOTALL,
)

_UI_KEYWORDS = frozenset(
    {
        "ui",
        "user interface",
        "web",
        "frontend",
        "screen",
        "dashboard",
        "mockup",
        "view",
        "page",
        "html",
        "css",
        "react",
        "component",
        "browser",
        "button",
        "layout",
    }
)


def extract_ui_requirements(spec_content: str) -> UIRequirements | None:
    """Extract UI requirements from Protocol/Contract sections.

    Returns None if the spec does not appear to describe UI/web components.
    """
    matches = list(_SECTION_RE.finditer(spec_content))
    if not matches:
        return None

    # Aggregate all matched sections in case there are multiple
    contents = [m.group(1).strip() for m in matches if m.group(1).strip()]
    if not contents:
        return None

    combined_content = "\n\n".join(contents)
    content_lower = combined_content.lower()

    if any(kw in content_lower for kw in _UI_KEYWORDS):
        return UIRequirements(description=combined_content)

    return None
