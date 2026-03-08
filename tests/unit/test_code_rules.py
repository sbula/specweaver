# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for code generation and code validation rules C01-C08."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path


import pytest

from specweaver.implementation.generator import Generator
from specweaver.llm.errors import GenerationError
from specweaver.llm.models import GenerationConfig, LLMResponse
from specweaver.validation.models import Status
from specweaver.validation.rules.code.c01_syntax_valid import SyntaxValidRule
from specweaver.validation.rules.code.c02_tests_exist import TestsExistRule
from specweaver.validation.rules.code.c03_tests_pass import TestsPassRule
from specweaver.validation.rules.code.c04_coverage import CoverageRule
from specweaver.validation.rules.code.c05_import_direction import ImportDirectionRule
from specweaver.validation.rules.code.c06_no_bare_except import NoBareExceptRule
from specweaver.validation.rules.code.c07_no_orphan_todo import NoOrphanTodoRule
from specweaver.validation.rules.code.c08_type_hints import TypeHintsRule
from specweaver.validation.runner import get_code_rules

# ---------------------------------------------------------------------------
# C01 Syntax Valid
# ---------------------------------------------------------------------------


class TestC01SyntaxValid:
    """Test the Syntax Valid rule."""

    def test_valid_python(self) -> None:
        rule = SyntaxValidRule()
        result = rule.check("def foo() -> int:\n    return 42\n")
        assert result.status == Status.PASS

    def test_invalid_python(self) -> None:
        rule = SyntaxValidRule()
        result = rule.check("def foo(\n")
        assert result.status == Status.FAIL
        assert result.findings
        assert result.findings[0].line is not None

    def test_empty_code(self) -> None:
        rule = SyntaxValidRule()
        result = rule.check("")
        assert result.status == Status.PASS

    def test_syntax_error_message(self) -> None:
        rule = SyntaxValidRule()
        result = rule.check("class:\n  pass")
        assert result.status == Status.FAIL
        assert "SyntaxError" in result.findings[0].message

    def test_rule_id(self) -> None:
        assert SyntaxValidRule().rule_id == "C01"
        assert SyntaxValidRule().name == "Syntax Valid"


# ---------------------------------------------------------------------------
# C02 Tests Exist
# ---------------------------------------------------------------------------


class TestC02TestsExist:
    """Test the Tests Exist rule."""

    def test_no_path(self) -> None:
        rule = TestsExistRule()
        result = rule.check("code", None)
        assert result.status == Status.SKIP

    def test_test_file_exists(self, tmp_path: pytest.TempPathFactory) -> None:
        # Create a source file and its test file
        src = tmp_path / "foo.py"
        src.write_text("pass")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_foo.py"
        test_file.write_text("pass")

        rule = TestsExistRule()
        result = rule.check("pass", src)
        assert result.status == Status.PASS

    def test_test_file_missing(self, tmp_path: pytest.TempPathFactory) -> None:
        src = tmp_path / "foo.py"
        src.write_text("pass")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        rule = TestsExistRule()
        result = rule.check("pass", src)
        assert result.status == Status.FAIL

    def test_rule_id(self) -> None:
        assert TestsExistRule().rule_id == "C02"


# ---------------------------------------------------------------------------
# C05 Import Direction
# ---------------------------------------------------------------------------


class TestC05ImportDirection:
    """Test the Import Direction rule."""

    def test_clean_imports(self) -> None:
        code = "from specweaver.llm.models import Message\n"
        rule = ImportDirectionRule()
        result = rule.check(code)
        assert result.status == Status.PASS

    def test_forbidden_cli_import(self) -> None:
        code = "from specweaver.cli import app\n"
        rule = ImportDirectionRule()
        result = rule.check(code)
        assert result.status == Status.FAIL
        assert "Forbidden import" in result.findings[0].message

    def test_forbidden_direct_import(self) -> None:
        code = "import specweaver.cli\n"
        rule = ImportDirectionRule()
        result = rule.check(code)
        assert result.status == Status.FAIL

    def test_syntax_error_skips(self) -> None:
        code = "def foo(\n"
        rule = ImportDirectionRule()
        result = rule.check(code)
        assert result.status == Status.SKIP

    def test_rule_id(self) -> None:
        assert ImportDirectionRule().rule_id == "C05"


