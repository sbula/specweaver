# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rendering discovered standards as the markdown a constitution embeds.

Split out of `_helpers.py` by `TECH-015`. Presentation, not discovery: these build table rows and
sections, and know nothing about how the standards were found.
"""

from __future__ import annotations

from typing import Any


def build_tech_stack_rows(languages: list[str]) -> str:
    """Build markdown table rows for the Tech Stack section."""
    if not languages:
        return "| Language | TODO | TODO | TODO |"

    lang_info = {
        "python": ("Python", "3.11+", "Primary language"),
        "javascript": ("JavaScript", "ES2022+", "Frontend / Node.js"),
        "typescript": ("TypeScript", "5.x+", "Type-safe JavaScript"),
    }

    rows: list[str] = []
    for lang in languages:
        info = lang_info.get(lang.lower(), (lang.capitalize(), "TODO", "TODO"))
        rows.append(f"| Language | {info[0]} | {info[1]} | {info[2]} |")

    return "\n".join(rows)


def build_standards_section(standards: list[dict[str, Any]]) -> str:
    """Build markdown bullet list from confirmed standards."""
    from specweaver.commons import json

    if not standards:
        return (
            "- TODO: Naming conventions\n"
            "- TODO: Error handling patterns\n"
            "- TODO: Documentation requirements"
        )

    lines: list[str] = []
    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = {}
    for s in standards:
        cat = s.get("category", "unknown")
        by_category.setdefault(cat, []).append(s)

    category_labels = {
        "naming": "Naming Conventions",
        "error_handling": "Error Handling",
        "type_hints": "Type Annotations",
        "docstrings": "Documentation Style",
        "import_patterns": "Import Organization",
        "test_patterns": "Testing Conventions",
        "async_patterns": "Async Patterns",
        "jsdoc": "JSDoc Documentation",
        "tsdoc": "TSDoc Documentation",
    }

    for category, items in sorted(by_category.items()):
        label = category_labels.get(category, category.replace("_", " ").title())
        lines.append(f"### {label}")
        lines.append("")
        for item in items:
            data = json.loads(item["data"]) if isinstance(item["data"], str) else item["data"]
            scope = item.get("scope", ".")
            lang = item.get("language", "unknown")
            conf = item.get("confidence", 0.0)
            prefix = f"[{scope}/{lang}]" if scope != "." else f"[{lang}]"
            lines.append(f"**{prefix}** (confidence: {conf:.0%})")
            for k, v in data.items():
                lines.append(f"- {k.replace('_', ' ').title()}: `{v}`")
            lines.append("")

    return "\n".join(lines).rstrip()
