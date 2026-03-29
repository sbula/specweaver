# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for TSStandardsAnalyzer."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from specweaver.standards.languages.typescript.analyzer import TSStandardsAnalyzer


@pytest.fixture()
def analyzer() -> TSStandardsAnalyzer:
    return TSStandardsAnalyzer()


class TestTSAnalyzerInterface:
    def test_language_name(self, analyzer: TSStandardsAnalyzer) -> None:
        assert analyzer.language_name() == "typescript"

    def test_file_extensions(self, analyzer: TSStandardsAnalyzer) -> None:
        assert analyzer.file_extensions() == {".ts", ".tsx", ".cts", ".mts"}

    def test_supported_categories(self, analyzer: TSStandardsAnalyzer) -> None:
        cats = analyzer.supported_categories()
        assert "naming" in cats
        assert "error_handling" in cats
        assert "tsdoc" in cats
        assert "test_patterns" in cats
        assert "import_patterns" in cats
        assert "async_patterns" in cats
        assert "typescript_types" in cats


class TestTSTypesExtraction:
    def test_detects_interface_dominance(
        self, analyzer: TSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "types.ts"
        f.write_text(
            textwrap.dedent("""\
            interface User { name: string; }
            interface DB { host: string; }
            type ID = string | number;
        """)
        )
        results = analyzer.extract_all([f], 180)
        types = next(r for r in results if r.category == "typescript_types")
        assert types.dominant.get("declaration") == "interface"
        assert types.sample_size == 3

    def test_detects_type_alias_dominance(
        self, analyzer: TSStandardsAnalyzer, tmp_path: Path
    ) -> None:
        f = tmp_path / "types.ts"
        f.write_text(
            textwrap.dedent("""\
            type User = { name: string; };
            type DB = { host: string; };
            interface ID { val: string; }
        """)
        )
        results = analyzer.extract_all([f], 180)
        types = next(r for r in results if r.category == "typescript_types")
        assert types.dominant.get("declaration") == "type_alias"
        assert types.sample_size == 3


class TestTSInheritance:
    """Verify that inherited JS extractors still run successfully on TS ASTs."""

    def test_js_extractor_naming(self, analyzer: TSStandardsAnalyzer, tmp_path: Path) -> None:
        f = tmp_path / "code.ts"
        f.write_text(
            textwrap.dedent("""\
            function getUser(): User {}
            class UserProfile implements User {}
        """)
        )
        results = analyzer.extract_all([f], 180)
        naming = next(r for r in results if r.category == "naming")
        assert naming.dominant.get("function_style") == "camelCase"
        assert naming.dominant.get("class_style") == "PascalCase"
        assert naming.sample_size == 2
