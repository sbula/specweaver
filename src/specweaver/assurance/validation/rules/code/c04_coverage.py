# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C04: Coverage — checks that test coverage meets the threshold.

Delegates pytest+coverage execution to the shared PythonQARunner
from the commons layer, eliminating duplicate subprocess handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

if TYPE_CHECKING:
    from pathlib import Path

_DEFAULT_THRESHOLD = 70


class CoverageRule(Rule):
    """Check that test coverage meets the configured threshold."""

    PARAM_MAP: ClassVar[dict[str, str]] = {
        "fail_threshold": "threshold",
    }

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

        # Delegate to QARunnerAtom via intent
        from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

        atom = QARunnerAtom(cwd=project_root)
        try:
            result = atom.run(
                {
                    "intent": "run_tests",
                    "target": str(spec_path),
                    "kind": "",
                    "timeout": 120,
                    "coverage": True,
                    "coverage_threshold": self._threshold,
                }
            )

            if result.status == "failed" and "timed out" in (result.message or "").lower():
                raise TimeoutError("Coverage check timed out")
        except TimeoutError:
            return self._fail(
                "Coverage check timed out",
                [Finding(message="Coverage check timed out after 120s", severity=Severity.ERROR)],
            )

        exports = result.exports or {}
        coverage = exports.get("coverage_pct")

        if coverage is None:
            return self._warn(
                "Could not parse coverage from output",
                [Finding(message="Coverage output unparseable", severity=Severity.WARNING)],
            )

        coverage_int = int(coverage)

        if coverage_int < self._threshold:
            return self._fail(
                f"Coverage {coverage_int}% below threshold {self._threshold}%",
                [
                    Finding(
                        message=f"Coverage: {coverage_int}% (threshold: {self._threshold}%)",
                        severity=Severity.ERROR,
                        suggestion=f"Add tests to reach at least {self._threshold}% coverage.",
                    )
                ],
            )

        return self._pass(f"Coverage: {coverage_int}% (threshold: {self._threshold}%)")
