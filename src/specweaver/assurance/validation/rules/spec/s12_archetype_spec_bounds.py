# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import json
from pathlib import Path

from specweaver.assurance.validation.models import Finding, Rule, RuleResult


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

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if not self.required_headers:
            return self._pass(message="No structural bounds configured.")

        if not hasattr(self, "context") or "structure" not in self.context:
            return self._fail(
                message="Markdown AST payload missing or malformed.",
                findings=[Finding(message="Missing `structure` context payload.")],
            )

        try:
            skeleton = json.loads(self.context["structure"])
        except (json.JSONDecodeError, TypeError):
            return self._fail(
                message="Markdown AST payload missing or malformed.",
                findings=[
                    Finding(message="Context payload `structure` is not a valid JSON string.")
                ],
            )

        failures = []

        for header_kind, expected_list in self.required_headers.items():
            found_headers = skeleton.get(header_kind, [])
            # For simplicity, check if the expected substrings exist in the found headers ATX
            for expected in expected_list:
                found = False
                for node_text in found_headers:
                    if expected.lower() in node_text.lower():
                        found = True
                        break

                if not found:
                    failures.append(f"Missing required <{header_kind}> header: '{expected}'")

        if failures:
            return self._fail(
                message="Structural bounds failed.", findings=[Finding(message=f) for f in failures]
            )

        return self._pass(message="Structural bounds matched.")
