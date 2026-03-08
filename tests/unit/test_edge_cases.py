# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Edge case tests for subprocess rules (C03, C04) and HITL provider.

Tests mock subprocess.run and Rich prompts to avoid real I/O.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from specweaver.context.hitl_provider import HITLProvider
from specweaver.validation.models import Status
from specweaver.validation.rules.code.c03_tests_pass import TestsPassRule
from specweaver.validation.rules.code.c04_coverage import CoverageRule

if TYPE_CHECKING:
    import pytest


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

    def test_skip_when_no_tests_dir(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Should SKIP when tests/ directory doesn't exist."""
        # Create a pyproject.toml so project root is found
        (tmp_path / "pyproject.toml").write_text("[project]", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        code = src / "mymod.py"
        code.write_text("pass", encoding="utf-8")

        rule = TestsPassRule()
        result = rule.check("pass", spec_path=code)
        assert result.status == Status.SKIP
        assert "tests/" in result.message.lower() or "no tests" in result.message.lower()

    def test_skip_when_no_test_file(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
        tmp_path: pytest.TempPathFactory,
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
# HITL Provider — Rich prompt tests
# ---------------------------------------------------------------------------


class TestHITLProvider:
    """Test the Human-in-the-Loop context provider."""

    def test_name(self) -> None:
        """Provider name should be 'hitl'."""
        provider = HITLProvider()
        assert provider.name == "hitl"

    @patch("specweaver.context.hitl_provider.Prompt.ask")
    async def test_ask_returns_stripped_input(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should return stripped user input."""
        mock_ask.return_value = "  user answer  "
        console = MagicMock()

        provider = HITLProvider(console=console)
        result = await provider.ask("What does it do?")
        assert result == "user answer"

    @patch("specweaver.context.hitl_provider.Prompt.ask")
    async def test_ask_with_section(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should display section context when provided."""
        mock_ask.return_value = "answer"
        console = MagicMock()

        provider = HITLProvider(console=console)
        result = await provider.ask(
            "Describe the purpose",
            section="Purpose",
        )

        assert result == "answer"
        # Should have printed the section context
        calls = console.print.call_args_list
        section_printed = any(
            "Section:" in str(c) and "Purpose" in str(c) for c in calls
        )
        assert section_printed

    @patch("specweaver.context.hitl_provider.Prompt.ask")
    async def test_ask_without_section(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should NOT display section context when not provided."""
        mock_ask.return_value = "answer"
        console = MagicMock()

        provider = HITLProvider(console=console)
        await provider.ask("What?")

        calls = console.print.call_args_list
        section_printed = any("Section:" in str(c) for c in calls)
        assert not section_printed

    @patch("specweaver.context.hitl_provider.Prompt.ask")
    async def test_ask_empty_input(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should return empty string when user presses Enter."""
        mock_ask.return_value = ""
        console = MagicMock()

        provider = HITLProvider(console=console)
        result = await provider.ask("Skip this?")
        assert result == ""

    def test_default_console(self) -> None:
        """Should create a default Console if none provided."""
        provider = HITLProvider()
        assert provider._console is not None
