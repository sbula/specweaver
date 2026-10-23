# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from specweaver.assurance.validation.models import Finding, Rule, RuleResult, Severity

logger = logging.getLogger(__name__)

_REQUIREMENT_ID = re.compile(r"\b(?:N)?FR-\d+[a-z]?\b")


def traced_requirements(root: Path, analyzer_factory: Any = None) -> set[str]:
    """Every requirement id that a `@trace` tag in a test file under `root` names."""
    if analyzer_factory is None:
        from specweaver.workspace.analyzers.factory import AnalyzerFactory

        analyzer_factory = AnalyzerFactory
    mapped_ids: set[str] = set()
    for analyzer in analyzer_factory.get_all_analyzers():
        try:
            mapped_ids.update(analyzer.extract_test_mapped_requirements(root))
        except Exception as e:
            logger.debug("Failed extracting tags via %s: %s", type(analyzer).__name__, e)
    return mapped_ids


def requirement_coverage(
    spec_text: str, coder_root: Path, scenarios_root: Path | None
) -> dict[str, str]:
    """Per requirement of the spec: `both`, `coder`, `scenario` or `none` covers it."""
    coder = traced_requirements(coder_root)
    scenario = (
        traced_requirements(scenarios_root)
        if scenarios_root is not None and scenarios_root.is_dir()
        else set()
    )
    sides = {(True, True): "both", (True, False): "coder", (False, True): "scenario"}
    return {
        rid: sides.get((rid in coder, rid in scenario), "none")
        for rid in sorted(set(_REQUIREMENT_ID.findall(spec_text)))
    }


class TraceabilityRule(Rule):
    """Rule to ensure all requirements (FRs/NFRs) in a spec are explicitly traced in implementation test code."""

    @property
    def rule_id(self) -> str:
        return "C09"

    @property
    def name(self) -> str:
        return "Traceability Matrix"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        """Scan project specs for requirements and map them to AST trace comments in test files."""
        project_root = self._find_project_root(spec_path)
        if not project_root:
            return self._pass("No valid workspace root found to assess traceability.")

        # 1. Extract targets greedily from all spec files
        target_ids = self._extract_all_requirements(project_root)

        if not target_ids:
            return self._pass("No explicit requirement tags (FR-x/NFR-x) found in spec.")

        # 2. Extract found traces dynamically
        mapped_ids = self._find_and_parse_tests(project_root)

        # 3. Calculate missing
        missing_ids = target_ids - mapped_ids

        if missing_ids:
            findings = [
                Finding(
                    message=f"Requirement {req_id} is unmapped in test code.",
                    severity=Severity.ERROR,
                )
                for req_id in sorted(missing_ids)
            ]
            return self._fail(
                message=f"Missing traceability: {len(missing_ids)} requirements lack # @trace() coverage in test code.",
                findings=findings,
            )

        return self._pass(f"All {len(target_ids)} requirements successfully traced to test code.")

    def _find_project_root(self, spec_path: Path | None) -> Path | None:
        from specweaver.assurance.validation.project_root import walk_up

        given = self.context.get("project_root")
        if given is not None:
            return Path(given)
        if spec_path is None:
            return None
        markers = ("pyproject.toml", "package.json", ".git", ".specweaver")
        return next(
            (f for f in walk_up(spec_path.parent, None) if any((f / m).exists() for m in markers)),
            None,
        )

    def _extract_all_requirements(self, project_root: Path) -> set[str]:
        target_ids: set[str] = set()
        specs_dir = project_root / "specs"
        if not specs_dir.exists():
            return target_ids

        for spec_file in specs_dir.rglob("*.md"):
            try:
                content = spec_file.read_text(encoding="utf-8")
                found = re.findall(r"\b(?:N)?FR-\d+\b", content)
                target_ids.update(found)
            except Exception as e:
                logger.debug("Failed reading spec file %s: %s", spec_file, e)
        return target_ids

    def _find_and_parse_tests(self, project_root: Path) -> set[str]:
        """Find test files using AnalyzerFactory and aggregate their trace tags."""
        analyzer_factory = (
            self.context.get("analyzer_factory")
            if hasattr(self, "context") and self.context
            else None
        )
        return traced_requirements(project_root, analyzer_factory)
