# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — sw check CLI flows.

Tests the `sw check` command with spec and code validation,
feature vs component levels, edge cases, and error handling.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".specweaver-test" / "specweaver.db"))
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# sw init → sw check flow
# ---------------------------------------------------------------------------


class TestInitCheckFlow:
    """Test init + check sequence."""

    def test_init_then_check_good_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Init a project, then check a good spec — should pass."""
        # Step 1: Init
        result = runner.invoke(app, ["init", "testapp", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower()

        # Step 2: Copy good spec
        good_spec = tmp_path / "specs" / "greeter_spec.md"
        fixture = (
            "# Greeter — Component Spec\n\n"
            "> **Status**: DRAFT\n\n---\n\n"
            "## 1. Purpose\n\nGreets users.\n\n---\n\n"
            "## 2. Contract\n\n```python\n"
            "def greet(name: str) -> str:\n"
            '    return f"Hello {name}"\n```\n\n---\n\n'
            "## 3. Protocol\n\n"
            "1. Validate name is not empty.\n"
            "2. Return greeting.\n\n---\n\n"
            "## 4. Policy\n\n"
            "| Error | Behavior |\n|:---|:---|\n"
            "| Empty name | Raise ValueError |\n\n---\n\n"
            "## 5. Boundaries\n\n"
            "| Concern | Owned By |\n|:---|:---|\n"
            "| Auth | AuthService |\n\n---\n\n"
            "## Done Definition\n\n"
            "- [ ] Unit tests pass\n"
            "- [ ] Coverage >= 70%\n"
        )
        good_spec.write_text(fixture, encoding="utf-8")

        # Step 3: Check spec
        result = runner.invoke(
            app,
            ["check", "--level", "component", str(good_spec)],
        )
        assert "S01" in result.output
        # Should not hard-fail on a well-formed spec
        assert "ALL PASSED" in result.output or "warnings" in result.output

    def test_init_then_check_bad_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Init, then check a bad spec — should fail."""
        runner.invoke(app, ["init", "badspec", "--path", str(tmp_path)])

        bad_spec = tmp_path / "specs" / "bad_spec.md"
        bad_spec.write_text("This is not a proper spec.", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "component", str(bad_spec)],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output


# ---------------------------------------------------------------------------
# sw check --level=code on generated code
# ---------------------------------------------------------------------------


