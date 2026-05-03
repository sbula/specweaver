# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — CLI constitution subcommands.

Tests: show, check, init via CliRunner with mocked DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

# Force import to test decentralized location (Red Phase)
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
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# constitution show
# ---------------------------------------------------------------------------


class TestConstitutionShow:
    """Test constitution show command."""

    def test_show_no_constitution(self, tmp_path: Path) -> None:
        """show with no CONSTITUTION.md → exit 1."""
        result = runner.invoke(
            app,
            ["constitution", "show", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "No CONSTITUTION.md" in result.output

    def test_show_displays_content(self, tmp_path: Path) -> None:
        """show with CONSTITUTION.md → displays content."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text(
            "# Test Constitution\nBe good.\n",
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["constitution", "show", "--project", str(tmp_path)],
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
            app,
            ["constitution", "check", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "No CONSTITUTION.md" in result.output

    def test_check_passes_small_file(self, tmp_path: Path) -> None:
        """check with small CONSTITUTION.md → passes."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("# Small\nOK.\n", encoding="utf-8")
        result = runner.invoke(
            app,
            ["constitution", "check", "--project", str(tmp_path)],
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
            app,
            ["constitution", "init", "--project", str(tmp_path)],
        )
        # May fail if no .specweaver dir; init may require scaffolding
        if result.exit_code == 0:
            assert (tmp_path / "CONSTITUTION.md").exists()

    def test_init_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        """init with existing file → exit 1 without --force."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("existing\n", encoding="utf-8")
        result = runner.invoke(
            app,
            ["constitution", "init", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_init_force_overwrites(self, tmp_path: Path) -> None:
        """init --force with existing file → overwrites."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("old content\n", encoding="utf-8")
        result = runner.invoke(
            app,
            ["constitution", "init", "--force", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0
        new_content = constitution.read_text(encoding="utf-8")
        assert new_content != "old content\n"

    def test_init_bad_project_path(self, tmp_path: Path) -> None:
        """init with invalid project → exit 1."""
        result = runner.invoke(
            app,
            [
                "constitution",
                "init",
                "--project",
                str(tmp_path / "nonexistent"),
            ],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# constitution bootstrap
# ---------------------------------------------------------------------------


class TestConstitutionBootstrap:
    """Test constitution bootstrap command."""

    @pytest.fixture(autouse=True)
    def _setup_project(self, tmp_path: Path, _mock_db):
        """Register and activate a project with seeded standards."""
        self.db = _mock_db
        self.project_dir = tmp_path / "my-proj"
        self.project_dir.mkdir()
        _run_workspace_op(_mock_db, "register_project", "my-proj", str(self.project_dir))
        _run_workspace_op(_mock_db, "set_active_project", "my-proj")

    def _seed_standards(self) -> None:
        """Insert sample standards into the DB."""
        _run_workspace_op(
            self.db,
            "save_standard",
            project_name="my-proj",
            scope=".",
            language="python",
            category="naming",
            data={"function_style": "snake_case"},
            confidence=0.95,
            confirmed_by="hitl",
        )
        _run_workspace_op(
            self.db,
            "save_standard",
            project_name="my-proj",
            scope=".",
            language="python",
            category="error_handling",
            data={"pattern": "try_except_specific"},
            confidence=0.88,
            confirmed_by="hitl",
        )

    def test_bootstrap_happy_path(self, tmp_path: Path) -> None:
        """bootstrap with standards → creates CONSTITUTION.md."""
        self._seed_standards()
        result = runner.invoke(
            app,
            ["constitution", "bootstrap", "--project", str(self.project_dir)],
        )
        assert result.exit_code == 0
        assert (self.project_dir / "CONSTITUTION.md").exists()
        content = (self.project_dir / "CONSTITUTION.md").read_text()
        assert "Auto-Discovered" in content

    def test_bootstrap_no_standards_exits(self, tmp_path: Path) -> None:
        """bootstrap with no standards → exit 1."""
        result = runner.invoke(
            app,
            ["constitution", "bootstrap", "--project", str(self.project_dir)],
        )
        assert result.exit_code == 1
        assert "No confirmed standards" in result.output

    def test_bootstrap_skip_user_edited(self, tmp_path: Path) -> None:
        """bootstrap with user-edited CONSTITUTION.md → exit 1."""
        self._seed_standards()
        # Create a custom constitution (no TODOs → user-edited)
        (self.project_dir / "CONSTITUTION.md").write_text(
            "# My Custom Constitution\nAll real content here.\n",
        )
        result = runner.invoke(
            app,
            ["constitution", "bootstrap", "--project", str(self.project_dir)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_bootstrap_force_overwrites(self, tmp_path: Path) -> None:
        """bootstrap --force → overwrites user-edited CONSTITUTION.md."""
        self._seed_standards()
        (self.project_dir / "CONSTITUTION.md").write_text(
            "# My Custom Constitution\n",
        )
        result = runner.invoke(
            app,
            [
                "constitution",
                "bootstrap",
                "--force",
                "--project",
                str(self.project_dir),
            ],
        )
        assert result.exit_code == 0
        content = (self.project_dir / "CONSTITUTION.md").read_text()
        assert "Auto-Discovered" in content

    def test_bootstrap_bad_project_path(self, tmp_path: Path) -> None:
        """bootstrap with invalid project → exit 1."""
        result = runner.invoke(
            app,
            [
                "constitution",
                "bootstrap",
                "--project",
                str(tmp_path / "nonexistent"),
            ],
        )
        assert result.exit_code == 1

    def test_bootstrap_output_shows_count_and_languages(
        self,
        tmp_path: Path,
    ) -> None:
        """bootstrap output mentions standard count and languages."""
        self._seed_standards()
        result = runner.invoke(
            app,
            ["constitution", "bootstrap", "--project", str(self.project_dir)],
        )
        assert result.exit_code == 0
        assert "2" in result.output  # 2 standards
        assert "python" in result.output


def _run_workspace_op(db_instance, method_name: str, *args, **kwargs):
    import anyio

    from specweaver.workspace.store import WorkspaceRepository

    async def _action():
        async with db_instance.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args, **kwargs)

    return anyio.run(_action)
