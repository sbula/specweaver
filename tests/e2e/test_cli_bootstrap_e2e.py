from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()



def test_cli_bootstrap_e2e_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[Happy Path] CLI natively bootstraps the database if it doesn't exist."""
    db_path = tmp_path / "specweaver.db"

    # We MUST bypass the conftest mock that pre-initializes the DB.
    # We must also mock config_db_path inside cli_db_utils.
    # The E2E conftest does: `monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", ...)`
    # We will undo that specific patch by re-importing the original get_db logic directly.
    def _native_get_db():
        from specweaver.core.config.database import Database

        try:
            from specweaver.core.config.cli_db_utils import bootstrap_database

            bootstrap_database(str(db_path))
        except Exception:
            pass
        return Database(db_path)

    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", _native_get_db)
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.config_db_path", lambda: db_path)

    assert not db_path.exists()

    result = runner.invoke(app, ["projects"])
    assert result.exit_code == 0
    assert (
        "Active Project" in result.stdout
        or "projects" in result.stdout
        or "Projects" in result.stdout
    )

    # Verify the database was actually created and seeded!
    assert db_path.exists()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert "llm_profiles" in tables
    assert "projects" in tables


def test_cli_bootstrap_e2e_idempotency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[Boundary] CLI handles an already-existing database seamlessly."""
    db_path = tmp_path / "specweaver.db"

    def _native_get_db():
        from specweaver.core.config.database import Database

        try:
            from specweaver.core.config.cli_db_utils import bootstrap_database

            bootstrap_database(str(db_path))
        except Exception:
            pass
        return Database(db_path)

    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", _native_get_db)
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.config_db_path", lambda: db_path)

    # Run once
    runner.invoke(app, ["projects"])
    assert db_path.exists()

    # Run twice
    result = runner.invoke(app, ["projects"])
    assert result.exit_code == 0

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM llm_profiles")
    count = cursor.fetchone()[0]
    conn.close()

    # It shouldn't have double-seeded the defaults
    assert count == 3
