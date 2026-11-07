# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A new `specweaver.db` names every table and index after its bounded context.

Proves: TECH-005 FR-1
Proves: TECH-005 FR-2
Proves: TECH-005 FR-6

Until TECH-090 these FRs were cited by a test of an Alembic script that never ran on a real file.
This one reads the file the product makes.

| Bucket | Case |
|---|---|
| Happy | the workspace and flow tables carry their prefix |
| Boundary | the artifact-event indexes carry the new table's name |
| Hostile | none of the old unprefixed names is created |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

if TYPE_CHECKING:
    from pathlib import Path


def _names(path: Path, kind: str) -> set[str]:
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,))
        return {row[0] for row in rows}


def test_the_workspace_and_flow_tables_carry_their_prefix(tmp_path: Path) -> None:
    bootstrap_database(str(tmp_path / "specweaver.db"))

    tables = _names(tmp_path / "specweaver.db", "table")

    assert {
        "workspace_projects",
        "workspace_active_state",
        "workspace_project_standards",
        "flow_artifact_events",
    } <= tables


def test_the_artifact_event_indexes_carry_the_new_name(tmp_path: Path) -> None:
    bootstrap_database(str(tmp_path / "specweaver.db"))

    indexes = _names(tmp_path / "specweaver.db", "index")

    assert {
        "ix_flow_artifact_events_artifact_id",
        "ix_flow_artifact_events_parent_id",
    } <= indexes
    assert not {"idx_lineage_artifact", "idx_lineage_parent"} & indexes


def test_no_old_unprefixed_name_is_created(tmp_path: Path) -> None:
    bootstrap_database(str(tmp_path / "specweaver.db"))

    tables = _names(tmp_path / "specweaver.db", "table")

    assert not {"projects", "active_state", "project_standards", "artifact_events"} & tables