# ---------------------------------------------------------------------------
# C06 No Bare Except
# ---------------------------------------------------------------------------


class TestC06NoBareExcept:
    """Test the No Bare Except rule."""

    def test_no_bare_except(self) -> None:
        code = "try:\n    pass\nexcept Exception:\n    pass\n"
        rule = NoBareExceptRule()
        result = rule.check(code)
        assert result.status == Status.PASS

    def test_bare_except_found(self) -> None:
        code = "try:\n    pass\nexcept:\n    pass\n"
        rule = NoBareExceptRule()
        result = rule.check(code)
        assert result.status == Status.WARN
        assert len(result.findings) == 1

    def test_multiple_bare_excepts(self) -> None:
        code = "try:\n    pass\nexcept:\n    pass\ntry:\n    pass\nexcept:\n    pass\n"
        rule = NoBareExceptRule()
        result = rule.check(code)
        assert result.status == Status.WARN
        assert len(result.findings) == 2

    def test_rule_id(self) -> None:
        assert NoBareExceptRule().rule_id == "C06"


# ---------------------------------------------------------------------------
# C07 No Orphan TODO
# ---------------------------------------------------------------------------


class TestC07NoOrphanTodo:
    """Test the No Orphan TODO rule."""

    def test_no_todos(self) -> None:
        code = "def foo() -> int:\n    return 42\n"
        rule = NoOrphanTodoRule()
        result = rule.check(code)
        assert result.status == Status.PASS

    def test_todo_found(self) -> None:
        code = "# TODO: implement this\ndef foo():\n    pass\n"
        rule = NoOrphanTodoRule()
        result = rule.check(code)
        assert result.status == Status.WARN
        assert len(result.findings) == 1

    def test_fixme_found(self) -> None:
        code = "# FIXME: broken\npass\n"
        rule = NoOrphanTodoRule()
        result = rule.check(code)
        assert result.status == Status.WARN

    def test_hack_and_xxx_found(self) -> None:
        code = "# HACK: workaround\n# XXX: review later\npass\n"
        rule = NoOrphanTodoRule()
        result = rule.check(code)
        assert result.status == Status.WARN
        assert len(result.findings) == 2

    def test_rule_id(self) -> None:
        assert NoOrphanTodoRule().rule_id == "C07"


# ---------------------------------------------------------------------------
# C08 Type Hints
# ---------------------------------------------------------------------------


class TestC08TypeHints:
    """Test the Type Hints rule."""

    def test_all_typed(self) -> None:
        code = "def foo() -> int:\n    return 42\ndef bar() -> str:\n    return 'hi'\n"
        rule = TypeHintsRule()
        result = rule.check(code)
        assert result.status == Status.PASS

    def test_missing_return_type(self) -> None:
        code = "def foo():\n    return 42\n"
        rule = TypeHintsRule()
        result = rule.check(code)
        # With only 1 public function missing -> 0% -> FAIL
        assert result.status == Status.FAIL

    def test_private_functions_ignored(self) -> None:
        code = "def _private():\n    pass\ndef __dunder__():\n    pass\n"
        rule = TypeHintsRule()
        result = rule.check(code)
        assert result.status == Status.PASS  # No public functions

    def test_mixed_coverage(self) -> None:
        code = (
            "def foo() -> int:\n    return 1\n"
            "def bar() -> int:\n    return 2\n"
            "def baz():\n    pass\n"
        )
        rule = TypeHintsRule()
        result = rule.check(code)
        # 2/3 typed = 66% -> WARN
        assert result.status == Status.WARN

    def test_rule_id(self) -> None:
        assert TypeHintsRule().rule_id == "C08"


# ---------------------------------------------------------------------------
# Runner integration
# ---------------------------------------------------------------------------


