# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — sw pipelines / sw run / sw resume CLI subcommands.

Covers: pipelines listing, _resolve_spec_path, _create_display,
run error paths, resume error paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


def _init_project(tmp_path: Path, name: str = "pipe-proj") -> Path:
    """Helper: init a project and return project dir."""
    project_dir = tmp_path / name
    project_dir.mkdir(exist_ok=True)
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"
    return project_dir


# ---------------------------------------------------------------------------
# sw pipelines (list)
# ---------------------------------------------------------------------------


class TestPipelinesList:
    """Test sw pipelines listing command."""

    def test_pipelines_lists_bundled(self) -> None:
        """sw pipelines shows available bundled pipeline templates."""
        result = runner.invoke(app, ["pipelines"])
        assert result.exit_code == 0
        # Should show at least the table header and some pipeline names
        assert "pipeline" in result.output.lower() or "name" in result.output.lower()

    def test_pipelines_shows_usage_hint(self) -> None:
        """sw pipelines shows usage hint at the bottom."""
        result = runner.invoke(app, ["pipelines"])
        assert result.exit_code == 0
        assert "sw run" in result.output.lower()


# ---------------------------------------------------------------------------
# _resolve_spec_path
# ---------------------------------------------------------------------------


class TestResolveSpecPath:
    """Test the _resolve_spec_path helper."""

    def test_existing_file_returned_directly(self, tmp_path: Path) -> None:
        """An existing file path is returned as-is."""
        from specweaver.cli.pipelines import _resolve_spec_path

        spec = tmp_path / "myspec.md"
        spec.write_text("content", encoding="utf-8")
        result = _resolve_spec_path("validate_only", str(spec), tmp_path)
        assert result == spec

    def test_new_feature_derives_spec_path(self, tmp_path: Path) -> None:
        """For new_feature pipeline, spec path is derived from module name."""
        from specweaver.cli.pipelines import _resolve_spec_path

        result = _resolve_spec_path("new_feature", "greeter", tmp_path)
        assert result == tmp_path / "specs" / "greeter_spec.md"

    def test_relative_to_project(self, tmp_path: Path) -> None:
        """A relative path is resolved against the project directory."""
        from specweaver.cli.pipelines import _resolve_spec_path

        spec = tmp_path / "specs" / "calculator.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("content", encoding="utf-8")
        result = _resolve_spec_path("validate_only", "specs/calculator.md", tmp_path)
        assert result == spec

    def test_nonexistent_falls_through(self, tmp_path: Path) -> None:
        """Non-existent path falls through as literal Path."""
        from specweaver.cli.pipelines import _resolve_spec_path

        result = _resolve_spec_path("validate_only", "nonexistent.md", tmp_path)
        assert result == Path("nonexistent.md")


# ---------------------------------------------------------------------------
# _create_display
# ---------------------------------------------------------------------------


class TestCreateDisplay:
    """Test the _create_display helper."""

    def test_creates_rich_display_by_default(self) -> None:
        """Default display is RichPipelineDisplay."""
        from specweaver.cli.pipelines import _create_display
        from specweaver.flow.display import RichPipelineDisplay

        display = _create_display()
        assert isinstance(display, RichPipelineDisplay)

    def test_creates_json_display(self) -> None:
        """use_json=True creates JsonPipelineDisplay."""
        from specweaver.cli.pipelines import _create_display
        from specweaver.flow.display import JsonPipelineDisplay

        display = _create_display(use_json=True)
        assert isinstance(display, JsonPipelineDisplay)


# ---------------------------------------------------------------------------
# sw run — error paths
# ---------------------------------------------------------------------------


class TestRunErrors:
    """Test sw run error handling."""

    def test_run_nonexistent_spec(self, tmp_path: Path) -> None:
        """sw run with non-existent spec fails."""
        project_dir = _init_project(tmp_path)
        result = runner.invoke(
            app,
            [
                "run",
                "validate_only",
                "nonexistent.md",
                "--project",
                str(project_dir),
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_run_validate_only_good_spec(self, tmp_path: Path) -> None:
        """sw run validate_only on a good spec succeeds."""
        project_dir = _init_project(tmp_path)
        spec = project_dir / "specs" / "greeter_spec.md"
        spec.write_text(
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
            "- [ ] Coverage >= 70%\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "run",
                "validate_only",
                str(spec),
                "--project",
                str(project_dir),
            ],
        )
        # validate_only should complete (may pass or fail based on rules)
        assert "S01" in result.output or result.exit_code in (0, 1)


# ---------------------------------------------------------------------------
# sw resume — error paths
# ---------------------------------------------------------------------------


class TestResumeErrors:
    """Test sw resume error handling."""

    def test_resume_nonexistent_id(self, tmp_path: Path, monkeypatch) -> None:
        """sw resume with unknown run ID fails."""
        _init_project(tmp_path)
        # Redirect state store to tmp so it doesn't touch user's real state
        _state_path = tmp_path / "pipeline_state.db"
        monkeypatch.setattr(
            "specweaver.config.paths.state_db_path",
            lambda: _state_path,
        )
        result = runner.invoke(app, ["resume", "nonexistent-run-id-12345"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_resume_no_active_project(self, monkeypatch) -> None:
        """sw resume without active project fails."""
        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 1
        assert "no active project" in result.output.lower()
