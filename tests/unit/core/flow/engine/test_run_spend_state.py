# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run keeps its spend brake's totals in the state store.

Proves: B-FLOW-05 FR-8

| Bucket | Case |
|---|---|
| Happy | a run's spend state is saved and loaded back unchanged |
| Boundary | a run that never called a model has an empty spend state |
| Degradation | a version-3 state database gains the column and its old runs load empty |
| Hostile | not applicable — the state comes only from the brake, never from input |
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from specweaver.core.flow.engine.state import PipelineRun, RunStatus
from specweaver.core.flow.engine.store import StateStore

if TYPE_CHECKING:
    from pathlib import Path

_STATE = {
    "spent": {"brake.hosted_spend_per_run": 9.5},
    "limits": {"brake.hosted_spend_per_run": 20.0},
}


def _run(**fields) -> PipelineRun:
    return PipelineRun(
        run_id=str(uuid.uuid4()),
        pipeline_name="p",
        project_name="proj",
        spec_path="specs/a_spec.md",
        status=RunStatus.PARKED,
        started_at="2026-10-07T10:00:00Z",
        updated_at="2026-10-07T10:00:00Z",
        **fields,
    )


def test_a_runs_spend_state_survives_save_and_load(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run = _run(spend_state=_STATE)

    store.save_run(run)

    assert store.load_run(run.run_id).spend_state == _STATE


def test_a_run_without_model_calls_has_an_empty_spend_state(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    run = _run()

    store.save_run(run)

    assert store.load_run(run.run_id).spend_state == {}


def test_a_version_3_database_gains_the_column_and_old_runs_load_empty(tmp_path: Path) -> None:
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            "CREATE TABLE flow_pipeline_runs (run_id TEXT PRIMARY KEY, parent_run_id TEXT,"
            " pipeline_name TEXT, project_name TEXT, spec_path TEXT, status TEXT,"
            " current_step INTEGER, step_records TEXT, started_at TEXT, updated_at TEXT);"
            "CREATE TABLE flow_state_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);"
            "INSERT INTO flow_state_schema_version VALUES (3, '2026-01-01T00:00:00Z');"
            "INSERT INTO flow_pipeline_runs VALUES ('old', NULL, 'p', 'proj', 's', 'parked', 0,"
            " '[]', '2026-01-01', '2026-01-01');"
        )

    store = StateStore(db)

    assert store.load_run("old").spend_state == {}
    with store.connect() as conn:
        version = conn.execute("SELECT MAX(version) FROM flow_state_schema_version").fetchone()[0]
    assert version == 4