class TestCodeRulesRunner:
    """Test get_code_rules and running them."""

    def test_get_code_rules_default(self) -> None:
        rules = get_code_rules()
        ids = [r.rule_id for r in rules]
        assert "C01" in ids
        assert "C03" in ids  # Subprocess rules included
        assert "C04" in ids

    def test_get_code_rules_no_subprocess(self) -> None:
        rules = get_code_rules(include_subprocess=False)
        ids = [r.rule_id for r in rules]
        assert "C01" in ids
        assert "C03" not in ids
        assert "C04" not in ids

    def test_run_code_rules_on_clean_code(self) -> None:
        from specweaver.validation.runner import run_rules

        code = "def greet(name: str) -> str:\n    return f'Hello {name}!'\n"
        rules = get_code_rules(include_subprocess=False)
        results = run_rules(rules, code)

        # C01 should pass, most others too (no path for C02)
        c01 = next(r for r in results if r.rule_id == "C01")
        assert c01.status == Status.PASS


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------


def _make_mock_llm(response_text: str = "def greet(): pass\n") -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResponse(
            text=response_text,
            model="test-model",
        )
    )
    return mock_llm


class TestGenerator:
    """Test the code generator."""

    @pytest.mark.asyncio
    async def test_generate_code(self, tmp_path: pytest.TempPathFactory) -> None:
        spec = tmp_path / "greet_spec.md"
        spec.write_text("# Greet Service\n\n## 1. Purpose\nGreets people.", encoding="utf-8")

        output = tmp_path / "greet.py"

        mock_llm = _make_mock_llm("def greet(name: str) -> str:\n    return f'Hello {name}!'\n")
        gen = Generator(llm=mock_llm)

        result = await gen.generate_code(spec, output)

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "def greet" in content

    @pytest.mark.asyncio
    async def test_generate_tests(self, tmp_path: pytest.TempPathFactory) -> None:
        spec = tmp_path / "greet_spec.md"
        spec.write_text("# Greet Service\n\n## Contract\ndef greet(name) -> str", encoding="utf-8")

        output = tmp_path / "test_greet.py"

        mock_llm = _make_mock_llm("import pytest\ndef test_greet():\n    assert True\n")
        gen = Generator(llm=mock_llm)

        result = await gen.generate_tests(spec, output)

        assert result.exists()
        assert "test_greet" in result.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_generate_creates_dirs(self, tmp_path: pytest.TempPathFactory) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")

        output = tmp_path / "nested" / "dir" / "code.py"

        mock_llm = _make_mock_llm("pass\n")
        gen = Generator(llm=mock_llm)

        result = await gen.generate_code(spec, output)
        assert result.exists()

    def test_clean_code_removes_markdown_fences(self) -> None:
        text = "```python\ndef foo():\n    pass\n```"
        result = Generator._clean_code_output(text)
        assert "```" not in result
        assert "def foo" in result

    def test_clean_code_removes_generic_fences(self) -> None:
        text = "```\nsome code\n```"
        result = Generator._clean_code_output(text)
        assert "```" not in result

    def test_clean_code_preserves_plain(self) -> None:
        text = "def foo():\n    pass"
        result = Generator._clean_code_output(text)
        assert "def foo" in result

    @pytest.mark.asyncio
    async def test_custom_config(self, tmp_path: pytest.TempPathFactory) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")
        output = tmp_path / "code.py"

        mock_llm = _make_mock_llm("pass\n")
        config = GenerationConfig(model="custom-model", temperature=0.1)
        gen = Generator(llm=mock_llm, config=config)

        await gen.generate_code(spec, output)

        call_args = mock_llm.generate.call_args
        used_config = call_args[0][1]
        assert used_config.model == "custom-model"


# ---------------------------------------------------------------------------
# CLI code check test
# ---------------------------------------------------------------------------


