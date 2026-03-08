# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.cli — TDD (tests first)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


# ---------------------------------------------------------------------------
# Help and version
# ---------------------------------------------------------------------------


class TestCLIHelp:
    """Test CLI help output and command discovery."""

    def test_help_shows_all_commands(self) -> None:
        """sw --help lists all available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "check" in result.output
        assert "draft" in result.output
        assert "review" in result.output
        assert "implement" in result.output

    def test_version(self) -> None:
        """sw --version shows the version string."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# sw init
# ---------------------------------------------------------------------------


class TestCLIInit:
    """Test the sw init command."""

    def test_init_creates_project_structure(self, tmp_path: Path) -> None:
        """sw init --project <path> creates .specweaver/ and specs/."""
        result = runner.invoke(app, ["init", "--project", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".specweaver").is_dir()
        assert (tmp_path / "specs").is_dir()
        assert (tmp_path / ".specweaver" / "config.yaml").is_file()

    def test_init_shows_success_message(self, tmp_path: Path) -> None:
        """sw init prints a success confirmation."""
        result = runner.invoke(app, ["init", "--project", str(tmp_path)])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "created" in result.output.lower()

    def test_init_idempotent(self, tmp_path: Path) -> None:
        """Running sw init twice should succeed without errors."""
        result1 = runner.invoke(app, ["init", "--project", str(tmp_path)])
        result2 = runner.invoke(app, ["init", "--project", str(tmp_path)])
        assert result1.exit_code == 0
        assert result2.exit_code == 0

    def test_init_nonexistent_project_shows_error(self) -> None:
        """sw init --project /nonexistent shows an error, not a traceback."""
        result = runner.invoke(app, ["init", "--project", "/nonexistent/xyz"])
        assert result.exit_code != 0
        assert "error" in result.output.lower() or "not" in result.output.lower()


# ---------------------------------------------------------------------------
# Stub commands (should exist but show "not implemented")
# ---------------------------------------------------------------------------


class TestCLIStubs:
    """Test that stub commands exist and exit cleanly."""

    def test_check_help(self) -> None:
        """sw check --help shows help without error."""
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "level" in result.output.lower() or "check" in result.output.lower()

    def test_draft_help(self) -> None:
        """sw draft --help shows help without error."""
        result = runner.invoke(app, ["draft", "--help"])
        assert result.exit_code == 0

    def test_review_help(self) -> None:
        """sw review --help shows help without error."""
        result = runner.invoke(app, ["review", "--help"])
        assert result.exit_code == 0

    def test_implement_help(self) -> None:
        """sw implement --help shows help without error."""
        result = runner.invoke(app, ["implement", "--help"])
        assert result.exit_code == 0

    def test_check_stub_not_implemented(self, tmp_path: Path) -> None:
        """sw check runs validation against a spec file."""
        spec = tmp_path / "test.md"
        spec.write_text("# Test")
        result = runner.invoke(
            app, ["check", "--level", "component", str(spec), "--project", str(tmp_path)]
        )
        # A minimal spec will fail some rules; check outputs validation table
        assert "S01" in result.output or "PASS" in result.output or "FAIL" in result.output


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCLIEdgeCases:
    """Edge cases for the CLI."""

    def test_no_args_shows_help(self) -> None:
        """Running sw with no arguments shows help text."""
        result = runner.invoke(app, [])
        # Typer's no_args_is_help may return 0 or 2 depending on version
        assert result.exit_code in (0, 2)
        assert "init" in result.output.lower()

    def test_unknown_command(self) -> None:
        """Running sw with unknown command shows error."""
        result = runner.invoke(app, ["nonexistent"])
        assert result.exit_code != 0
