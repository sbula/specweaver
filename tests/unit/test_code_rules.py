# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for code generation and code validation rules C01-C08."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.implementation.generator import Generator
from specweaver.llm.models import GenerationConfig, LLMResponse
from specweaver.validation.models import Status
from specweaver.validation.rules.code.c01_syntax_valid import SyntaxValidRule
from specweaver.validation.rules.code.c02_tests_exist import TestsExistRule
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
        code = "def foo() -> int:\n    return 1\ndef bar() -> int:\n    return 2\ndef baz():\n    pass\n"
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
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        text=response_text,
        model="test-model",
    ))
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
