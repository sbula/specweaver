# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every target has a DAL: its nearest `context.yaml`, else its project's default (DAL_C).

Proves: B-FLOW-07 FR-3, B-FLOW-07 FR-10

The seam: the run (`core.flow`) reads the project's default DAL from the project store
(`workspace`), by the project's root path, and validation reads it the same way.

| Bucket | Case |
|---|---|
| Happy | a project with no DAL in any `context.yaml` → the run's DAL is the project's default |
| Boundary | a `context.yaml` DAL wins over the project's default |
| Degradation | a folder no project is registered at → no DAL, as before |
| Hostile | a project registered under another name than its folder is still found |
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.isolation import seed_dal_level
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.workspace.store import default_dal_at
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def db(tmp_path: Path) -> Database:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path)


def _project(tmp_path: Path, db: Database, name: str = "not-the-folder-name") -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    register_test_project(db, name, str(root))
    return root


def _context(root: Path, db: Database) -> RunContext:
    return RunContext(project_path=root, spec_path=root / "a_spec.md", db=db)


def test_a_run_without_a_declared_dal_takes_the_projects_default(
    tmp_path: Path, db: Database
) -> None:
    root = _project(tmp_path, db)

    assert seed_dal_level(_context(root, db)) is DALLevel.DAL_C


def test_a_declared_dal_wins(tmp_path: Path, db: Database) -> None:
    root = _project(tmp_path, db)
    (root / "context.yaml").write_text(
        "name: proj\nlevel: system\noperational:\n  dal_level: DAL_A\n"
    )

    assert seed_dal_level(_context(root, db)) is DALLevel.DAL_A


def test_a_folder_outside_every_project_gets_dal_c(tmp_path: Path, db: Database) -> None:
    """Agreed 2026-10-11: no project means the same default a new project gets."""
    loose = tmp_path / "loose"
    loose.mkdir()

    assert default_dal_at(db, loose) is None
    assert seed_dal_level(_context(loose, db)) is DALLevel.DAL_C


def test_validation_uses_the_same_dal(tmp_path: Path, db: Database) -> None:
    from specweaver.core.flow.handlers.validation import target_dal

    root = _project(tmp_path, db)

    assert target_dal(_context(root, db), root / "a_spec.md") is DALLevel.DAL_C


def _drop_new_columns(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("DROP INDEX ix_llm_usage_history")
        for column in ("server", "dal_level", "step_name"):
            conn.execute(f"ALTER TABLE llm_usage_log DROP COLUMN {column}")
        conn.execute("UPDATE workspace_projects SET default_dal = 'DAL_A'")
        conn.execute("DROP TABLE specweaver_migrations")


def test_an_old_database_moves_to_dal_c_once(tmp_path: Path, db: Database) -> None:
    _project(tmp_path, db)
    path = tmp_path / "specweaver.db"
    _drop_new_columns(path)

    bootstrap_database(str(path))
    with sqlite3.connect(path) as conn:
        moved = conn.execute("SELECT default_dal FROM workspace_projects").fetchall()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(llm_usage_log)")}
        conn.execute("UPDATE workspace_projects SET default_dal = 'DAL_A'")
    bootstrap_database(str(path))
    with sqlite3.connect(path) as conn:
        kept = conn.execute("SELECT default_dal FROM workspace_projects").fetchall()

    assert moved == [("DAL_C",)]
    assert {"server", "dal_level", "step_name"} <= columns
    assert kept == [("DAL_A",)], "a DAL set on purpose was undone by a later start"


def test_a_stored_value_that_is_not_a_dal_counts_as_none(tmp_path: Path, db: Database) -> None:
    root = _project(tmp_path, db)
    with sqlite3.connect(tmp_path / "specweaver.db") as conn:
        conn.execute("UPDATE workspace_projects SET default_dal = 'NOT_A_DAL'")

    assert default_dal_at(db, root) is None


def test_a_rebuilt_old_table_still_moves_to_dal_c(tmp_path: Path, db: Database) -> None:
    _project(tmp_path, db)
    path = tmp_path / "specweaver.db"
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE llm_usage_log")
        conn.execute(
            "CREATE TABLE llm_usage_log (id INTEGER PRIMARY KEY, timestamp VARCHAR NOT NULL, "
            "project_name VARCHAR NOT NULL, task_type VARCHAR NOT NULL, model VARCHAR NOT NULL, "
            "provider VARCHAR NOT NULL, prompt_tokens INTEGER NOT NULL, "
            "completion_tokens INTEGER NOT NULL, total_tokens INTEGER NOT NULL, "
            "estimated_cost FLOAT NOT NULL, duration_ms INTEGER NOT NULL, run_id VARCHAR)"
        )
        conn.execute("DROP TABLE IF EXISTS specweaver_migrations")
        conn.execute("UPDATE workspace_projects SET default_dal = 'DAL_A'")

    bootstrap_database(str(path))

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT default_dal FROM workspace_projects").fetchall() == [("DAL_C",)]
