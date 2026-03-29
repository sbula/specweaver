# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for CLI standards helper functions.

Covers:
- confirmed_by audit trail (item 8)
- _save_accepted_standards (item 9)
- _maybe_bootstrap_constitution (item 10)
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
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all standards tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


def _init_project(db, name: str, root_path: str) -> None:
    """Register and activate a project in the test DB."""
    runner.invoke(app, ["init", name, "--path", root_path])
    runner.invoke(app, ["use", name])


def _seed_standards(db, name: str, count: int = 2) -> None:
    """Insert sample standards into the DB."""
    db.save_standard(
        project_name=name,
        scope=".",
        language="python",
        category="naming",
        data={"style": "snake_case", "classes": "PascalCase"},
        confidence=0.85,
    )
    if count >= 2:
        db.save_standard(
            project_name=name,
            scope=".",
            language="python",
            category="docstrings",
            data={"style": "google"},
            confidence=0.72,
        )


# ---------------------------------------------------------------------------
# Item 8: confirmed_by audit trail
# ---------------------------------------------------------------------------


class TestConfirmedByAuditTrail:
    """Tests for confirmed_by='hitl' / None for scan with/without review."""

    def test_no_review_sets_confirmed_by_none(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """--no-review → saved standards have confirmed_by=None."""
        _init_project(_mock_db, "proj", str(tmp_path))
        py_file = tmp_path / "hello.py"
        py_file.write_text("def hello():\n    pass\n", encoding="utf-8")

        monkeypatch.setattr(
            "specweaver.standards.discovery.discover_files",
            lambda p: [py_file],
        )

        runner.invoke(app, ["standards", "scan", "--no-review"])

        standards = _mock_db.get_standards("proj")
        for s in standards:
            assert s.get("confirmed_by") is None


# ---------------------------------------------------------------------------
# Item 9: _save_accepted_standards
# ---------------------------------------------------------------------------


class TestSaveAcceptedStandards:
    """Unit tests for _save_accepted_standards helper."""

    def test_save_with_review_sets_hitl(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """no_review=False → confirmed_by='hitl'."""
        from specweaver.cli.standards import _save_accepted_standards
        from specweaver.standards.analyzer import CategoryResult

        _init_project(_mock_db, "proj", str(tmp_path))
        accepted = {
            ".": [
                CategoryResult(
                    category="naming",
                    dominant={"style": "snake_case"},
                    confidence=0.9,
                    sample_size=5,
                    language="python",
                )
            ],
        }
        _save_accepted_standards(_mock_db, "proj", accepted, no_review=False)
        standards = _mock_db.get_standards("proj")
        assert len(standards) >= 1
        assert standards[0]["confirmed_by"] == "hitl"

    def test_save_without_review_sets_none(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """no_review=True → confirmed_by=None."""
        from specweaver.cli.standards import _save_accepted_standards
        from specweaver.standards.analyzer import CategoryResult

        _init_project(_mock_db, "proj", str(tmp_path))
        accepted = {
            ".": [
                CategoryResult(
                    category="naming",
                    dominant={"style": "snake_case"},
                    confidence=0.9,
                    sample_size=5,
                    language="python",
                )
            ],
        }
        _save_accepted_standards(_mock_db, "proj", accepted, no_review=True)
        standards = _mock_db.get_standards("proj")
        assert len(standards) >= 1
        assert standards[0]["confirmed_by"] is None


# ---------------------------------------------------------------------------
# Item 10: _maybe_bootstrap_constitution
# ---------------------------------------------------------------------------


class TestMaybeBootstrapConstitution:
    """Unit tests for _maybe_bootstrap_constitution helper."""

    def _make_accepted(self):
        """Create a minimal accepted dict for testing."""
        from specweaver.standards.analyzer import CategoryResult

        return {
            ".": [
                CategoryResult(
                    category="naming",
                    dominant={"style": "snake_case"},
                    confidence=0.9,
                    sample_size=5,
                    language="python",
                )
            ],
        }

    def test_skips_when_user_edited_exists(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """User-edited CONSTITUTION.md → returns without action."""
        from specweaver.cli.standards import _maybe_bootstrap_constitution

        _init_project(_mock_db, "proj", str(tmp_path))
        # Create user-edited constitution
        (tmp_path / "CONSTITUTION.md").write_text(
            "# My Custom Constitution\nReal content.\n",
        )
        accepted = self._make_accepted()
        # Should return without error (no overwrite)
        _maybe_bootstrap_constitution(
            project_path=tmp_path,
            project_name="proj",
            db=_mock_db,
            accepted=accepted,
            no_review=False,
        )
        content = (tmp_path / "CONSTITUTION.md").read_text()
        assert "My Custom Constitution" in content

    def test_auto_mode_creates_constitution(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """mode='auto' → auto-creates CONSTITUTION.md."""
        from specweaver.cli.standards import _maybe_bootstrap_constitution

        _init_project(_mock_db, "proj", str(tmp_path))
        _mock_db.set_auto_bootstrap("proj", "auto")
        _seed_standards(_mock_db, "proj")
        accepted = self._make_accepted()

        _maybe_bootstrap_constitution(
            project_path=tmp_path,
            project_name="proj",
            db=_mock_db,
            accepted=accepted,
            no_review=False,
        )
        assert (tmp_path / "CONSTITUTION.md").exists()
        content = (tmp_path / "CONSTITUTION.md").read_text()
        assert "Auto-Discovered" in content

    def test_off_mode_prints_hint(
        self,
        tmp_path: Path,
        _mock_db,
        capsys,
    ) -> None:
        """mode='off' → prints hint about sw constitution bootstrap."""
        from specweaver.cli.standards import _maybe_bootstrap_constitution

        _init_project(_mock_db, "proj", str(tmp_path))
        _mock_db.set_auto_bootstrap("proj", "off")
        # _init_project scaffolds a starter CONSTITUTION.md; remove it
        (tmp_path / "CONSTITUTION.md").unlink(missing_ok=True)
        accepted = self._make_accepted()

        _maybe_bootstrap_constitution(
            project_path=tmp_path,
            project_name="proj",
            db=_mock_db,
            accepted=accepted,
            no_review=False,
        )
        # off mode should NOT create constitution — only print hint
        assert not (tmp_path / "CONSTITUTION.md").exists()

    def test_prompt_with_no_review_prints_hint(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """mode='prompt' + no_review → prints hint (no prompt)."""
        from specweaver.cli.standards import _maybe_bootstrap_constitution

        _init_project(_mock_db, "proj", str(tmp_path))
        _mock_db.set_auto_bootstrap("proj", "prompt")
        # _init_project scaffolds a starter CONSTITUTION.md; remove it
        (tmp_path / "CONSTITUTION.md").unlink(missing_ok=True)
        accepted = self._make_accepted()

        _maybe_bootstrap_constitution(
            project_path=tmp_path,
            project_name="proj",
            db=_mock_db,
            accepted=accepted,
            no_review=True,
        )
        # prompt + no_review should NOT create constitution — only print hint
        assert not (tmp_path / "CONSTITUTION.md").exists()

    def test_prompt_mode_user_accepts(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """mode='prompt' + user says yes → creates constitution."""
        from specweaver.cli.standards import _maybe_bootstrap_constitution

        _init_project(_mock_db, "proj", str(tmp_path))
        _mock_db.set_auto_bootstrap("proj", "prompt")
        _seed_standards(_mock_db, "proj")
        accepted = self._make_accepted()

        # Mock typer.confirm to return True
        monkeypatch.setattr("specweaver.cli.standards.typer.confirm", lambda *a, **kw: True)

        _maybe_bootstrap_constitution(
            project_path=tmp_path,
            project_name="proj",
            db=_mock_db,
            accepted=accepted,
            no_review=False,
        )
        assert (tmp_path / "CONSTITUTION.md").exists()
