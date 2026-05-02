# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for TreeSitterAnalyzer base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.standards.analyzer import CategoryResult
from specweaver.assurance.standards.tree_sitter_base import TreeSitterAnalyzer
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import tree_sitter

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface


class DummyJSAnalyzer(TreeSitterAnalyzer):
    def language_name(self) -> str:
        return "javascript"

    def file_extensions(self) -> set[str]:
        return {".js", ".jsx"}

    def supported_categories(self) -> list[str]:
        return ["dummy_cat"]

    def get_code_structure(self) -> CodeStructureInterface:
        return TypeScriptCodeStructure()

    def get_extractors(self) -> list[Callable]:
        return [self._extract_dummy]

    def _extract_dummy(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        sample_size = 0
        for _path, _w, tree in parsed_files:
            if tree.root_node.type == "program":
                sample_size += 1

        return CategoryResult(
            category="dummy_cat",
            dominant={"status": "ok"},
            confidence=1.0,
            sample_size=sample_size,
        )


@pytest.fixture()
def analyzer() -> DummyJSAnalyzer:
    return DummyJSAnalyzer()


class TestTreeSitterAnalyzer:
    """Verify the common tree-sitter AST extraction pipeline."""

    def test_parses_files_and_calls_extractors(
        self, analyzer: DummyJSAnalyzer, tmp_path: Path
    ) -> None:
        """Should parse multiple files in one pass and feed to extractors."""
        f1 = tmp_path / "valid.js"
        f1.write_text("const x = 1;")
        f2 = tmp_path / "also_valid.js"
        f2.write_text("function add(a, b) { return a + b; }")

        results = analyzer.extract_all([f1, f2], 180)
        assert len(results) == 1

        res = results[0]
        assert res.category == "dummy_cat"
        assert res.sample_size == 2
        assert res.dominant == {"status": "ok"}
        assert res.confidence == 1.0

    def test_skips_files_with_read_errors(self, analyzer: DummyJSAnalyzer, tmp_path: Path) -> None:
        """Files that cannot be read (e.g. absent) should be skipped gracefully."""
        f = tmp_path / "missing.js"
        # We do not write the file, so path.read_bytes() will fail

        results = analyzer.extract_all([f], 180)
        assert len(results) == 1
        assert results[0].sample_size == 0

    def test_extractor_failure_is_caught_safely(self, tmp_path: Path) -> None:
        """If one extractor raises an exception, the pipeline should not completely crash."""

        class BuggyAnalyzer(DummyJSAnalyzer):
            def _extract_crash(self, parsed_files: list) -> CategoryResult:
                raise ValueError("Oops!")

            def get_extractors(self) -> list[Callable]:
                # The first will crash, the second will succeed
                return [self._extract_crash, self._extract_dummy]

        buggy = BuggyAnalyzer()
        f = tmp_path / "test.js"
        f.write_text("console.log();")

        # The crash in _extract_crash should be caught and logger.warning'd,
        # allowing _extract_dummy to still return its result.
        results = buggy.extract_all([f], 180)

        assert len(results) == 1
        assert results[0].category == "dummy_cat"
        assert results[0].sample_size == 1
