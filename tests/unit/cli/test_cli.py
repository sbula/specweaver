# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.cli — TDD (tests first)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""

    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli.get_db", lambda: db)
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
        monkeypatch.setattr(os, "environ", {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"})

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


# ---------------------------------------------------------------------------
# sw check --set one-off overrides
# ---------------------------------------------------------------------------


class TestCheckSetOverrides:
    """Test the --set one-off override flag on sw check."""

    def test_set_flag_help(self) -> None:
        """--set appears in sw check --help."""
        result = runner.invoke(app, ["check", "--help"])
        assert result.exit_code == 0
        assert "--set" in result.output

    def test_set_invalid_format_shows_error(self, tmp_path) -> None:
        """--set without RULE.FIELD=VALUE format → error."""
        spec = tmp_path / "s.md"
        spec.write_text("## 1. Purpose\nX.\n")
        result = runner.invoke(
            app,
            ["check", str(spec), "--set", "BADFORMAT"],
        )
        assert result.exit_code == 1
        assert "Invalid --set format" in result.output

    def test_set_extra_param_routes_to_extra_params(self, tmp_path) -> None:
        """--set with custom field routes to extra_params (e.g. max_h2)."""
        spec = tmp_path / "s.md"
        spec.write_text("## 1. Purpose\nX.\n")
        runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])
        # Should NOT error — unknown fields now go to extra_params
        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--set", "S01.max_h2=3"],
        )
        # The check should run (may pass or fail, but no --set error)
        assert "Invalid --set format" not in result.output

    def test_set_extra_param_non_numeric_shows_error(self, tmp_path) -> None:
        """--set with non-numeric custom field value → error."""
        spec = tmp_path / "s.md"
        spec.write_text("## 1. Purpose\nX.\n")
        result = runner.invoke(
            app,
            ["check", str(spec), "--set", "S01.max_h2=abc"],
        )
        assert result.exit_code == 1
        assert "Invalid value" in result.output

    def test_set_non_numeric_threshold_shows_error(self, tmp_path) -> None:
        """--set with non-numeric threshold → error."""
        spec = tmp_path / "s.md"
        spec.write_text("## 1. Purpose\nX.\n")
        result = runner.invoke(
            app,
            ["check", str(spec), "--set", "S08.fail_threshold=abc"],
        )
        assert result.exit_code == 1
        assert "Invalid threshold value" in result.output

    def test_set_threshold_applied(self, tmp_path) -> None:
        """--set S08.fail_threshold=999 makes S08 very lenient."""
        spec = tmp_path / "spec.md"
        # This spec has weasel words (should, might, could)
        spec.write_text(
            "## 1. Purpose\nDo X.\n\n"
            "## 2. Contract\nShould work. Might fail. Could break.\n",
            encoding="utf-8",
        )
        runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])

        # With very high thresholds, S08 should pass (3 weasels < 999)
        result_lenient = runner.invoke(
            app,
            ["check", str(spec), "--level", "component",
             "--set", "S08.warn_threshold=999", "--set", "S08.fail_threshold=999"],
        )

        # Find S08 line in the output — it should show PASS not FAIL
        lines = result_lenient.output.split("\n")
        s08_lines = [ln for ln in lines if "S08" in ln]
        assert len(s08_lines) > 0, "S08 should appear in output"
        # With threshold=999, S08 must pass (3 weasel words < 999)
        assert any("PASS" in ln for ln in s08_lines), (
            f"S08 should PASS with threshold=999, got: {s08_lines}"
        )

    def test_set_enabled_false_disables_rule(self, tmp_path) -> None:
        """--set S08.enabled=false removes S08 from output."""
        spec = tmp_path / "spec.md"
        spec.write_text("## 1. Purpose\nDo X.\n", encoding="utf-8")
        runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])
        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--set", "S08.enabled=false"],
        )
        # S08 should not appear in results when disabled
        assert "S08" not in result.output


# ---------------------------------------------------------------------------
# sw check DB settings wiring
# ---------------------------------------------------------------------------


