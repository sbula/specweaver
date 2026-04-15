# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for C03 (tests pass), C04 (coverage), generator, and behavioral tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c03_tests_pass import TestsPassRule
from specweaver.assurance.validation.rules.code.c04_coverage import CoverageRule
from specweaver.assurance.validation.runner import run_rules
from specweaver.infrastructure.llm.errors import GenerationError
from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.workflows.implementation.generator import Generator


def _make_mock_llm(response_text: str = "def greet(): pass\n") -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResponse(
            text=response_text,
            model="test-model",
        )
    )
    return mock_llm


# ---------------------------------------------------------------------------
# C03: Tests Pass — PythonQARunner mock tests
# ---------------------------------------------------------------------------


class TestC03TestsPass:
    """C03 runs pytest via PythonQARunner and checks results."""

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

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_pass_when_tests_succeed(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should PASS when PythonQARunner.run_tests reports no failures."""
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

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="No failures",
            exports={
                "passed": 3,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 3,
            }
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.PASS

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_fail_when_tests_fail(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when PythonQARunner.run_tests reports failures."""
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

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.FAILED,
            message="Tests failed",
            exports={
                "passed": 0,
                "failed": 1,
                "errors": 0,
                "skipped": 0,
                "total": 1,
                "failures": [{"nodeid": "test_bad", "message": "assert False"}],
            }
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert len(result.findings) > 0

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_fail_when_tests_timeout(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL with timeout message when PythonQARunner times out."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.side_effect = TimeoutError("Timed out")

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "timed out" in result.message.lower()

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_fail_output_truncated(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Long failure messages should be truncated to last 500 chars."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        long_message = "x" * 1000
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.FAILED,
            message="Failures",
            exports={
                "passed": 0,
                "failed": 1,
                "errors": 0,
                "skipped": 0,
                "total": 1,
                "failures": [{"nodeid": "test_x", "message": long_message}],
            }
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        # Output is truncated to 500 chars
        assert len(result.findings[0].message) <= 500

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_fail_no_output(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should handle empty failure list gracefully."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymod.py").write_text("", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.FAILED,
            message="Failed but no details",
            exports={
                "passed": 0,
                "failed": 1,
                "errors": 0,
                "skipped": 0,
                "total": 1,
                "failures": [],  # no failure details
            }
        )

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "No output" in result.findings[0].message


# ---------------------------------------------------------------------------
# C04: Coverage — PythonQARunner mock tests
# ---------------------------------------------------------------------------


class TestC04Coverage:
    """C04 runs pytest --cov via PythonQARunner and checks coverage."""

    def test_skip_when_no_path(self) -> None:
        """Should SKIP when no spec_path is provided."""
        rule = CoverageRule()
        result = rule.check("code content", spec_path=None)
        assert result.status == Status.SKIP

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_pass_when_above_threshold(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should PASS when coverage is above the threshold."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="No failures",
            exports={
                "passed": 5,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 5,
                "coverage_pct": 95.0,
            }
        )

        rule = CoverageRule(threshold=70)
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.PASS
        assert "95%" in result.message

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_fail_when_below_threshold(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when coverage is below the threshold."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="No failures",
            exports={
                "passed": 5,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 5,
                "coverage_pct": 40.0,
            }
        )

        rule = CoverageRule(threshold=70)
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "40%" in result.message
        assert len(result.findings) > 0

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_warn_when_output_unparseable(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should WARN when coverage output can't be parsed (coverage_pct=None)."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="No failures",
            exports={
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 0,
                "coverage_pct": None,
            }
        )

        rule = CoverageRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.WARN
        assert "unparseable" in result.message.lower() or "parse" in result.message.lower()

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_fail_when_timeout(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when coverage check times out."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.side_effect = TimeoutError("Timed out")

        rule = CoverageRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.FAIL
        assert "timed out" in result.message.lower()

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_pass_at_exact_threshold(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should PASS when coverage equals the threshold exactly."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="No failures",
            exports={
                "passed": 5,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 5,
                "coverage_pct": 70.0,
            }
        )

        rule = CoverageRule(threshold=70)
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.PASS

    @patch("specweaver.core.loom.atoms.qa_runner.atom.QARunnerAtom")
    def test_fail_one_below_threshold(
        self,
        mock_runner_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Should FAIL when coverage is 1% below threshold."""
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        code = tmp_path / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

        mock_atom = mock_runner_cls.return_value
        mock_atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="No failures",
            exports={
                "passed": 5,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "total": 5,
                "coverage_pct": 69.0,
            }
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
    """Test pipeline filtering (executor path) and runner error handling."""

    def test_code_pipeline_has_c01_c05_but_not_subprocess_by_default(self) -> None:
        """Verify code pipeline step IDs include C01, C05 and also C03/C04."""
        import specweaver.assurance.validation.rules.code  # noqa: F401
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

        pipeline = load_pipeline_yaml("validation_code_default")
        ids = {s.rule for s in pipeline.steps}
        assert "C01" in ids
        assert "C05" in ids
        assert "C03" in ids
        assert "C04" in ids

    def test_code_pipeline_disable_subprocess_rules(self) -> None:
        """Disabling C03/C04 via settings removes subprocess rules."""
        import specweaver.assurance.validation.rules.code  # noqa: F401
        from specweaver.assurance.validation.executor import apply_settings_to_pipeline
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.settings import RuleOverride, ValidationSettings

        pipeline = load_pipeline_yaml("validation_code_default")
        settings = ValidationSettings(
            overrides={
                "C03": RuleOverride(rule_id="C03", enabled=False),
                "C04": RuleOverride(rule_id="C04", enabled=False),
            }
        )
        pipeline = apply_settings_to_pipeline(pipeline, settings)
        ids = {s.rule for s in pipeline.steps}
        assert "C03" not in ids
        assert "C04" not in ids
        assert "C01" in ids
        assert "C05" in ids

    def test_spec_pipeline_has_only_non_llm_rules(self) -> None:
        """Default spec pipeline has no LLM-requiring rules."""
        import specweaver.assurance.validation.rules.spec  # noqa: F401
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.assurance.validation.registry import get_registry

        pipeline = load_pipeline_yaml("validation_spec_default")
        registry = get_registry()
        for step in pipeline.steps:
            rule_cls = registry.get(step.rule)
            if rule_cls is not None:
                assert not getattr(rule_cls(), "requires_llm", False)

    def test_run_rules_exception_in_rule(self) -> None:
        """A crashing rule → FAIL result with error message, not an exception."""

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
