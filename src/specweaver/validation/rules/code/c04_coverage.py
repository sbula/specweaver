# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""C04: Coverage — checks that test coverage meets the threshold."""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

_DEFAULT_THRESHOLD = 70


class CoverageRule(Rule):
    """Check that test coverage meets the configured threshold."""

    def __init__(self, threshold: int = _DEFAULT_THRESHOLD) -> None:
        self._threshold = threshold

    @property
    def rule_id(self) -> str:
        return "C04"

    @property
    def name(self) -> str:
        return "Coverage"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if spec_path is None:
            return self._skip("No file path provided")

        # Find project root
        project_root = spec_path.parent
        while project_root != project_root.parent:
            if (project_root / "pyproject.toml").exists():
                break
            project_root = project_root.parent

        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    "--cov",
                    str(spec_path),
                    "--cov-report",
                    "term",
                    "-q",
                    "--tb=no",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(project_root),
            )
        except subprocess.TimeoutExpired:
            return self._fail(
                "Coverage check timed out",
                [Finding(message="Coverage check timed out after 120s", severity=Severity.ERROR)],
            )

        # Parse coverage from output (look for "TOTAL ... XX%")
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", result.stdout)
        if not match:
            return self._warn(
                "Could not parse coverage from output",
                [Finding(message="Coverage output unparseable", severity=Severity.WARNING)],
            )

        coverage = int(match.group(1))

        if coverage < self._threshold:
            return self._fail(
                f"Coverage {coverage}% below threshold {self._threshold}%",
                [
                    Finding(
                        message=f"Coverage: {coverage}% (threshold: {self._threshold}%)",
                        severity=Severity.ERROR,
                        suggestion=f"Add tests to reach at least {self._threshold}% coverage.",
                    )
                ],
            )

        return self._pass(f"Coverage: {coverage}% (threshold: {self._threshold}%)")