class TestCheckDBWiring:
    """Test that sw check loads overrides from the active project's DB."""

    def test_check_loads_db_overrides(self, tmp_path, _mock_db) -> None:
        """Overrides set via DB are applied when sw check runs."""
        spec = tmp_path / "spec.md"
        spec.write_text("## 1. Purpose\nDo X.\n", encoding="utf-8")

        # Register project and set it active
        runner.invoke(app, ["init", "demo", "--path", str(tmp_path)])
        runner.invoke(app, ["use", "demo"])

        # Disable S08 via DB
        _mock_db.set_validation_override("demo", "S08", enabled=False)

        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component"],
        )
        # S08 should be absent from output
        assert "S08" not in result.output

    def test_check_no_active_project_uses_defaults(self, tmp_path) -> None:
        """Without an active project, sw check uses default rules."""
        spec = tmp_path / "spec.md"
        spec.write_text("## 1. Purpose\nDo X.\n", encoding="utf-8")
        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component"],
        )
        # Should still work and show results
        assert "S01" in result.output

    def test_set_overrides_db(self, tmp_path, _mock_db) -> None:
        """--set overrides should take precedence over DB overrides."""
        spec = tmp_path / "spec.md"
        spec.write_text("## 1. Purpose\nDo X.\n", encoding="utf-8")

        runner.invoke(app, ["init", "demo", "--path", str(tmp_path)])
        runner.invoke(app, ["use", "demo"])

        # DB says S08 is enabled
        _mock_db.set_validation_override("demo", "S08", enabled=True)

        # CLI says S08 is disabled (should win)
        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--set", "S08.enabled=false"],
        )
        assert "S08" not in result.output


# ---------------------------------------------------------------------------
# Combined --strict + --set
# ---------------------------------------------------------------------------


class TestCheckStrictAndSetCombined:
    """Test --strict and --set used together."""

    def test_strict_plus_set_disable_rule(self, tmp_path) -> None:
        """--strict + --set S08.enabled=false should work together."""
        spec = tmp_path / "spec.md"
        spec.write_text(
            "## 1. Purpose\nDo X.\n\n## 2. Contract\nShould maybe work.\n",
            encoding="utf-8",
        )
        runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])
        result = runner.invoke(
            app,
            [
                "check", str(spec), "--level", "component",
                "--strict", "--set", "S08.enabled=false",
            ],
        )
        # S08 should be absent from output
        assert "S08" not in result.output

    def test_strict_plus_set_high_threshold(self, tmp_path) -> None:
        """--strict + --set S08.fail_threshold=999 should compose correctly."""
        spec = tmp_path / "spec.md"
        spec.write_text(
            "## 1. Purpose\nDo X.\n\n## 2. Contract\nShould work.\n",
            encoding="utf-8",
        )
        runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])
        result = runner.invoke(
            app,
            [
                "check", str(spec), "--level", "component",
                "--strict",
                "--set", "S08.warn_threshold=999",
                "--set", "S08.fail_threshold=999",
            ],
        )
        # S08 should PASS with high thresholds even in strict mode
        lines = [ln for ln in result.output.split("\n") if "S08" in ln]
        if lines:
            assert any("PASS" in ln for ln in lines)


# ---------------------------------------------------------------------------
# _build_rule_kwargs extra_params support
# ---------------------------------------------------------------------------


class TestBuildRuleKwargsExtraParams:
    """Test that _build_rule_kwargs handles extra_params."""

    def test_extra_params_max_h2_passed_to_s01(self) -> None:
        """extra_params with max_h2 should be included in kwargs for S01."""
        from specweaver.config.settings import RuleOverride, ValidationSettings
        from specweaver.validation.runner import _build_rule_kwargs

        settings = ValidationSettings(
            overrides={
                "S01": RuleOverride(
                    rule_id="S01",
                    extra_params={"max_h2": 3},
                ),
            },
        )
        kwargs = _build_rule_kwargs("S01", settings)
        assert kwargs["max_h2"] == 3

    def test_extra_params_empty_leaves_defaults(self) -> None:
        """Empty extra_params should not inject anything."""
        from specweaver.config.settings import RuleOverride, ValidationSettings
        from specweaver.validation.runner import _build_rule_kwargs

        settings = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01")},
        )
        kwargs = _build_rule_kwargs("S01", settings)
        assert "max_h2" not in kwargs

    def test_extra_params_combined_with_thresholds(self) -> None:
        """extra_params + standard thresholds should both appear."""
        from specweaver.config.settings import RuleOverride, ValidationSettings
        from specweaver.validation.runner import _build_rule_kwargs

        settings = ValidationSettings(
            overrides={
                "S01": RuleOverride(
                    rule_id="S01",
                    warn_threshold=1,
                    fail_threshold=3,
                    extra_params={"max_h2": 5},
                ),
            },
        )
        kwargs = _build_rule_kwargs("S01", settings)
        assert kwargs["warn_conjunctions"] == 1
        assert kwargs["fail_conjunctions"] == 3
        assert kwargs["max_h2"] == 5

    def test_no_settings_returns_empty(self) -> None:
        """None settings should return empty kwargs."""
        from specweaver.validation.runner import _build_rule_kwargs

        assert _build_rule_kwargs("S01", None) == {}
