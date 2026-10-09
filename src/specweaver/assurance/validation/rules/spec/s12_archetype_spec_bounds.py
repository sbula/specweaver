# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import re
from pathlib import Path
from typing import Any

from specweaver.assurance.validation.models import Finding, Rule, RuleResult
from specweaver.commons import json


class S12ArchetypeSpecBoundsRule(Rule):
    """Validates structural DOM constraints mapped out via Markdown Skeletons."""

    def __init__(self, required_headers: dict[str, list[str]] | None = None) -> None:
        self.required_headers = required_headers or {}

    @property
    def rule_id(self) -> str:
        return "S12"

    @property
    def name(self) -> str:
        return "Archetype Spec Bounds"

    def _missing_headers(self, skeleton: dict[str, Any]) -> list[str]:
        """Every configured header the skeleton does not carry, matched as a substring.

        Case-insensitive and by containment on purpose: the bound is "this section exists", not
        "its title is exactly this".
        """
        return [
            f"Missing required <{header_kind}> header: '{expected}'"
            for header_kind, expected_list in self.required_headers.items()
            for expected in expected_list
            if not any(
                expected.lower() in node_text.lower() for node_text in skeleton.get(header_kind, [])
            )
        ]

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if not self.required_headers:
            return self._pass(message="No structural bounds configured.")
        if not isinstance(self.required_headers, dict):
            return self._fail(
                message="required_headers must map a header level to its titles, e.g. h2: [...]",
                findings=[Finding(message="required_headers is not a map of header levels.")],
            )

        structure = getattr(self, "context", {}).get("structure")
        failures = self._missing_headers(_headings(structure if structure else spec_text))

        if failures:
            return self._fail(
                message="Structural bounds failed.", findings=[Finding(message=f) for f in failures]
            )

        return self._pass(message="Structural bounds matched.")


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def _headings(structure: Any) -> dict[str, list[str]]:
    """Headings per level (`h1`..`h6`): from a JSON map, else from Markdown text."""
    if isinstance(structure, dict):
        return structure
    try:
        parsed = json.loads(structure)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed
    levels: dict[str, list[str]] = {}
    for marks, title in _HEADING.findall(str(structure)):
        levels.setdefault(f"h{len(marks)}", []).append(title)
    return levels