class TestCLICodeCheck:
    """Test sw check --level=code."""

    def test_check_code_valid_python(self, tmp_path: pytest.TempPathFactory) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        code_file = tmp_path / "clean.py"
        code_file.write_text("def greet(name: str) -> str:\n    return f'Hello {name}'\n")

        runner = CliRunner()
        result = runner.invoke(app, ["check", "--level", "code", str(code_file)])

        assert "C01" in result.output
        # Clean code should have C01 PASS at minimum
        assert "Syntax Valid" in result.output

    def test_check_code_syntax_error(self, tmp_path: pytest.TempPathFactory) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        code_file = tmp_path / "broken.py"
        code_file.write_text("def foo(\n")

        runner = CliRunner()
        result = runner.invoke(app, ["check", "--level", "code", str(code_file)])

        assert result.exit_code == 1
        assert "FAIL" in result.output


# ---------------------------------------------------------------------------
# C03: Tests Pass — subprocess mock tests
# ---------------------------------------------------------------------------


class TestC03TestsPass:
    """C03 runs pytest and checks results (all subprocess-mocked)."""

    def test_skip_when_no_path(self) -> None:
        """Should SKIP when no spec_path is provided."""
        rule = TestsPassRule()
        result = rule.check("code content", spec_path=None)
        assert result.status == Status.SKIP

    def test_skip_when_no_tests_dir(self, tmp_path: Path) -> None:
        """Should SKIP when tests/ directory doesn't exist."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.SKIP
        assert "tests/" in result.message.lower() or "no tests" in result.message.lower()

    def test_skip_when_no_test_file(self, tmp_path: Path) -> None:
        """Should SKIP when test file for the module doesn't exist."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.SKIP
        assert "test_mymod" in result.message

    @patch("specweaver.validation.rules.code.c03_tests_pass.subprocess.run")
    def test_pass_when_tests_succeed(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should PASS when pytest returns exit code 0."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text(
            "def test_ok(): assert True",
            encoding="utf-8",
        )
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="1 passed",
            stderr="",
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.PASS

    @patch("specweaver.validation.rules.code.c03_tests_pass.subprocess.run")
    def test_fail_when_tests_fail(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when pytest returns non-zero exit code."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text(
            "def test_bad(): assert False",
            encoding="utf-8",
        )
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="FAILED test_bad - assert False",
            stderr="",
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert len(result.findings) > 0

    @patch("specweaver.validation.rules.code.c03_tests_pass.subprocess.run")
    def test_fail_when_tests_timeout(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL with timeout message when pytest times out."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="pytest",
            timeout=60,
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "timed out" in result.message.lower()

    @patch("specweaver.validation.rules.code.c03_tests_pass.subprocess.run")
    def test_fail_output_truncated(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Long output should be truncated to last 500 chars."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        long_output = "x" * 1000
        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=long_output,
            stderr="",
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        # Output is truncated to 500 chars
        assert len(result.findings[0].message) <= 500

    @patch("specweaver.validation.rules.code.c03_tests_pass.subprocess.run")
    def test_fail_no_output(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should handle empty pytest output gracefully."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="",
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "No output" in result.findings[0].message


# ---------------------------------------------------------------------------
# C04: Coverage — subprocess mock tests
# ---------------------------------------------------------------------------


class TestC04Coverage:
    """C04 runs pytest --cov and checks coverage (all subprocess-mocked)."""

    def test_skip_when_no_path(self) -> None:
        """Should SKIP when no spec_path is provided."""
        rule = CoverageRule()
        result = rule.check("code content", spec_path=None)
        assert result.status == Status.SKIP

    @patch("specweaver.validation.rules.code.c04_coverage.subprocess.run")
    def test_pass_when_above_threshold(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should PASS when coverage is above the threshold."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="TOTAL     100       5    95%",
            stderr="",
        )

        rule = CoverageRule(threshold=70)
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.PASS
        assert "95%" in result.message

    @patch("specweaver.validation.rules.code.c04_coverage.subprocess.run")
    def test_fail_when_below_threshold(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when coverage is below the threshold."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="TOTAL      50      30    40%",
            stderr="",
        )

        rule = CoverageRule(threshold=70)
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "40%" in result.message
        assert len(result.findings) > 0

    @patch("specweaver.validation.rules.code.c04_coverage.subprocess.run")
    def test_warn_when_output_unparseable(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should WARN when coverage output can't be parsed."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="some unexpected output",
            stderr="",
        )

        rule = CoverageRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.WARN
        assert "unparseable" in result.message.lower() or "parse" in result.message.lower()

    @patch("specweaver.validation.rules.code.c04_coverage.subprocess.run")
    def test_fail_when_timeout(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when coverage check times out."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="pytest",
            timeout=120,
        )

        rule = CoverageRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "timed out" in result.message.lower()

    @patch("specweaver.validation.rules.code.c04_coverage.subprocess.run")
    def test_pass_at_exact_threshold(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should PASS when coverage equals the threshold exactly."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="TOTAL     100      30    70%",
            stderr="",
        )

        rule = CoverageRule(threshold=70)
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.PASS

    @patch("specweaver.validation.rules.code.c04_coverage.subprocess.run")
    def test_fail_one_below_threshold(
        self,
        mock_run: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when coverage is 1% below threshold."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="TOTAL     100      31    69%",
            stderr="",
        )

        rule = CoverageRule(threshold=70)
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL

    def test_custom_threshold(self) -> None:
        """CoverageRule should accept a custom threshold."""
        rule = CoverageRule(threshold=90)
        assert rule._threshold == 90

    def test_default_threshold(self) -> None:
        """Default threshold should be 70."""
        rule = CoverageRule()
        assert rule._threshold == 70


# ---------------------------------------------------------------------------
# Generator — behavioral tests (failure, boundaries, unexpected input)
# ---------------------------------------------------------------------------


def _failing_llm(exc: Exception | None = None) -> MagicMock:
    """Create a mock LLM that raises on generate."""
    mock = MagicMock()
    mock.generate = AsyncMock(
        side_effect=exc or GenerationError("LLM exploded", provider="test"),
    )
    return mock


class TestGeneratorBehavioral:
    """Behavioral tests: failure, boundaries, unexpected input."""

    @pytest.mark.asyncio
    async def test_llm_error_propagates(self, tmp_path: Path) -> None:
        """Failure: LLM raises → exception propagates to caller."""
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n## 1. Purpose\nDoes things.", encoding="utf-8")
        output = tmp_path / "code.py"

        gen = Generator(llm=_failing_llm())
        with pytest.raises(GenerationError, match="LLM exploded"):
            await gen.generate_code(spec, output)

    @pytest.mark.asyncio
    async def test_llm_returns_empty_text(self, tmp_path: Path) -> None:
        """Boundary: LLM returns empty string → file is still written."""
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")
        output = tmp_path / "code.py"

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(text="", model="test-model"),
        )
        gen = Generator(llm=mock_llm)
        result = await gen.generate_code(spec, output)

        assert result.exists()
        assert result.read_text(encoding="utf-8") == "\n"

    @pytest.mark.asyncio
    async def test_spec_file_not_found(self, tmp_path: Path) -> None:
        """Unexpected input: spec_path doesn't exist → FileNotFoundError."""
        spec = tmp_path / "nonexistent.md"
        output = tmp_path / "code.py"

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(text="pass", model="test-model"),
        )
        gen = Generator(llm=mock_llm)
        with pytest.raises(FileNotFoundError):
            await gen.generate_code(spec, output)

    @pytest.mark.asyncio
    async def test_empty_spec_file(self, tmp_path: Path) -> None:
        """Boundary: 0-byte spec → still generates (LLM gets empty content)."""
        spec = tmp_path / "empty_spec.md"
        spec.write_text("", encoding="utf-8")
        output = tmp_path / "code.py"

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=LLMResponse(text="pass\n", model="test-model"),
        )
        gen = Generator(llm=mock_llm)
        result = await gen.generate_code(spec, output)

        assert result.exists()
        assert "pass" in result.read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_llm_error_on_generate_tests(self, tmp_path: Path) -> None:
        """Failure: LLM error during generate_tests → propagates."""
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")
        output = tmp_path / "test_code.py"

        gen = Generator(llm=_failing_llm())
        with pytest.raises(GenerationError):
            await gen.generate_tests(spec, output)

    @pytest.mark.asyncio
    async def test_output_not_written_on_error(self, tmp_path: Path) -> None:
        """Exception: on LLM error, output file should NOT be created."""
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")
        output = tmp_path / "code.py"

        gen = Generator(llm=_failing_llm())
        with pytest.raises(GenerationError):
            await gen.generate_code(spec, output)

        assert not output.exists()


