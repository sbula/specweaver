# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — sw constitution CLI subcommands.

Covers: constitution show, constitution check, constitution init,
error paths and edge cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

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


def _init_project(tmp_path: Path, name: str = "const-proj") -> Path:
    """Helper: init a project and return project dir."""
    project_dir = tmp_path / name
    project_dir.mkdir(exist_ok=True)
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"
    return project_dir


# ---------------------------------------------------------------------------
# sw constitution init
# ---------------------------------------------------------------------------


class TestConstitutionInit:
    """Test sw constitution init command."""

    def test_init_creates_file(self, tmp_path: Path) -> None:
        """sw constitution init creates CONSTITUTION.md."""
        project_dir = _init_project(tmp_path)
        # Delete the one created by sw init scaffold
        const = project_dir / "CONSTITUTION.md"
        if const.exists():
            const.unlink()
        assert not const.exists()

        result = runner.invoke(
            app,
            ["constitution", "init", "--project", str(project_dir)],
        )
        assert result.exit_code == 0
        assert (project_dir / "CONSTITUTION.md").exists()

    def test_init_already_exists_without_force(self, tmp_path: Path) -> None:
        """sw constitution init refuses to overwrite without --force."""
        project_dir = _init_project(tmp_path)
        (project_dir / "CONSTITUTION.md").write_text("existing", encoding="utf-8")
        result = runner.invoke(
            app,
            ["constitution", "init", "--project", str(project_dir)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output.lower()

    def test_init_force_overwrites(self, tmp_path: Path) -> None:
        """sw constitution init --force overwrites existing file."""
        project_dir = _init_project(tmp_path)
        (project_dir / "CONSTITUTION.md").write_text("old content", encoding="utf-8")
        result = runner.invoke(
            app,
            ["constitution", "init", "--force", "--project", str(project_dir)],
        )
        assert result.exit_code == 0
        content = (project_dir / "CONSTITUTION.md").read_text(encoding="utf-8")
        assert content != "old content"


# ---------------------------------------------------------------------------
# sw constitution show
# ---------------------------------------------------------------------------


class TestConstitutionShow:
    """Test sw constitution show command."""

    def test_show_displays_content(self, tmp_path: Path) -> None:
        """sw constitution show displays the file content."""
        project_dir = _init_project(tmp_path)
        (project_dir / "CONSTITUTION.md").write_text(
            "# Constitution\n\nRule 1: Be nice.\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["constitution", "show", "--project", str(project_dir)],
        )
        assert result.exit_code == 0
        assert "be nice" in result.output.lower()

    def test_show_no_constitution(self, tmp_path: Path) -> None:
        """sw constitution show with no file shows error."""
        project_dir = _init_project(tmp_path)
        # Remove generated CONSTITUTION.md if scaffold created one
        const = project_dir / "CONSTITUTION.md"
        if const.exists():
            const.unlink()
        result = runner.invoke(
            app,
            ["constitution", "show", "--project", str(project_dir)],
        )
        assert result.exit_code == 1
        assert "no constitution" in result.output.lower()

    def test_show_nonexistent_project(self, tmp_path: Path) -> None:
        """sw constitution show with bad --project fails."""
        result = runner.invoke(
            app,
            ["constitution", "show", "--project", str(tmp_path / "nonexistent")],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# sw constitution check
# ---------------------------------------------------------------------------


class TestConstitutionCheck:
    """Test sw constitution check command."""

    def test_check_within_limits(self, tmp_path: Path) -> None:
        """sw constitution check passes for small constitution."""
        project_dir = _init_project(tmp_path)
        (project_dir / "CONSTITUTION.md").write_text(
            "# Constitution\n\nShort content.\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["constitution", "check", "--project", str(project_dir)],
        )
        assert result.exit_code == 0
        assert "within" in result.output.lower() or "\u2713" in result.output

    def test_check_no_constitution(self, tmp_path: Path) -> None:
        """sw constitution check with no file shows error."""
        project_dir = _init_project(tmp_path)
        const = project_dir / "CONSTITUTION.md"
        if const.exists():
            const.unlink()
        result = runner.invoke(
            app,
            ["constitution", "check", "--project", str(project_dir)],
        )
        assert result.exit_code == 1
        assert "no constitution" in result.output.lower()
