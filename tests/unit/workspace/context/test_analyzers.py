# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for language analyzers — TDD for context.yaml auto-inference."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.workspace.context.analyzers import (
    AnalyzerFactory,
    PythonAnalyzer,
)

if TYPE_CHECKING:
    from pathlib import Path

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
        "from specweaver.core.config.settings import load_settings\n"
        "from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter\n"
        "import requests\n"
        "\n"
        "class PriceFeedClient:\n"
        '    """Connects to Binance and streams price data."""\n'
        "    pass\n"
    )
    (pkg / "models.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "class PriceUpdate:\n"
        '    """A single price update event."""\n'
        "    pass\n"
        "\n"
        "class _InternalHelper:\n"
        "    pass\n"
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
        '"""Public API layer."""\n\n__all__ = ["Router", "Endpoint"]\n'
    )
    (pkg / "router.py").write_text("class Router:\n    pass\nclass _RouteTable:\n    pass\n")
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
        assert "specweaver.core.config.settings" in imports
        assert "specweaver.infrastructure.llm.adapters.gemini" in imports
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
            "from __future__ import annotations\n"
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )
        archetype = PythonAnalyzer().infer_archetype(pkg)
        assert archetype == "pure-logic"

    def test_empty_dir_defaults_pure_logic(self, empty_dir: Path) -> None:
        assert PythonAnalyzer().infer_archetype(empty_dir) == "pure-logic"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestPythonAnalyzerEdgeCases:
    """Edge cases and resilience tests."""

    def test_syntax_error_in_file_skipped_for_imports(self, tmp_path: Path) -> None:
        """Syntax errors in a .py file should be skipped, not crash."""
        pkg = tmp_path / "broken"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Valid module."""\n')
        (pkg / "bad.py").write_text("def broken(:\n")  # invalid syntax
        (pkg / "good.py").write_text("import os\n")
        imports = PythonAnalyzer().extract_imports(pkg)
        assert "os" in imports  # good.py was still parsed

    def test_syntax_error_in_file_skipped_for_symbols(self, tmp_path: Path) -> None:
        pkg = tmp_path / "broken2"
        pkg.mkdir()
        (pkg / "bad.py").write_text("class Oops(:\n")
        (pkg / "good.py").write_text("class Valid:\n    pass\n")
        symbols = PythonAnalyzer().extract_public_symbols(pkg)
        assert "Valid" in symbols

    def test_pycache_only_not_detected(self, tmp_path: Path) -> None:
        """__pycache__ contains .py files but should not count."""
        pkg = tmp_path / "__pycache__"
        pkg.mkdir()
        (pkg / "mod.cpython-313.pyc").write_bytes(b"")
        # __pycache__ has no .py files (only .pyc), so shouldn't detect
        assert PythonAnalyzer().detect(pkg) is False

    def test_multiline_docstring_takes_first_line(self, tmp_path: Path) -> None:
        pkg = tmp_path / "multi"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""First line of the docstring.\n\nThis is extra detail.\nAnd more.\n"""\n'
        )
        purpose = PythonAnalyzer().extract_purpose(pkg)
        assert purpose == "First line of the docstring."

    def test_extracts_public_functions_not_just_classes(self, tmp_path: Path) -> None:
        pkg = tmp_path / "funcs"
        pkg.mkdir()
        (pkg / "utils.py").write_text(
            "def public_func():\n    pass\n\n"
            "async def async_public():\n    pass\n\n"
            "def _private_func():\n    pass\n"
        )
        symbols = PythonAnalyzer().extract_public_symbols(pkg)
        assert "public_func" in symbols
        assert "async_public" in symbols
        assert "_private_func" not in symbols

    def test_specweaver_imports_are_internal(self, tmp_path: Path) -> None:
        """Imports from specweaver.* should not trigger 'adapter' archetype."""
        pkg = tmp_path / "internal"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Internal module."""\n')
        (pkg / "code.py").write_text(
            "from specweaver.assurance.validation.models import Rule\n"
            "from specweaver.core.config.settings import load_settings\n"
        )
        assert PythonAnalyzer().infer_archetype(pkg) == "pure-logic"


# ---------------------------------------------------------------------------
# Polyglot Proxy Tests
# ---------------------------------------------------------------------------


class TestPolyglotLanguageAnalyzer:
    """Verify AnalyzerFactory dynamically maps to non-Python analyzers."""

    def test_gets_python_parser_by_default(self, tmp_path: Path) -> None:
        (tmp_path / "hello.py").touch()
        from specweaver.workspace.context.analyzers import AnalyzerFactory, PythonAnalyzer

        analyzer = AnalyzerFactory.for_directory(tmp_path)
        assert isinstance(analyzer, PythonAnalyzer)

    def test_gets_java_parser(self, tmp_path: Path) -> None:
        (tmp_path / "App.java").touch()
        from specweaver.workspace.context.analyzers import AnalyzerFactory, JavaAnalyzer

        analyzer = AnalyzerFactory.for_directory(tmp_path)
        assert isinstance(analyzer, JavaAnalyzer)

    def test_gets_kotlin_parser(self, tmp_path: Path) -> None:
        (tmp_path / "App.kt").touch()
        from specweaver.workspace.context.analyzers import AnalyzerFactory, KotlinAnalyzer

        analyzer = AnalyzerFactory.for_directory(tmp_path)
        assert isinstance(analyzer, KotlinAnalyzer)

    def test_gets_rust_parser(self, tmp_path: Path) -> None:
        (tmp_path / "main.rs").touch()
        from specweaver.workspace.context.analyzers import AnalyzerFactory, RustAnalyzer

        analyzer = AnalyzerFactory.for_directory(tmp_path)
        assert isinstance(analyzer, RustAnalyzer)

    def test_gets_typescript_parser(self, tmp_path: Path) -> None:
        (tmp_path / "app.ts").touch()
        from specweaver.workspace.context.analyzers import AnalyzerFactory, TypeScriptAnalyzer

        analyzer = AnalyzerFactory.for_directory(tmp_path)
        assert isinstance(analyzer, TypeScriptAnalyzer)

    def test_gets_none_for_unknown(self, tmp_path: Path) -> None:
        (tmp_path / "file.unknown").touch()
        from specweaver.workspace.context.analyzers import AnalyzerFactory

        analyzer = AnalyzerFactory.for_directory(tmp_path)
        assert analyzer is None

    def test_get_all_analyzers_returns_polyglot_union(self) -> None:
        """AnalyzerFactory exposes a union of all mapped parsers globally."""
        from specweaver.workspace.context.analyzers import AnalyzerFactory

        analyzers = AnalyzerFactory.get_all_analyzers()
        assert len(analyzers) == 5
        types = [type(a).__name__ for a in analyzers]
        assert "PythonAnalyzer" in types
        assert "JavaAnalyzer" in types
        assert "KotlinAnalyzer" in types
        assert "RustAnalyzer" in types
        assert "TypeScriptAnalyzer" in types

    def test_language_analyzer_delegates_binary_ignores_to_parser(self) -> None:
        """TreeSitterAnalyzerBase correctly passes binary ignore requests down to parser."""
        from specweaver.workspace.context.analyzers import PythonAnalyzer
        analyzer = PythonAnalyzer()
        patterns = analyzer.get_binary_ignore_patterns()
        assert "*.pyc" in patterns

    def test_language_analyzer_delegates_directory_ignores_to_parser(self) -> None:
        """TreeSitterAnalyzerBase correctly passes directory ignore requests down to parser."""
        from specweaver.workspace.context.analyzers import PythonAnalyzer
        analyzer = PythonAnalyzer()
        dirs = analyzer.get_default_directory_ignores()
        # Python parser adds .venv, env, .pytest_cache
        assert ".venv/" in dirs
        assert ".pytest_cache/" in dirs
