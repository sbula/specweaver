# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for C01 SyntaxValidRule, C02 TestsExistRule, C03 TestsPassRule."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c01_syntax_valid import SyntaxValidRule
from specweaver.assurance.validation.rules.code.c02_tests_exist import TestsExistRule
from specweaver.assurance.validation.rules.code.c03_tests_pass import TestsPassRule

# ═══════════════════════════════════════════════════════════════════════════
# C01: SyntaxValidRule
# ═══════════════════════════════════════════════════════════════════════════


class TestSyntaxValidRule:
    def test_rule_id(self) -> None:
        assert SyntaxValidRule().rule_id == "C01"

    def test_rule_name(self) -> None:
        assert SyntaxValidRule().name == "Syntax Valid"

    def test_valid_code_passes(self) -> None:
        rule = SyntaxValidRule()
        code = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
        result = rule.check(code)
        assert result.status == Status.PASS

    def test_syntax_error_fails(self) -> None:
        rule = SyntaxValidRule()
        code = "def broken(:\n    pass\n"
        result = rule.check(code)
        assert result.status == Status.FAIL
        assert len(result.findings) == 1
        assert result.findings[0].line is not None

    def test_empty_code_passes(self) -> None:
        rule = SyntaxValidRule()
        result = rule.check("")
        assert result.status == Status.PASS

    def test_whitespace_only_passes(self) -> None:
        rule = SyntaxValidRule()
        result = rule.check("   \n\n   \n")
        assert result.status == Status.PASS

    def test_complex_valid_code(self) -> None:
        rule = SyntaxValidRule()
        code = (
            "import os\n"
            "from pathlib import Path\n\n"
            "class Foo:\n"
            "    def __init__(self, x: int) -> None:\n"
            "        self.x = x\n\n"
            "    async def bar(self) -> str:\n"
            "        return 'baz'\n"
        )
        result = rule.check(code)
        assert result.status == Status.PASS

    def test_error_message_includes_line_info(self) -> None:
        rule = SyntaxValidRule()
        code = "x = 1\ny = 2\nz = (\n"  # unclosed paren
        result = rule.check(code)
        assert result.status == Status.FAIL
        assert "SyntaxError" in result.findings[0].message

    def test_indentation_error_caught(self) -> None:
        rule = SyntaxValidRule()
        code = "def f():\nreturn 1\n"  # missing indent
        result = rule.check(code)
        assert result.status == Status.FAIL


# ═══════════════════════════════════════════════════════════════════════════
# C02: TestsExistRule
# ═══════════════════════════════════════════════════════════════════════════


class TestTestsExistRule:
    def test_rule_id(self) -> None:
        assert TestsExistRule().rule_id == "C02"

    def test_rule_name(self) -> None:
        assert TestsExistRule().name == "Tests Exist"

    def test_no_path_skips(self) -> None:
        rule = TestsExistRule()
        result = rule.check("code here", spec_path=None)
        assert result.status == Status.SKIP

    def test_finds_test_file(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "calculator.py"
        src.parent.mkdir()
        src.write_text("def add(a, b): return a + b\n")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_calculator.py"
        test_file.write_text("def test_add(): pass\n")

        rule = TestsExistRule()
        result = rule.check("code", spec_path=src)
        assert result.status == Status.PASS

    def test_no_test_file_fails(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "calculator.py"
        src.parent.mkdir()
        src.write_text("code")

        (tmp_path / "tests").mkdir()

        rule = TestsExistRule()
        result = rule.check("code", spec_path=src)
        assert result.status == Status.FAIL

    def test_nested_test_directory(self, tmp_path: Path) -> None:
        """Test file in nested tests/unit/ subdirectory."""
        src = tmp_path / "src" / "mymod.py"
        src.parent.mkdir()
        src.write_text("code")

        test_file = tmp_path / "tests" / "unit" / "test_mymod.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_it(): pass\n")

        rule = TestsExistRule()
        result = rule.check("code", spec_path=src)
        assert result.status == Status.PASS

    def test_no_tests_directory_fails(self, tmp_path: Path) -> None:
        """No tests/ directory at all → should fail."""
        src = tmp_path / "file.py"
        src.write_text("code")

        rule = TestsExistRule()
        result = rule.check("code", spec_path=src)
        assert result.status == Status.FAIL


# ═══════════════════════════════════════════════════════════════════════════
# C03: TestsPassRule
# ═══════════════════════════════════════════════════════════════════════════


class TestTestsPassRule:
    def test_rule_id(self) -> None:
        assert TestsPassRule().rule_id == "C03"

    def test_rule_name(self) -> None:
        assert TestsPassRule().name == "Tests Pass"

    def test_no_path_skips(self) -> None:
        rule = TestsPassRule()
        result = rule.check("code", spec_path=None)
        assert result.status == Status.SKIP

    def test_no_tests_dir_skips(self, tmp_path: Path) -> None:
        src = tmp_path / "mymod.py"
        src.write_text("x = 1\n")
        rule = TestsPassRule()
        result = rule.check("code", spec_path=src)
        assert result.status == Status.SKIP

    def test_no_test_file_skips(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "tests").mkdir()
        src = tmp_path / "mymod.py"
        src.write_text("x = 1\n")

        rule = TestsPassRule()
        result = rule.check("code", spec_path=src)
        assert result.status == Status.SKIP

    def test_passing_tests_pass(self, tmp_path: Path) -> None:
        """Mocked PythonQARunner returns passing results."""
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("def test_it(): pass\n")
        src = tmp_path / "mymod.py"
        src.write_text("x = 1\n")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="Passed",
            exports={"failed": 0, "errors": 0, "failures": []},
        )
        with patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom") as mock_runner:
            mock_runner.return_value.run.return_value = mock_result
            rule = TestsPassRule()
            result = rule.check("code", spec_path=src)
        assert result.status == Status.PASS

    def test_failing_tests_fail(self, tmp_path: Path) -> None:
        """Mocked PythonQARunner returns failing results."""
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("def test_it(): assert False\n")
        src = tmp_path / "mymod.py"
        src.write_text("x = 1\n")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_result = AtomResult(
            status=AtomStatus.FAILED,
            message="Failed",
            exports={"failed": 1, "errors": 0, "failures": [{"message": "assert False"}]},
        )
        with patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom") as mock_runner:
            mock_runner.return_value.run.return_value = mock_result
            rule = TestsPassRule()
            result = rule.check("code", spec_path=src)
        assert result.status == Status.FAIL

    def test_timeout_fails(self, tmp_path: Path) -> None:
        """Mocked PythonQARunner raises TimeoutError."""
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("pass\n")
        src = tmp_path / "mymod.py"
        src.write_text("x = 1\n")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_result = AtomResult(status=AtomStatus.FAILED, message="timed out after 120s")
        with patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom") as mock_runner:
            mock_runner.return_value.run.return_value = mock_result
            rule = TestsPassRule()
            result = rule.check("code", spec_path=src)
        assert result.status == Status.FAIL
        assert any("timed out" in f.message.lower() for f in result.findings)