# ---------------------------------------------------------------------------
# Generator._clean_code_output — pure function tests
# ---------------------------------------------------------------------------


class TestCleanCodeOutput:
    """Test the markdown fence stripping helper."""

    def test_removes_python_fences(self) -> None:
        """Strips ```python ... ``` wrapper."""
        raw = "```python\nprint('hello')\n```"
        assert Generator._clean_code_output(raw) == "print('hello')\n"

    def test_removes_plain_fences(self) -> None:
        """Strips plain ``` ... ``` wrapper."""
        raw = "```\nprint('hello')\n```"
        assert Generator._clean_code_output(raw) == "print('hello')\n"

    def test_no_fences_passthrough(self) -> None:
        """Code without fences passes through unchanged (plus trailing newline)."""
        raw = "print('hello')"
        assert Generator._clean_code_output(raw) == "print('hello')\n"

    def test_only_trailing_fence(self) -> None:
        """Only trailing ``` is stripped."""
        raw = "print('hello')\n```"
        assert Generator._clean_code_output(raw) == "print('hello')\n"

    def test_empty_input(self) -> None:
        """Empty string → just a newline."""
        assert Generator._clean_code_output("") == "\n"

    def test_whitespace_around_fences(self) -> None:
        """Leading/trailing whitespace around fenced code is stripped."""
        raw = "  \n```python\ncode()\n```  \n"
        assert Generator._clean_code_output(raw) == "code()\n"


