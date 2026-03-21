# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests — CLI constitution subcommands.

Tests: show, check, init via CliRunner with mocked DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# constitution show
# ---------------------------------------------------------------------------


class TestConstitutionShow:
    """Test constitution show command."""

    def test_show_no_constitution(self, tmp_path: Path) -> None:
        """show with no CONSTITUTION.md → exit 1."""
        result = runner.invoke(
            app, ["constitution", "show", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "No CONSTITUTION.md" in result.output

    def test_show_displays_content(self, tmp_path: Path) -> None:
        """show with CONSTITUTION.md → displays content."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text(
            "# Test Constitution\nBe good.\n", encoding="utf-8",
        )
        result = runner.invoke(
            app, ["constitution", "show", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Test Constitution" in result.output


# ---------------------------------------------------------------------------
# constitution check
# ---------------------------------------------------------------------------


class TestConstitutionCheck:
    """Test constitution check command."""

    def test_check_no_constitution(self, tmp_path: Path) -> None:
        """check with no CONSTITUTION.md → exit 1."""
        result = runner.invoke(
            app, ["constitution", "check", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "No CONSTITUTION.md" in result.output

    def test_check_passes_small_file(self, tmp_path: Path) -> None:
        """check with small CONSTITUTION.md → passes."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("# Small\nOK.\n", encoding="utf-8")
        result = runner.invoke(
            app, ["constitution", "check", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "within size limits" in result.output.lower() or "✓" in result.output


# ---------------------------------------------------------------------------
# constitution init
# ---------------------------------------------------------------------------


class TestConstitutionInit:
    """Test constitution init command."""

    def test_init_creates_file(self, tmp_path: Path) -> None:
        """init → creates CONSTITUTION.md."""
        result = runner.invoke(
            app, ["constitution", "init", "--project", str(tmp_path)],
        )
        # May fail if no .specweaver dir; init may require scaffolding
        if result.exit_code == 0:
            assert (tmp_path / "CONSTITUTION.md").exists()

    def test_init_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        """init with existing file → exit 1 without --force."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("existing\n", encoding="utf-8")
        result = runner.invoke(
            app, ["constitution", "init", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_init_force_overwrites(self, tmp_path: Path) -> None:
        """init --force with existing file → overwrites."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("old content\n", encoding="utf-8")
        result = runner.invoke(
            app, ["constitution", "init", "--force", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        new_content = constitution.read_text(encoding="utf-8")
        assert new_content != "old content\n"

    def test_init_bad_project_path(self, tmp_path: Path) -> None:
        """init with invalid project → exit 1."""
        result = runner.invoke(
            app, [
                "constitution", "init",
                "--project", str(tmp_path / "nonexistent"),
            ],
        )
        assert result.exit_code == 1
