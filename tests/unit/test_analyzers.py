# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for language analyzers — TDD for context.yaml auto-inference."""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.context.analyzers import (
    AnalyzerFactory,
    LanguageAnalyzer,
    PythonAnalyzer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def py_dir(tmp_path: Path) -> Path:
    """Create a directory with Python source files."""
    pkg = tmp_path / "my_module"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Price feed adapter for Binance WebSocket."""\n')
    (pkg / "client.py").write_text(
        'from specweaver.config.settings import load_settings\n'
        'from specweaver.llm.gemini_adapter import GeminiAdapter\n'
        'import requests\n'
        '\n'
        'class PriceFeedClient:\n'
        '    """Connects to Binance and streams price data."""\n'
        '    pass\n'
    )
    (pkg / "models.py").write_text(
        'from __future__ import annotations\n'
        '\n'
        'class PriceUpdate:\n'
        '    """A single price update event."""\n'
        '    pass\n'
        '\n'
        'class _InternalHelper:\n'
        '    pass\n'
    )
    return pkg


@pytest.fixture()
def py_dir_no_init(tmp_path: Path) -> Path:
    """Create a Python directory without __init__.py."""
    pkg = tmp_path / "scripts"
    pkg.mkdir()
    (pkg / "run.py").write_text('print("hello")\n')
    return pkg


@pytest.fixture()
def empty_dir(tmp_path: Path) -> Path:
    """Create an empty directory."""
    d = tmp_path / "empty"
    d.mkdir()
    return d


@pytest.fixture()
def non_python_dir(tmp_path: Path) -> Path:
    """Create a directory with only non-Python files."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "README.md").write_text("# Hello\n")
    (d / "notes.txt").write_text("some notes\n")
    return d


@pytest.fixture()
def py_dir_with_all(tmp_path: Path) -> Path:
    """Python dir with __all__ defined in __init__.py."""
    pkg = tmp_path / "api"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Public API layer."""\n'
        '\n'
        '__all__ = ["Router", "Endpoint"]\n'
    )
    (pkg / "router.py").write_text(
        'class Router:\n    pass\n'
        'class _RouteTable:\n    pass\n'
    )
    return pkg


# ---------------------------------------------------------------------------
# AnalyzerFactory tests
# ---------------------------------------------------------------------------


class TestAnalyzerFactory:
    """Test language detection and analyzer creation."""

    def test_python_detected(self, py_dir: Path) -> None:
        analyzer = AnalyzerFactory.for_directory(py_dir)
        assert analyzer is not None
        assert isinstance(analyzer, PythonAnalyzer)

    def test_python_detected_no_init(self, py_dir_no_init: Path) -> None:
        analyzer = AnalyzerFactory.for_directory(py_dir_no_init)
        assert analyzer is not None
        assert isinstance(analyzer, PythonAnalyzer)

    def test_empty_dir_returns_none(self, empty_dir: Path) -> None:
        analyzer = AnalyzerFactory.for_directory(empty_dir)
        assert analyzer is None

    def test_non_python_returns_none(self, non_python_dir: Path) -> None:
        analyzer = AnalyzerFactory.for_directory(non_python_dir)
        assert analyzer is None


# ---------------------------------------------------------------------------
# PythonAnalyzer tests
# ---------------------------------------------------------------------------


class TestPythonAnalyzerDetect:
    """Test Python language detection."""

    def test_detects_py_files(self, py_dir: Path) -> None:
        assert PythonAnalyzer().detect(py_dir) is True

    def test_rejects_empty(self, empty_dir: Path) -> None:
        assert PythonAnalyzer().detect(empty_dir) is False

    def test_rejects_no_py(self, non_python_dir: Path) -> None:
        assert PythonAnalyzer().detect(non_python_dir) is False


class TestPythonAnalyzerPurpose:
    """Test purpose extraction from __init__.py docstring."""

    def test_extracts_docstring(self, py_dir: Path) -> None:
        purpose = PythonAnalyzer().extract_purpose(py_dir)
        assert purpose == "Price feed adapter for Binance WebSocket."

    def test_no_init_returns_none(self, py_dir_no_init: Path) -> None:
        purpose = PythonAnalyzer().extract_purpose(py_dir_no_init)
        assert purpose is None

    def test_empty_init(self, tmp_path: Path) -> None:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        assert PythonAnalyzer().extract_purpose(pkg) is None


class TestPythonAnalyzerImports:
    """Test import extraction from all .py files in a directory."""

    def test_extracts_imports(self, py_dir: Path) -> None:
        imports = PythonAnalyzer().extract_imports(py_dir)
        assert "specweaver.config.settings" in imports
        assert "specweaver.llm.gemini_adapter" in imports
        assert "requests" in imports

    def test_no_duplicates(self, py_dir: Path) -> None:
        imports = PythonAnalyzer().extract_imports(py_dir)
        assert len(imports) == len(set(imports))

    def test_empty_dir(self, empty_dir: Path) -> None:
        assert PythonAnalyzer().extract_imports(empty_dir) == []


class TestPythonAnalyzerPublicSymbols:
    """Test public symbol extraction."""

    def test_extracts_public_classes(self, py_dir: Path) -> None:
        symbols = PythonAnalyzer().extract_public_symbols(py_dir)
        assert "PriceFeedClient" in symbols
        assert "PriceUpdate" in symbols

    def test_excludes_private(self, py_dir: Path) -> None:
        symbols = PythonAnalyzer().extract_public_symbols(py_dir)
        assert "_InternalHelper" not in symbols

    def test_prefers_all_when_present(self, py_dir_with_all: Path) -> None:
        symbols = PythonAnalyzer().extract_public_symbols(py_dir_with_all)
        assert "Router" in symbols
        assert "Endpoint" in symbols
        # _RouteTable should NOT be in the list because __all__ is defined
        assert "_RouteTable" not in symbols

    def test_empty_dir(self, empty_dir: Path) -> None:
        assert PythonAnalyzer().extract_public_symbols(empty_dir) == []


class TestPythonAnalyzerArchetype:
    """Test archetype inference heuristic."""

    def test_adapter_when_external_imports(self, py_dir: Path) -> None:
        # py_dir imports 'requests' (external) → adapter
        archetype = PythonAnalyzer().infer_archetype(py_dir)
        assert archetype == "adapter"

    def test_pure_logic_when_internal_only(self, tmp_path: Path) -> None:
        pkg = tmp_path / "logic"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pure business logic."""\n')
        (pkg / "calc.py").write_text(
            'from __future__ import annotations\n'
            'def add(a: int, b: int) -> int:\n'
            '    return a + b\n'
        )
        archetype = PythonAnalyzer().infer_archetype(pkg)
        assert archetype == "pure-logic"

    def test_empty_dir_defaults_pure_logic(self, empty_dir: Path) -> None:
        assert PythonAnalyzer().infer_archetype(empty_dir) == "pure-logic"
