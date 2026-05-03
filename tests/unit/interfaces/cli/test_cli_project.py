# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for new CLI commands: sw init (DB), sw use, sw projects, sw remove, sw update, sw scan."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fixtures.db_utils import get_test_active_project, get_test_project

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".specweaver-test" / "specweaver.db"))
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.get_db", lambda: db)
    return db


@pytest.fixture
def mock_db(_mock_db):
    """Expose the mock DB for tests that need to inspect it."""
    return _mock_db


# ---------------------------------------------------------------------------
# sw init <name> --path <path>
# ---------------------------------------------------------------------------


class TestCLIInitDB:
    """Test the DB-backed sw init command."""

    def test_init_registers_project(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert result.exit_code == 0
        assert "registered" in result.output.lower() or "initialized" in result.output.lower()

    def test_init_creates_marker(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert (project_dir / ".specweaver").is_dir()

    def test_init_creates_context_yaml(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert (project_dir / "context.yaml").is_file()

    def test_init_creates_specs_dir(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert (project_dir / "specs").is_dir()

    def test_init_creates_template(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert (project_dir / ".specweaver" / "templates" / "component_spec.md").is_file()

    def test_init_creates_specweaverignore(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert (project_dir / ".specweaverignore").is_file()

    def test_init_no_config_yaml(self, tmp_path: Path):
        """Marker-only: .specweaver/config.yaml should NOT be created."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert not (project_dir / ".specweaver" / "config.yaml").exists()

    def test_init_sets_active_project(self, mock_db, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        runner.invoke(app, ["init", "my-app", "--path", str(project_dir)])
        assert get_test_active_project(mock_db) == "my-app"

    def test_init_invalid_name_special_chars(self, tmp_path: Path):
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "My App!", "--path", str(project_dir)])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_init_invalid_name_spaces(self, tmp_path: Path):
        """Spaces are not allowed in project names."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "my app", "--path", str(project_dir)])
        assert result.exit_code != 0

    def test_init_invalid_name_uppercase(self, tmp_path: Path):
        """Uppercase chars are not allowed in project names."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "MyApp", "--path", str(project_dir)])
        assert result.exit_code != 0

    def test_init_valid_name_with_hyphens(self, tmp_path: Path):
        """Hyphens are allowed."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "my-cool-app", "--path", str(project_dir)])
        assert result.exit_code == 0

    def test_init_valid_name_with_underscores(self, tmp_path: Path):
        """Underscores are allowed."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "my_cool_app", "--path", str(project_dir)])
        assert result.exit_code == 0

    def test_init_duplicate_name(self, tmp_path: Path):
        dir1 = tmp_path / "proj1"
        dir1.mkdir()
        dir2 = tmp_path / "proj2"
        dir2.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(dir1)])
        result = runner.invoke(app, ["init", "myapp", "--path", str(dir2)])
        assert result.exit_code != 0
        assert "already exists" in result.output.lower()

    def test_init_nonexistent_path(self, tmp_path: Path):
        result = runner.invoke(app, ["init", "myapp", "--path", str(tmp_path / "nonexistent")])
        assert result.exit_code != 0

    def test_init_defaults_to_cwd(self, mock_db, tmp_path: Path, monkeypatch):
        """sw init <name> without --path uses current directory."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "myapp"])
        assert result.exit_code == 0
        assert get_test_project(mock_db, "myapp") is not None

    def test_init_name_starting_with_hyphen(self, tmp_path: Path):
        """Project name starting with hyphen should be rejected."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "-bad-name", "--path", str(project_dir)])
        # Typer may interpret this as a flag, or DB validation rejects it
        assert result.exit_code != 0

    def test_init_empty_name(self, tmp_path: Path):
        """Empty project name should be rejected."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        result = runner.invoke(app, ["init", "", "--path", str(project_dir)])
        assert result.exit_code != 0

    def test_init_with_mcp_flag_postgres(self, mock_db, tmp_path: Path):
        """sw init <name> --mcp postgres provisions the target DB envelope."""
        project_dir = tmp_path / "mcp-proj"
        project_dir.mkdir()
        result = runner.invoke(
            app, ["init", "mcp-app", "--path", str(project_dir), "--mcp", "postgres"]
        )
        assert result.exit_code == 0
        assert (project_dir / ".specweaver_mcp" / "postgres" / "context.yaml").is_file()
        assert (project_dir / ".specweaver" / "vault.env").is_file()

    @patch("specweaver.interfaces.cli.projects.scaffold_project")
    def test_init_with_mcp_flag_invalid(self, mock_scaffold, mock_db, tmp_path: Path):
        """sw init catches ValueError from scaffold_project and rejects invalid mcp boundaries."""
        project_dir = tmp_path / "mcp-fail-proj"
        project_dir.mkdir()

        mock_scaffold.side_effect = ValueError("Unsupported MCP Target boundary")

        result = runner.invoke(
            app, ["init", "fail-app", "--path", str(project_dir), "--mcp", "invalid"]
        )
        assert result.exit_code == 1
        assert "Error: Unsupported MCP Target" in result.stdout


# ---------------------------------------------------------------------------
# sw use <name>
# ---------------------------------------------------------------------------


class TestCLIUse:
    """Test sw use command."""

    def test_use_switches_project(self, mock_db, tmp_path: Path):
        dir1 = tmp_path / "p1"
        dir1.mkdir()
        dir2 = tmp_path / "p2"
        dir2.mkdir()
        runner.invoke(app, ["init", "app1", "--path", str(dir1)])
        runner.invoke(app, ["init", "app2", "--path", str(dir2)])
        result = runner.invoke(app, ["use", "app1"])
        assert result.exit_code == 0
        assert get_test_active_project(mock_db) == "app1"

    def test_use_shows_confirmation(self, tmp_path: Path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        result = runner.invoke(app, ["use", "myapp"])
        assert result.exit_code == 0
        assert "myapp" in result.output

    def test_use_nonexistent_suggests_init(self):
        result = runner.invoke(app, ["use", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()
        assert "sw init" in result.output.lower()

    def test_use_detects_stale_path(self, tmp_path: Path):
        """If project root was deleted, warn the user."""
        project_dir = tmp_path / "deleted-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "stale", "--path", str(project_dir)])
        shutil.rmtree(project_dir)
        result = runner.invoke(app, ["use", "stale"])
        assert result.exit_code != 0
        assert "no longer exists" in result.output.lower()

    def test_use_stale_suggests_update_or_remove(self, tmp_path: Path):
        """Stale path error should suggest sw update or sw remove."""
        project_dir = tmp_path / "gone-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "gone", "--path", str(project_dir)])
        shutil.rmtree(project_dir)
        result = runner.invoke(app, ["use", "gone"])
        assert "sw update" in result.output.lower() or "sw remove" in result.output.lower()

    def test_use_switches_between_multiple(self, mock_db, tmp_path: Path):
        """Switching between 3+ projects works correctly."""
        for name in ("aaa", "bbb", "ccc"):
            d = tmp_path / name
            d.mkdir()
            runner.invoke(app, ["init", name, "--path", str(d)])

        runner.invoke(app, ["use", "aaa"])
        assert get_test_active_project(mock_db) == "aaa"
        runner.invoke(app, ["use", "ccc"])
        assert get_test_active_project(mock_db) == "ccc"
        runner.invoke(app, ["use", "bbb"])
        assert get_test_active_project(mock_db) == "bbb"


# ---------------------------------------------------------------------------
# sw projects
# ---------------------------------------------------------------------------


class TestCLIProjects:
    """Test sw projects command."""

    def test_projects_empty(self):
        result = runner.invoke(app, ["projects"])
        assert result.exit_code == 0
        assert "no projects" in result.output.lower()

    def test_projects_lists_registered(self, tmp_path: Path):
        dir1 = tmp_path / "p1"
        dir1.mkdir()
        dir2 = tmp_path / "p2"
        dir2.mkdir()
        runner.invoke(app, ["init", "alpha", "--path", str(dir1)])
        runner.invoke(app, ["init", "beta", "--path", str(dir2)])
        result = runner.invoke(app, ["projects"])
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output

    def test_projects_shows_active_marker(self, tmp_path: Path):
        """The active project should be marked with *."""
        dir1 = tmp_path / "p1"
        dir1.mkdir()
        runner.invoke(app, ["init", "active-proj", "--path", str(dir1)])
        result = runner.invoke(app, ["projects"])
        assert result.exit_code == 0
        assert "*" in result.output


# ---------------------------------------------------------------------------
# sw remove <name>
# ---------------------------------------------------------------------------


class TestCLIRemove:
    """Test sw remove command."""

    def test_remove_project(self, mock_db, tmp_path: Path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        result = runner.invoke(app, ["remove", "myapp"], input="y\n")
        assert result.exit_code == 0
        assert get_test_project(mock_db, "myapp") is None

    def test_remove_asks_confirmation(self, mock_db, tmp_path: Path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        result = runner.invoke(app, ["remove", "myapp"], input="n\n")
        assert result.exit_code == 0
        assert get_test_project(mock_db, "myapp") is not None  # not removed

    def test_remove_nonexistent(self):
        result = runner.invoke(app, ["remove", "nonexistent"], input="y\n")
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_remove_with_force(self, mock_db, tmp_path: Path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        result = runner.invoke(app, ["remove", "myapp", "--force"])
        assert result.exit_code == 0
        assert get_test_project(mock_db, "myapp") is None

    def test_remove_does_not_delete_files(self, tmp_path: Path):
        """sw remove only unregisters — project files stay on disk."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        runner.invoke(app, ["remove", "myapp", "--force"])
        # Project directory and scaffold should still exist
        assert project_dir.exists()
        assert (project_dir / ".specweaver").is_dir()
        assert (project_dir / "specs").is_dir()


# ---------------------------------------------------------------------------
# sw update <name> path <new-path>
# ---------------------------------------------------------------------------


class TestCLIUpdate:
    """Test sw update command."""

    def test_update_path(self, mock_db, tmp_path: Path):
        old = tmp_path / "old"
        old.mkdir()
        new = tmp_path / "new"
        new.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(old)])
        result = runner.invoke(app, ["update", "myapp", "path", str(new)])
        assert result.exit_code == 0
        proj = get_test_project(mock_db, "myapp")
        assert proj["root_path"] == str(new)

    def test_update_nonexistent_project(self, tmp_path: Path):
        result = runner.invoke(app, ["update", "nonexistent", "path", str(tmp_path)])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_update_unknown_field(self, tmp_path: Path):
        """Updating an unsupported field should fail."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        result = runner.invoke(app, ["update", "myapp", "color", "blue"])
        assert result.exit_code != 0
        assert "unknown field" in result.output.lower() or "supported" in result.output.lower()


# ---------------------------------------------------------------------------
# sw scan
# ---------------------------------------------------------------------------


class TestCLIScan:
    """Test sw scan command."""

    def test_scan_requires_active_project(self):
        result = runner.invoke(app, ["scan"])
        assert result.exit_code != 0
        assert "no active project" in result.output.lower()

    def test_scan_on_project(self, tmp_path: Path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        src_dir = project_dir / "src" / "mymodule"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text("")
        (src_dir / "main.py").write_text("def hello(): pass\n")
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "scan" in result.output.lower()

    def test_scan_skips_hidden_dirs(self, tmp_path: Path):
        """Scan should skip dot-directories like .git, .venv."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        hidden = project_dir / ".git" / "objects"
        hidden.mkdir(parents=True)
        (hidden / "test.py").write_text("x = 1\n")
        runner.invoke(app, ["init", "myapp", "--path", str(project_dir)])
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        # Should not list .git in output
        assert ".git" not in result.output

    def test_scan_skips_pycache(self, tmp_path: Path):
        """Scan should skip __pycache__ directories."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        cache = project_dir / "src" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "mod.cpython-313.pyc").write_bytes(b"\x00")
        runner.invoke(app, ["init", "myapp2", "--path", str(project_dir)])
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "__pycache__" not in result.output

    def test_scan_reports_existing_context(self, tmp_path: Path):
        """Directories with existing context.yaml should be reported as existing."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        sub = project_dir / "submod"
        sub.mkdir()
        (sub / "context.yaml").write_text("name: submod\nlevel: component\n")
        (sub / "main.py").write_text("pass\n")
        runner.invoke(app, ["init", "myapp3", "--path", str(project_dir)])
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "existing" in result.output.lower() or "exists" in result.output.lower()

    def test_scan_sync_tach_success(self, tmp_path: Path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp4", "--path", str(project_dir)])

        # Add a context.yaml to ensure a TopologyGraph builds at least 1 node
        (project_dir / "context.yaml").write_text(
            "name: root\nlevel: module\narchetype: pure-logic\n"
        )

        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Synchronizing Tach Architecture Matrix" in result.output
        assert "Tach Sync" in result.output
        assert "Synchronized" in result.output

    def test_scan_sync_tach_handles_errors(self, tmp_path: Path):
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "myapp5", "--path", str(project_dir)])

        # Corrupt the tach.toml explicitly to simulate a crash inside the adapter
        corrupt = project_dir / "tach.toml"
        corrupt.write_text("[[modules]\nINVALID", encoding="utf-8")

        result = runner.invoke(app, ["scan"])
        # Should catch Exception and not crash the program, exiting 0 normally since scan completes
        assert result.exit_code == 0
        assert "Tach Sync Failed" in result.output


# ---------------------------------------------------------------------------
# sw init — standards scan hint
# ---------------------------------------------------------------------------


class TestInitStandardsScanHint:
    """Test the 'run sw standards scan' hint after sw init."""

    def test_hint_shown_with_existing_python(self, tmp_path: Path) -> None:
        """Init with existing .py files → shows scan hint."""
        project_dir = tmp_path / "existing-proj"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("def main(): pass\n")
        result = runner.invoke(
            app,
            ["init", "existproj", "--path", str(project_dir)],
        )
        assert result.exit_code == 0
        assert "sw standards scan" in result.output

    def test_hint_shown_with_existing_typescript(self, tmp_path: Path) -> None:
        """Init with existing .ts files → shows scan hint."""
        project_dir = tmp_path / "ts-proj"
        project_dir.mkdir()
        (project_dir / "app.ts").write_text("const x = 1;\n")
        result = runner.invoke(
            app,
            ["init", "tsproj", "--path", str(project_dir)],
        )
        assert result.exit_code == 0
        assert "sw standards scan" in result.output

    def test_no_hint_without_source_files(self, tmp_path: Path) -> None:
        """Init with no source files → no scan hint."""
        project_dir = tmp_path / "empty-proj"
        project_dir.mkdir()
        result = runner.invoke(
            app,
            ["init", "emptyproj", "--path", str(project_dir)],
        )
        assert result.exit_code == 0
        assert "sw standards scan" not in result.output

    def test_hint_excludes_hidden_dirs(self, tmp_path: Path) -> None:
        """Init where only source files are in hidden dirs → no scan hint."""
        project_dir = tmp_path / "hidden-proj"
        project_dir.mkdir()
        git_dir = project_dir / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        (git_dir / "pre-commit.py").write_text("print('hook')\n")
        result = runner.invoke(
            app,
            ["init", "hiddenproj", "--path", str(project_dir)],
        )
        assert result.exit_code == 0
        assert "sw standards scan" not in result.output
