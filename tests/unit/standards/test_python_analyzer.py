# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for PythonStandardsAnalyzer — single-pass AST extraction."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from specweaver.standards.languages.python.analyzer import PythonStandardsAnalyzer

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def analyzer() -> PythonStandardsAnalyzer:
    return PythonStandardsAnalyzer()


# ---------------------------------------------------------------------------
# Analyzer interface
# ---------------------------------------------------------------------------


class TestAnalyzerInterface:
    """Verify the ABC contract is satisfied."""

    def test_language_name(self, analyzer: PythonStandardsAnalyzer) -> None:
        assert analyzer.language_name() == "python"

    def test_file_extensions(self, analyzer: PythonStandardsAnalyzer) -> None:
        assert analyzer.file_extensions() == {".py"}

    def test_supported_categories(
        self, analyzer: PythonStandardsAnalyzer,
    ) -> None:
        cats = analyzer.supported_categories()
        assert "naming" in cats
        assert "error_handling" in cats
        assert "type_hints" in cats
        assert "docstrings" in cats
        assert "import_patterns" in cats
        assert "test_patterns" in cats



# ---------------------------------------------------------------------------
# Naming conventions
# ---------------------------------------------------------------------------


class TestNamingExtraction:
    """Test extraction of naming convention patterns."""

    def test_detects_snake_case_functions(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Should detect snake_case as dominant function naming style."""
        f = tmp_path / "code.py"
        f.write_text(textwrap.dedent("""\
            def get_user_name():
                pass

            def set_user_age():
                pass

            def create_new_record():
                pass
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "naming"), None)

        assert result is not None, 'Category "naming" not found in results'
        assert result.dominant.get("function_style") == "snake_case"
        assert result.confidence > 0.5

    def test_detects_class_naming(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Should detect PascalCase as dominant class naming style."""
        f = tmp_path / "models.py"
        f.write_text(textwrap.dedent("""\
            class UserProfile:
                pass

            class PaymentGateway:
                pass

            class AbstractBaseModel:
                pass
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "naming"), None)

        assert result is not None, 'Category "naming" not found in results'
        assert result.dominant.get("class_style") == "PascalCase"

    def test_empty_files_return_zero_confidence(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Empty files should produce zero sample_size."""
        f = tmp_path / "empty.py"
        f.write_text("")
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "naming"), None)

        assert result is not None, 'Category "naming" not found in results'
        assert result.sample_size == 0

    def test_no_files_returns_zero_sample(
        self, analyzer: PythonStandardsAnalyzer,
    ) -> None:
        """No files → zero sample size."""
        results = analyzer.extract_all([], 180)

        result = next((r for r in results if r.category == "naming"), None)

        assert result is not None, 'Category "naming" not found in results'
        assert result.sample_size == 0
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Error handling patterns
# ---------------------------------------------------------------------------


class TestErrorHandlingExtraction:
    """Test extraction of error handling patterns."""

    def test_detects_specific_exceptions(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Should detect whether specific or bare exceptions are used."""
        f = tmp_path / "handlers.py"
        f.write_text(textwrap.dedent("""\
            def process():
                try:
                    do_work()
                except ValueError:
                    handle_error()
                except KeyError:
                    handle_key_error()
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "error_handling"), None)

        assert result is not None, 'Category "error_handling" not found in results'
        assert result.dominant.get("exception_style") == "specific"
        assert result.sample_size > 0

    def test_detects_bare_except(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Bare except blocks should be detected."""
        f = tmp_path / "sloppy.py"
        f.write_text(textwrap.dedent("""\
            def process():
                try:
                    do_work()
                except:
                    pass
                try:
                    do_more()
                except:
                    pass
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "error_handling"), None)

        assert result is not None, 'Category "error_handling" not found in results'
        assert result.dominant.get("exception_style") == "bare"


# ---------------------------------------------------------------------------
# Type hints
# ---------------------------------------------------------------------------


class TestTypeHintsExtraction:
    """Test extraction of type hint usage patterns."""

    def test_detects_type_hints(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Should detect functions using type annotations."""
        f = tmp_path / "typed.py"
        f.write_text(textwrap.dedent("""\
            def greet(name: str) -> str:
                return f"Hello, {name}"

            def add(a: int, b: int) -> int:
                return a + b

            def noop() -> None:
                pass
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "type_hints"), None)

        assert result is not None, 'Category "type_hints" not found in results'
        assert result.dominant.get("usage") == "yes"
        assert result.sample_size >= 3

    def test_detects_no_type_hints(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Untyped code should be detected."""
        f = tmp_path / "untyped.py"
        f.write_text(textwrap.dedent("""\
            def greet(name):
                return f"Hello, {name}"

            def add(a, b):
                return a + b
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "type_hints"), None)

        assert result is not None, 'Category "type_hints" not found in results'
        assert result.dominant.get("usage") == "no"


# ---------------------------------------------------------------------------
# Docstrings
# ---------------------------------------------------------------------------


class TestDocstringsExtraction:
    """Test extraction of docstring patterns."""

    def test_detects_docstrings_present(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Functions with docstrings should be detected."""
        f = tmp_path / "documented.py"
        f.write_text(textwrap.dedent('''\
            def greet(name):
                """Greet a user by name."""
                return f"Hello, {name}"

            def add(a, b):
                """Add two numbers."""
                return a + b
        '''))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "docstrings"), None)

        assert result is not None, 'Category "docstrings" not found in results'
        assert result.dominant.get("coverage") in ("high", "full")

    def test_detects_no_docstrings(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Functions without docstrings should be detected."""
        f = tmp_path / "undocumented.py"
        f.write_text(textwrap.dedent("""\
            def greet(name):
                return f"Hello, {name}"

            def add(a, b):
                return a + b
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "docstrings"), None)

        assert result is not None, 'Category "docstrings" not found in results'
        assert result.dominant.get("coverage") in ("none", "low")


# ---------------------------------------------------------------------------
# Import patterns
# ---------------------------------------------------------------------------


class TestImportPatternsExtraction:
    """Test extraction of import style patterns."""

    def test_detects_absolute_imports(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Standard absolute imports should be detected."""
        f = tmp_path / "imports.py"
        f.write_text(textwrap.dedent("""\
            import os
            import sys
            from pathlib import Path
            from collections import defaultdict
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "import_patterns"), None)

        assert result is not None, 'Category "import_patterns" not found in results'
        assert result.dominant.get("style") == "absolute"
        assert result.sample_size >= 4


# ---------------------------------------------------------------------------
# Test patterns
# ---------------------------------------------------------------------------


class TestTestPatternsExtraction:
    """Test extraction of test patterns (pytest vs unittest)."""

    def test_detects_pytest_style(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Pytest-style tests should be detected."""
        f = tmp_path / "test_foo.py"
        f.write_text(textwrap.dedent("""\
            import pytest

            def test_addition():
                assert 1 + 1 == 2

            def test_subtraction():
                assert 2 - 1 == 1

            class TestMath:
                def test_multiply(self):
                    assert 2 * 3 == 6
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "test_patterns"), None)

        assert result is not None, 'Category "test_patterns" not found in results'
        assert result.dominant.get("framework") == "pytest"

    def test_no_test_files_returns_zero(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Non-test files should produce zero sample for test_patterns."""
        f = tmp_path / "app.py"
        f.write_text("def main(): pass")
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "test_patterns"), None)

        assert result is not None, 'Category "test_patterns" not found in results'
        assert result.sample_size == 0

    def test_suffix_style_test_file_detected(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Files named *_test.py (suffix style) are included."""
        f = tmp_path / "math_test.py"
        f.write_text(textwrap.dedent("""\
            import pytest

            def test_add():
                assert 1 + 1 == 2
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "test_patterns"), None)

        assert result is not None, 'Category "test_patterns" not found in results'
        assert result.sample_size > 0
        assert result.dominant.get("framework") == "pytest"

    def test_detects_unittest_framework(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """unittest-style tests should be detected."""
        f = tmp_path / "test_old.py"
        f.write_text(textwrap.dedent("""\
            import unittest

            class TestOld(unittest.TestCase):
                def test_one(self):
                    self.assertEqual(1, 1)
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "test_patterns"), None)

        assert result is not None, 'Category "test_patterns" not found in results'
        assert result.dominant.get("framework") == "unittest"


# ---------------------------------------------------------------------------
# _parse_file / _file_weight / _compute_confidence — edge cases
# ---------------------------------------------------------------------------


class TestHelperEdgeCases:
    """Test private helper edge cases."""

    def test_parse_file_with_syntax_error(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Files with SyntaxError are skipped (return None)."""
        f = tmp_path / "broken.py"
        f.write_text("def oops(\n")
        result = analyzer._parse_file(f)
        assert result is None

    def test_parse_file_with_encoding_errors(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Files with encoding errors are handled via errors='replace'."""
        f = tmp_path / "binary_ish.py"
        f.write_bytes(b"x = '\xff\xfe'\n")
        # Should not raise — errors="replace" handles it
        result = analyzer._parse_file(f)
        assert result is not None

    def test_file_weight_oserror_uses_current_time(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path, monkeypatch,
    ) -> None:
        """If stat() fails, _file_weight should use time.time()."""

        f = tmp_path / "gone.py"
        f.write_text("pass")
        # Remove the file so stat() fails
        f.unlink()

        # _file_weight catches OSError and uses time.time()
        weight = analyzer._file_weight(f, 180)
        # Weight should be ≈ 1.0 because it uses current time
        assert weight > 0.9

    def test_compute_confidence_empty_counter(
        self, analyzer: PythonStandardsAnalyzer,
    ) -> None:
        """Empty Counter → 0.0."""
        from collections import Counter

        assert analyzer._compute_confidence(Counter()) == 0.0

    def test_compute_confidence_unanimous(
        self, analyzer: PythonStandardsAnalyzer,
    ) -> None:
        """All votes for one style → confidence 1.0."""
        from collections import Counter

        c = Counter({"snake_case": 10.0})
        assert analyzer._compute_confidence(c) == 1.0

    def test_compute_confidence_mixed(
        self, analyzer: PythonStandardsAnalyzer,
    ) -> None:
        """Mixed votes → confidence < 1.0."""
        from collections import Counter

        c = Counter({"snake_case": 7.0, "camelCase": 3.0})
        conf = analyzer._compute_confidence(c)
        assert conf == pytest.approx(0.7, abs=0.01)


# ---------------------------------------------------------------------------
# _classify_name — all branches
# ---------------------------------------------------------------------------


class TestClassifyName:
    """Test _classify_name for every return branch."""

    def test_dunder_name(self) -> None:
        from specweaver.standards.languages.python.analyzer import _classify_name

        assert _classify_name("__init__") == "dunder"
        assert _classify_name("__str__") == "dunder"

    def test_pascal_case(self) -> None:
        from specweaver.standards.languages.python.analyzer import _classify_name

        assert _classify_name("MyClass") == "PascalCase"
        assert _classify_name("AbstractBase") == "PascalCase"

    def test_snake_case(self) -> None:
        from specweaver.standards.languages.python.analyzer import _classify_name

        assert _classify_name("get_user") == "snake_case"
        assert _classify_name("process_data_v2") == "snake_case"

    def test_camel_case(self) -> None:
        from specweaver.standards.languages.python.analyzer import _classify_name

        assert _classify_name("getUserName") == "camelCase"
        assert _classify_name("processData") == "camelCase"

    def test_upper_snake(self) -> None:
        from specweaver.standards.languages.python.analyzer import _classify_name

        assert _classify_name("MAX_RETRIES") == "UPPER_SNAKE"
        assert _classify_name("DB_HOST") == "UPPER_SNAKE"

    def test_other_fallback(self) -> None:
        from specweaver.standards.languages.python.analyzer import _classify_name

        assert _classify_name("_private_func") == "other"
        assert _classify_name("__double_private") == "other"


# ---------------------------------------------------------------------------
# Naming — more edge cases
# ---------------------------------------------------------------------------


class TestNamingEdgeCases:
    """Edge cases for _extract_naming."""

    def test_private_functions_excluded(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Functions starting with '_' are excluded from naming analysis."""
        f = tmp_path / "private.py"
        f.write_text(textwrap.dedent("""\
            def _internal():
                pass

            def __double():
                pass
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "naming"), None)

        assert result is not None, 'Category "naming" not found in results'
        # No public functions → empty dominant, 0 sample
        assert result.sample_size == 0
        assert result.dominant == {}

    def test_mixed_naming_lowers_confidence(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Mixed snake_case and camelCase should give confidence < 1.0."""
        f = tmp_path / "mixed.py"
        f.write_text(textwrap.dedent("""\
            def get_data():
                pass

            def processResult():
                pass

            def fetch_items():
                pass
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "naming"), None)

        assert result is not None, 'Category "naming" not found in results'
        # snake_case is dominant (2 vs 1 camelCase)
        assert result.dominant.get("function_style") == "snake_case"
        assert result.confidence < 1.0

    def test_no_classes_no_functions_empty_dominant(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """File with only module-level constants → empty dominant dict."""
        f = tmp_path / "constants.py"
        f.write_text("MAX_SIZE = 100\nDEFAULT_NAME = 'test'\n")
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "naming"), None)

        assert result is not None, 'Category "naming" not found in results'
        assert result.dominant == {}
        assert result.sample_size == 0


# ---------------------------------------------------------------------------
# Docstrings — boundary values
# ---------------------------------------------------------------------------


class TestDocstringBoundaries:
    """Test docstring coverage boundary conditions."""

    def test_full_coverage_boundary(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Exactly 90% documented → 'full'."""
        f = tmp_path / "mostly_doc.py"
        # 9 documented + 1 undocumented = 90%
        lines = []
        for i in range(9):
            lines.append(f'def func_{i}():\n    """Doc."""\n    pass\n')
        lines.append("def no_doc():\n    pass\n")
        f.write_text("\n".join(lines))

        results = analyzer.extract_all([f], 180)


        result = next((r for r in results if r.category == "docstrings"), None)


        assert result is not None, 'Category "docstrings" not found in results'
        assert result.dominant.get("coverage") == "full"

    def test_no_functions_at_all(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """File with no functions → sample_size=0, confidence=0.0."""
        f = tmp_path / "no_funcs.py"
        f.write_text("X = 42\n")
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "docstrings"), None)

        assert result is not None, 'Category "docstrings" not found in results'
        assert result.sample_size == 0
        assert result.confidence == 0.0
        assert result.dominant == {}


# ---------------------------------------------------------------------------
# Imports — relative imports
# ---------------------------------------------------------------------------


class TestImportEdgeCases:
    """Edge cases for import pattern extraction."""

    def test_detects_relative_imports(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Relative imports should be detected."""
        f = tmp_path / "rel.py"
        f.write_text(textwrap.dedent("""\
            from . import sibling
            from ..parent import base
            from .utils import helper
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "import_patterns"), None)

        assert result is not None, 'Category "import_patterns" not found in results'
        assert result.dominant.get("style") == "relative"
        assert result.sample_size == 3

    def test_mixed_imports_absolute_dominant(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Mixed absolute + relative with absolute majority → 'absolute'."""
        f = tmp_path / "mixed_imports.py"
        f.write_text(textwrap.dedent("""\
            import os
            import sys
            from pathlib import Path
            from . import local
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "import_patterns"), None)

        assert result is not None, 'Category "import_patterns" not found in results'
        assert result.dominant.get("style") == "absolute"
        assert result.confidence > 0.5

    def test_no_imports_returns_empty(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """File with no imports → empty dominant."""
        f = tmp_path / "no_imports.py"
        f.write_text("x = 1\n")
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "import_patterns"), None)

        assert result is not None, 'Category "import_patterns" not found in results'
        assert result.sample_size == 0
        assert result.dominant == {}


# ---------------------------------------------------------------------------
# Error handling — edge cases
# ---------------------------------------------------------------------------


class TestErrorHandlingEdgeCases:
    """Edge cases for error_handling extraction."""

    def test_no_try_except_returns_empty(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """File with no try/except → empty dominan, 0 samples."""
        f = tmp_path / "clean.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "error_handling"), None)

        assert result is not None, 'Category "error_handling" not found in results'
        assert result.sample_size == 0
        assert result.dominant == {}
        assert result.confidence == 0.0

    def test_mixed_bare_and_specific(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """Mixed bare and specific except → 'specific' wins if majority."""
        f = tmp_path / "mixed_err.py"
        f.write_text(textwrap.dedent("""\
            def a():
                try:
                    pass
                except ValueError:
                    pass
                except KeyError:
                    pass
                except:
                    pass
        """))
        results = analyzer.extract_all([f], 180)

        result = next((r for r in results if r.category == "error_handling"), None)

        assert result is not None, 'Category "error_handling" not found in results'
        assert result.dominant.get("exception_style") == "specific"
        assert result.sample_size == 3


# ---------------------------------------------------------------------------
# Extract with SyntaxError file in the mix
# ---------------------------------------------------------------------------


class TestExtractWithBrokenFiles:
    """Extraction should gracefully skip unparseable files."""

    def test_naming_skips_syntax_error_file(
        self, analyzer: PythonStandardsAnalyzer, tmp_path: Path,
    ) -> None:
        """A SyntaxError file is skipped, valid files still analyzed."""
        good = tmp_path / "good.py"
        good.write_text("def get_user():\n    pass\n")
        bad = tmp_path / "bad.py"
        bad.write_text("def oops(\n")

        results = analyzer.extract_all([good, bad], 180)


        result = next((r for r in results if r.category == "naming"), None)


        assert result is not None, 'Category "naming" not found in results'
        assert result.sample_size == 1
        assert result.dominant.get("function_style") == "snake_case"

