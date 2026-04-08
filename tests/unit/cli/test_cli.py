# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.cli — TDD (tests first)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""

    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


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
        assert "use" in result.output
        assert "projects" in result.output
        assert "remove" in result.output
        assert "update" in result.output
        assert "scan" in result.output

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
        """sw init <name> --path <path> creates .specweaver/ and specs/."""
        result = runner.invoke(app, ["init", "testapp", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / ".specweaver").is_dir()
        assert (tmp_path / "specs").is_dir()

    def test_init_shows_success_message(self, tmp_path: Path) -> None:
        """sw init prints a success confirmation."""
        result = runner.invoke(app, ["init", "testapp", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "created" in result.output.lower()

    def test_init_idempotent_scaffold(self, tmp_path: Path) -> None:
        """Running sw init twice with different names should work (scaffold idempotent)."""
        dir1 = tmp_path / "p1"
        dir1.mkdir()
        dir2 = tmp_path / "p2"
        dir2.mkdir()
        result1 = runner.invoke(app, ["init", "app1", "--path", str(dir1)])
        result2 = runner.invoke(app, ["init", "app2", "--path", str(dir2)])
        assert result1.exit_code == 0
        assert result2.exit_code == 0

    def test_init_nonexistent_project_shows_error(self) -> None:
        """sw init <name> --path /nonexistent shows an error, not a traceback."""
        result = runner.invoke(app, ["init", "testapp", "--path", "/nonexistent/xyz"])
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


# ---------------------------------------------------------------------------
# CLI — behavioral tests (failure, unexpected input)
# ---------------------------------------------------------------------------


class TestCLIBehavioral:
    """Behavioral tests: failure paths, unexpected input."""

    def test_check_with_directory_path(self) -> None:
        """Unexpected input: check with a directory path → error."""
        result = runner.invoke(app, ["check", "tests/"])
        assert result.exit_code == 1

    def test_implement_nonexistent_spec(self) -> None:
        """Failure: implement with non-existent spec → error."""
        result = runner.invoke(app, ["implement", "/nonexistent/spec.md"])
        assert result.exit_code != 0

    def test_review_nonexistent_spec(self) -> None:
        """Failure: review with non-existent spec → error."""
        result = runner.invoke(app, ["review", "/nonexistent/spec.md"])
        assert result.exit_code != 0

    def test_draft_without_api_key_shows_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure: draft without API key → friendly error, not traceback."""
        import os

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # Ensure no key from any source
        monkeypatch.setattr(
            os,
            "environ",
            {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"},
        )

        runner.invoke(app, ["init", "testapp", "--path", str(tmp_path)])
        result = runner.invoke(app, ["draft", "test_comp", "--project", str(tmp_path)])

        assert result.exit_code != 0
        # Should show user-friendly error, not a Python traceback
        assert "Traceback" not in result.output

    def test_check_component_shows_summary(self, tmp_path: Path) -> None:
        """Check with component level → shows summary line with pass/fail counts."""
        spec = tmp_path / "test.md"
        spec.write_text("# Test Spec\n\n## 1. Purpose\n\nDoes one thing.\n", encoding="utf-8")
        runner.invoke(app, ["init", "testcheck", "--path", str(tmp_path)])
        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--project", str(tmp_path)],
        )

        # Should show validation results with status indicators
        assert "PASS" in result.output or "FAIL" in result.output


# ---------------------------------------------------------------------------
# sw check --strict flag
# ---------------------------------------------------------------------------


class TestCheckStrict:
    """Test the --strict flag on sw check."""

    @pytest.fixture()
    def _good_spec(self, tmp_path):
        """Create a spec good enough to pass most rules."""
        spec = tmp_path / "spec.md"
        spec.write_text(
            "# Greeter\n\n"
            "## 1. Purpose\n\nGenerate welcome messages.\n\n"
            "## 2. Contract\n\n```python\ndef greet(name: str) -> str: ...\n```\n\n"
            "## 3. Protocol\n\nCall greet() with a name.\n\n"
            "## 4. Policy\n\nMUST return a non-empty string.\n\n"
            "## 5. Boundaries\n\n- Raises ValueError on empty name.\n"
            "- Done when greet() returns a greeting.\n",
            encoding="utf-8",
        )
        return spec

    def test_strict_flag_help(self) -> None:
        """--strict appears in sw check --help."""
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "--strict" in result.output

    def test_check_without_strict_passes_on_warnings(self, tmp_path, _good_spec):
        """Without --strict, warnings don't cause exit code 1."""
        runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])
        result = runner.invoke(
            app,
            ["check", str(_good_spec), "--level", "component"],
        )
        # If there are only warnings, should pass (exit 0)
        if "PASSED with warnings" in result.output:
            assert result.exit_code == 0

    def test_check_with_strict_fails_on_warnings(self, tmp_path, _good_spec):
        """With --strict, warnings cause exit code 1."""
        runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])
        result = runner.invoke(
            app,
            ["check", str(_good_spec), "--level", "component", "--strict"],
        )
        # If there are warnings, strict mode should exit 1
        if "warning" in result.output.lower():
            assert result.exit_code == 1
