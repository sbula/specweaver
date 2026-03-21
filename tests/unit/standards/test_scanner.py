# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for StandardsScanner."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from specweaver.standards.analyzer import CategoryResult, StandardsAnalyzer
from specweaver.standards.scanner import StandardsScanner


class DummyPythonAnalyzer(StandardsAnalyzer):
    def language_name(self) -> str:
        return "python"

    def file_extensions(self) -> set[str]:
        return {".py"}

    def supported_categories(self) -> list[str]:
        return ["dummy_py"]

    def extract_all(
        self, files: list[Path], half_life_days: float
    ) -> list[CategoryResult]:
        return [
            CategoryResult(
                category="dummy_py",
                dominant={"detected": True},
                confidence=1.0,
                sample_size=len(files),
            )
        ]


class DummyJSAnalyzer(StandardsAnalyzer):
    def language_name(self) -> str:
        return "javascript"

    def file_extensions(self) -> set[str]:
        return {".js", ".jsx"}

    def supported_categories(self) -> list[str]:
        return ["dummy_js"]

    def extract_all(
        self, files: list[Path], half_life_days: float
    ) -> list[CategoryResult]:
        return [
            CategoryResult(
                category="dummy_js",
                dominant={"detected": True},
                confidence=1.0,
                sample_size=len(files),
            )
        ]


@pytest.fixture()
def scanner() -> StandardsScanner:
    return StandardsScanner(analyzers=[DummyPythonAnalyzer(), DummyJSAnalyzer()])


class TestStandardsScanner:
    def test_routes_files_to_correct_analyzers(
        self, scanner: StandardsScanner, tmp_path: Path
    ) -> None:
        """Scanner should group files by extension and trigger specific extract_all methods."""
        py1 = tmp_path / "main.py"
        py2 = tmp_path / "util.py"
        js1 = tmp_path / "app.js"
        txt1 = tmp_path / "readme.txt"

        for p in [py1, py2, js1, txt1]:
            p.touch()

        # The txt file should be ignored.
        results = scanner.scan([py1, py2, js1, txt1], 180.0)

        assert len(results) == 2

        py_res = next(r for r in results if r.category == "dummy_py")
        assert py_res.sample_size == 2

        js_res = next(r for r in results if r.category == "dummy_js")
        assert js_res.sample_size == 1

    def test_skips_unmapped_files_silently(
        self, scanner: StandardsScanner, tmp_path: Path
    ) -> None:
        txt = tmp_path / "note.md"
        txt.touch()

        results = scanner.scan([txt], 180.0)
        assert len(results) == 0

    def test_default_initialization_contains_all_languages(self) -> None:
        # Without providing analyzers, it should load Python, JS, TS
        default_scanner = StandardsScanner()
        exts = set()
        for a in default_scanner.analyzers:
            exts.update(a.file_extensions())

        assert ".py" in exts
        assert ".js" in exts
        assert ".ts" in exts
