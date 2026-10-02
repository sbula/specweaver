# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

if TYPE_CHECKING:
    from pathlib import Path


def test_bootstrap_database_happy_path(tmp_path: Path) -> None:
    """bootstrap_database should be idempotent and create seed data."""
    db_path = tmp_path / "test.db"

    # Run twice to test idempotence
    bootstrap_database(str(db_path))
    bootstrap_database(str(db_path))

    # Verify tables created using standard sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "llm_usage_log" in tables
    assert "llm_profiles" not in tables  # LLM settings live in the settings files
    assert "workspace_projects" in tables
    assert "workspace_active_state" in tables
    conn.close()


def test_bootstrap_database_degradation_readonly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[Degradation] Bootstrap raises clear error if path is read-only."""
    db_path = tmp_path / "readonly_dir" / "test.db"

    # We mock Path.mkdir to simulate a PermissionError without needing OS-specific chmod
    def mock_mkdir(self, *args, **kwargs):
        raise PermissionError(f"Permission denied: {self}")

    monkeypatch.setattr("pathlib.Path.mkdir", mock_mkdir)

    with pytest.raises(PermissionError, match="Permission denied"):
        bootstrap_database(str(db_path))


def test_bootstrap_database_hostile_invalid_path(tmp_path: Path) -> None:
    """[Hostile] Bootstrap handles invalid paths (like directories) safely."""
    # Create a directory where the file should be
    db_path = tmp_path / "im_a_dir"
    db_path.mkdir()

    # SQLAlchemy will throw its own OperationalError
    import sqlalchemy.exc

    with pytest.raises(sqlalchemy.exc.OperationalError):
        bootstrap_database(str(db_path))
