# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C12: Archetype Code Bounds — checks that code matches required framework boundary markers."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path


class C12ArchetypeCodeBoundsRule(Rule):
    """Enforce architectural constraints mapped by Pipeline framework templates.

    Expects `framework_markers` inside the execution context parameters.
    """

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "extra:required_markers": "required_markers",
        "extra:forbidden_markers": "forbidden_markers",
    }

    def __init__(
        self,
        required_markers: list[str] | None = None,
        forbidden_markers: list[str] | None = None,
    ) -> None:
        """Initialize with bounding constraints."""
        self.required_markers = required_markers or []
        self.forbidden_markers = forbidden_markers or []

    @property
    def rule_id(self) -> str:
        return "C12"

    @property
    def name(self) -> str:
        return "Archetype Code Bounds"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        """Check the validation context for necessary architectural keys."""
        findings: list[Finding] = []

        # Extract mapped indicators from parsed tree-sitter bindings.
        # Ensure we always fallback to a dict safely.
        markers = self.context.get("framework_markers") or {}

        # 1. Require Markers
        for marker in self.required_markers:
            if marker not in markers:
                findings.append(
                    Finding(
                        message=f"Missing required framework marker: '{marker}'. Ensure module implements the correct bindings.",
                        severity=Severity.ERROR,
                        suggestion=f"Provide the exact implementation logic bounding '{marker}'.",
                    )
                )

        # 2. Forbid Markers
        for marker in self.forbidden_markers:
            if marker in markers:
                findings.append(
                    Finding(
                        message=f"Found forbidden framework boundary: '{marker}'. Artifact breaches bounded boundaries.",
                        severity=Severity.ERROR,
                        suggestion=f"Refactor to remove '{marker}' and isolate logic.",
                    )
                )

        if findings:
            return self._fail(
                f"Archetype boundaries breached: {len(findings)} violations", findings
            )

        return self._pass("Code safely aligns to archetype bounded constraints")