# ---------------------------------------------------------------------------
# Validation runner — filter logic tests
# ---------------------------------------------------------------------------


class TestValidationRunnerFiltering:
    """Test that runner filter flags work correctly."""

    def test_code_rules_without_subprocess_excludes_c03_c04(self) -> None:
        """include_subprocess=False → no TestsPassRule or CoverageRule."""
        from specweaver.validation.runner import get_code_rules

        rules = get_code_rules(include_subprocess=False)
        rule_ids = {r.rule_id for r in rules}

        assert "C03" not in rule_ids
        assert "C04" not in rule_ids
        assert "C01" in rule_ids
        assert "C05" in rule_ids

    def test_code_rules_with_subprocess_includes_c03_c04(self) -> None:
        """include_subprocess=True → includes TestsPassRule and CoverageRule."""
        from specweaver.validation.runner import get_code_rules

        rules = get_code_rules(include_subprocess=True)
        rule_ids = {r.rule_id for r in rules}

        assert "C03" in rule_ids
        assert "C04" in rule_ids

    def test_spec_rules_without_llm_excludes_llm_rules(self) -> None:
        """include_llm=False → only non-LLM spec rules returned."""
        from specweaver.validation.runner import get_spec_rules

        rules = get_spec_rules(include_llm=False)
        assert all(not r.requires_llm for r in rules)

    def test_run_rules_exception_in_rule(self) -> None:
        """A crashing rule → FAIL result with error message, not an exception."""
        from specweaver.validation.runner import run_rules

        class CrashingRule:
            rule_id = "X99"
            name = "Crash"
            requires_llm = False

            def check(self, text: str, path: object = None) -> None:
                msg = "boom"
                raise RuntimeError(msg)

        results = run_rules([CrashingRule()], "some text")  # type: ignore[list-item]

        assert len(results) == 1
        assert results[0].status == Status.FAIL
        assert "boom" in results[0].message

