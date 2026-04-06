# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.validation.models import Finding, Rule, RuleResult, Severity

logger = logging.getLogger(__name__)


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
                Finding(message=f"Requirement {req_id} is unmapped in test code.", severity=Severity.ERROR)
                for req_id in sorted(missing_ids)
            ]
            return self._fail(
                message=f"Missing traceability: {len(missing_ids)} requirements lack # @trace() coverage in test code.",
                findings=findings,
            )

        return self._pass(f"All {len(target_ids)} requirements successfully traced to test code.")

    def _find_project_root(self, spec_path: Path | None) -> Path | None:
        if spec_path is None:
            return None

        project_root = spec_path.parent
        while project_root != project_root.parent:
            if (project_root / "pyproject.toml").exists() or (project_root / "package.json").exists() or (project_root / ".git").exists() or (project_root / ".specweaver").exists():
                return project_root
            project_root = project_root.parent

        # Fallback to current directory if not found upward
        return None

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

    def _discover_test_files(self, project_root: Path) -> list[Path]:
        if not project_root.is_dir():
            return []

        test_files = list(project_root.rglob("test_*.py"))
        test_files.extend(project_root.rglob("*_test.py"))
        return test_files

    def _find_and_parse_tests(self, project_root: Path) -> set[str]:
        """Find test files and parse ASTs to extract trace tags cleanly from comments."""
        test_files = self._discover_test_files(project_root)
        if not test_files:
            return set()

        mapped_ids: set[str] = set()

        try:
            import tree_sitter
            import tree_sitter_python
            parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
        except ImportError:
            logger.warning("tree_sitter or tree_sitter_python not installed, skipping trace extraction.")
            return set()

        for path in test_files:
            try:
                source = path.read_bytes()
                tree = parser.parse(source)
                self._extract_traces(tree.root_node, source, mapped_ids)
            except Exception as e:
                logger.debug("Failed AST parsing for traceability on %s: %s", path, e)

        return mapped_ids

    def _extract_traces(self, root_node: Any, source: bytes, mapped_ids: set[str]) -> None:
        """Recursively search strictly for AST nodes of type 'comment'."""
        def visit(node: Any) -> None:
            if node.type == "comment":
                text = source[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
                matches = re.findall(r"@trace\((?:N)?FR-\d+\)", text)
                for match in matches:
                    # extract inner requirement ID, e.g. "FR-123"
                    req_id = match.split("(")[1].split(")")[0]
                    mapped_ids.add(req_id)
            elif hasattr(node, "children"):
                for child in node.children:
                    visit(child)

        visit(root_node)