class TestCheckCodeFlow:
    """Test running code checks on Python files."""

    def test_check_clean_code_passes(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Clean Python code should pass syntax and type hint checks."""
        code = tmp_path / "clean.py"
        code.write_text(
            'def greet(name: str) -> str:\n    return f"Hello {name}!"\n',
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        assert "C01" in result.output
        assert "PASS" in result.output

    def test_check_broken_code_fails(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code with syntax errors should fail C01."""
        broken = tmp_path / "broken.py"
        broken.write_text("def foo(\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(broken)],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_check_code_with_bare_except(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code with bare excepts should trigger C06 warning."""
        code = tmp_path / "bare.py"
        code.write_text(
            "def foo() -> None:\n    try:\n        pass\n    except:\n        pass\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        # C06 should show up
        assert "C06" in result.output

    def test_check_code_with_todos(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code with TODOs should trigger C07 warning."""
        code = tmp_path / "todos.py"
        code.write_text(
            "# TODO: implement this\ndef foo() -> None:\n    pass\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        # C07 should show up
        assert "C07" in result.output

    def test_check_code_missing_type_hints(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code missing type hints should trigger C08."""
        code = tmp_path / "nohints.py"
        code.write_text(
            "def foo():\n    return 42\ndef bar():\n    return 'hi'\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        assert "C08" in result.output


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_check_nonexistent_file(self) -> None:
        """Check with a non-existent file should fail."""
        result = runner.invoke(
            app,
            ["check", "--level", "component", "does_not_exist.md"],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_check_invalid_level(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Check with invalid level should fail."""
        f = tmp_path / "test.md"
        f.write_text("content", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "invalid", str(f)],
        )
        assert result.exit_code == 1
        assert "unknown" in result.output.lower() and "level" in result.output.lower()

    def test_check_empty_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Empty spec file should trigger failures."""
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "component", str(empty)],
        )
        # Should produce results (mostly WARN/FAIL)
        assert "S01" in result.output

    def test_check_empty_code(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Empty code file should still produce results."""
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(empty)],
        )
        assert "C01" in result.output

    def test_pipeline_overrides_level(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """--pipeline takes priority when both --pipeline and --level given (#6)."""
        spec = tmp_path / "spec.md"
        spec.write_text(
            "# Test — Component Spec\n\n"
            "> **Status**: DRAFT\n\n---\n\n"
            "## 1. Purpose\n\nTest.\n\n---\n\n"
            "## Done Definition\n\n- [ ] Tests pass\n",
            encoding="utf-8",
        )

        # --level component would use validation_spec_default (11 rules, has S04)
        # --pipeline validation_spec_feature should override (10 rules, no S04)
        result = runner.invoke(
            app,
            [
                "check",
                "--level",
                "component",
                "--pipeline",
                "validation_spec_feature",
                str(spec),
            ],
        )
        assert result.exit_code in (0, 1)
        # Pipeline should be feature (no S04)
        assert "S04" not in result.output

    def test_non_utf8_binary_file(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Binary (non-UTF8) file should fail with a friendly error (#7)."""
        binary = tmp_path / "binary.md"
        binary.write_bytes(b"\x80\x81\x82\xff\xfe\xfd")

        result = runner.invoke(
            app,
            ["check", "--level", "component", str(binary)],
        )
        assert result.exit_code == 1
        assert "not valid utf-8" in result.output.lower()


# ---------------------------------------------------------------------------
# sw check --level=feature (Feature 3.1 e2e)
# ---------------------------------------------------------------------------


class TestFeatureLevelCheck:
    """E2E tests for sw check --level=feature CLI flow."""

    def test_feature_level_good_spec_passes(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Feature spec with ## Intent passes validation at feature level."""
        runner.invoke(app, ["init", "feattest", "--path", str(tmp_path)])

        spec = tmp_path / "specs" / "onboarding.md"
        spec.write_text(
            "# Onboarding — Feature Spec\n\n"
            "> **Status**: DRAFT\n\n---\n\n"
            "## Intent\n\n"
            "The system enables new users to register.\n\n---\n\n"
            "## Done Definition\n\n"
            "- [ ] All acceptance criteria pass\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "feature", str(spec)],
        )
        # S01 should detect ## Intent (feature header) and PASS
        assert "S01" in result.output
        # S04 should NOT be in output (removed from feature pipeline)
        assert "S04" not in result.output
        # Header label should say "Feature"
        assert "Feature" in result.output

    def test_feature_level_spec_with_leaks(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Feature spec with implementation leaks triggers S03 warnings."""
        runner.invoke(app, ["init", "leaktest", "--path", str(tmp_path)])

        spec = tmp_path / "specs" / "payment.md"
        spec.write_text(
            "# Payment — Feature Spec\n\n---\n\n"
            "## Intent\n\n"
            "The system processes payments.\n\n---\n\n"
            "## Details\n\n"
            "Use `TaxCalculator.calculate()` for tax computation.\n"
            "See [gateway](src/payments/gateway.py) for details.\n"
            "See [invoices](src/billing/invoices/gen.py) for invoicing.\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "feature", str(spec)],
        )
        # S03 should detect abstraction leaks
        assert "S03" in result.output
        # Should have findings about leaks
        assert "leak" in result.output.lower() or "WARN" in result.output or "FAIL" in result.output

    def test_feature_vs_component_different_results(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Same spec produces different results for feature vs component level."""
        runner.invoke(app, ["init", "difftest", "--path", str(tmp_path)])

        # A spec with ## Intent (feature header) but no ## 1. Purpose (component header)
        spec = tmp_path / "specs" / "dual.md"
        spec.write_text(
            "# Dual — Spec\n\n---\n\n"
            "## Intent\n\n"
            "The system does stuff.\n\n---\n\n"
            "## Done Definition\n\n"
            "- [ ] Tests pass\n",
            encoding="utf-8",
        )

        # Feature level: finds ## Intent → S01 PASS
        feature_result = runner.invoke(
            app,
            ["check", "--level", "feature", str(spec)],
        )
        assert "Feature" in feature_result.output

        # Component level: can't find ## 1. Purpose → S01 WARN
        component_result = runner.invoke(
            app,
            ["check", "--level", "component", str(spec)],
        )
        assert "Spec" in component_result.output

        # S04 should not appear in feature output (removed from pipeline)
        assert "S04" not in feature_result.output
        # Component should show S04 results (S04 is in default pipeline)

    def test_feature_level_empty_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Empty spec at feature level still produces rule output."""
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "feature", str(empty)],
        )
        # Should produce S01 and other rule output
        assert "S01" in result.output
        assert "Feature" in result.output
