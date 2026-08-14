# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rule results persist queryably, one row per finding. `INT-US-04` SF-01 CB-2.

`INT-US-04` C1 claims the DB *"statefully persists Validation Engine outputs"*. It does not: rule
results ride inside `flow_pipeline_runs.step_records` as one opaque JSON blob, with no `rule_id`,
`status` or `severity` column anywhere. `flow_validation_results` is that surface.

**One row per FINDING, not per rule** (plan D-11). A per-rule grain leaves each rule's `Finding`
list nowhere to go but a JSON column — the blob `CB-1` had just rescued those fields from, one layer
down, inside a table whose entire claim is that it is queryable.

**A rule with no findings still gets a row**, `finding_index` and the four finding columns `NULL`.
Otherwise passing rules vanish and *"did S01 run, and did it pass?"* — the first question anyone
asks of validation history — cannot be answered.

Adding the table needs **no data migration**: `_ensure_schema` runs `executescript` on every
construction and every statement is `CREATE TABLE IF NOT EXISTS`, so an existing v2 database gains
it on next open. The version row moves to 3 so the recorded version reflects reality.

Proves: INT-US-04 FR-2.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepStatus,
)
from specweaver.core.flow.engine.store import StateStore

if TYPE_CHECKING:
    from pathlib import Path


def _rule_dict(rule_id: str, *findings: dict, status: str = "fail") -> dict:
    """One entry of `StepResult.output["results"]`, as `_rule_payload` builds it."""
    return {
        "rule_id": rule_id,
        "status": status,
        "message": f"{rule_id} says so",
        "findings": list(findings),
    }


def _finding(message: str, line: int | None = 1, severity: str = "error", suggestion=None) -> dict:
    return {"message": message, "line": line, "severity": severity, "suggestion": suggestion}


@pytest.fixture()
def store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "pipeline_state.db")


@pytest.fixture()
def run(store: StateStore) -> PipelineRun:
    """A persisted run — the foreign key target every validation row needs."""
    pipeline_run = PipelineRun(
        run_id=str(uuid.uuid4()),
        pipeline_name="validation_spec_default",
        project_name="proj",
        spec_path="specs/test_spec.md",
        status=RunStatus.RUNNING,
        current_step=0,
        step_records=[StepRecord(step_name="validate_spec", status=StepStatus.PENDING)],
        started_at="2026-08-14T10:00:00Z",
        updated_at="2026-08-14T10:00:00Z",
    )
    store.save_run(pipeline_run)
    return pipeline_run


class TestStateStoreValidationSchema:
    """`StateStore` — the table, its index, and the version bump."""

    def test_the_table_and_its_index_exist_on_a_fresh_db(self, store: StateStore) -> None:
        with store.connect() as conn:
            tables = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            indexes = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            }
        assert "flow_validation_results" in tables
        assert any("validation_results" in i and "run" in i for i in indexes), (
            f"no run_id index — every query is by run_id (RB-7): {sorted(indexes)}"
        )

    def test_an_existing_v2_database_gains_the_table_without_migration(
        self, tmp_path: Path
    ) -> None:
        """[Boundary] `CREATE TABLE IF NOT EXISTS` runs on every construction (plan R-8).

        Simulates the real upgrade path: a database created before this table existed, reopened.
        """
        db = tmp_path / "old.db"
        with sqlite3.connect(db) as conn:
            conn.executescript(
                "CREATE TABLE flow_pipeline_runs (run_id TEXT PRIMARY KEY, parent_run_id TEXT,"
                " pipeline_name TEXT, project_name TEXT, spec_path TEXT, status TEXT,"
                " current_step INTEGER, step_records TEXT, started_at TEXT, updated_at TEXT);"
                "CREATE TABLE flow_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,"
                " timestamp TEXT, event TEXT, step_name TEXT, details TEXT);"
                "CREATE TABLE flow_state_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);"
                "INSERT INTO flow_state_schema_version VALUES (2, '2026-01-01T00:00:00Z');"
            )

        reopened = StateStore(db)

        with reopened.connect() as conn:
            tables = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            version = conn.execute("SELECT MAX(version) FROM flow_state_schema_version").fetchone()[
                0
            ]
        assert "flow_validation_results" in tables
        assert version == 3, "the recorded version must reflect the schema actually present"


class TestStateStoreSaveValidationResults:
    """`save_validation_results` / `get_validation_results` — the queryable surface."""

    def test_one_row_per_finding_with_every_column_intact(
        self, store: StateStore, run: PipelineRun
    ) -> None:
        """[Happy] Two rules, three findings between them → three rows, fully populated."""
        store.save_validation_results(
            run.run_id,
            "validate_spec",
            attempt=1,
            results=[
                _rule_dict(
                    "S01",
                    _finding("first", 12, "error", "split it"),
                    _finding("second", 99, "warning"),
                ),
                _rule_dict("S02", _finding("third", None, "info")),
            ],
        )

        rows = store.get_validation_results(run.run_id)
        assert len(rows) == 3
        assert [r["rule_id"] for r in rows] == ["S01", "S01", "S02"]
        assert [r["finding_index"] for r in rows] == [0, 1, 0]
        assert [r["message"] for r in rows] == ["first", "second", "third"]
        assert [r["line"] for r in rows] == [12, 99, None]
        assert [r["severity"] for r in rows] == ["error", "warning", "info"]
        assert rows[0]["suggestion"] == "split it"
        assert rows[1]["suggestion"] is None
        assert all(r["step_name"] == "validate_spec" and r["attempt"] == 1 for r in rows)
        assert rows[0]["rule_status"] == "fail"

    def test_a_rule_with_no_findings_still_gets_a_row(
        self, store: StateStore, run: PipelineRun
    ) -> None:
        """[Boundary] Otherwise a passing rule vanishes and 'did S01 pass?' is unanswerable."""
        store.save_validation_results(
            run.run_id, "validate_spec", attempt=1, results=[_rule_dict("S03", status="pass")]
        )

        rows = store.get_validation_results(run.run_id)
        assert len(rows) == 1
        assert rows[0]["rule_id"] == "S03"
        assert rows[0]["rule_status"] == "pass"
        assert rows[0]["finding_index"] is None
        assert rows[0]["message"] is None

    def test_no_results_writes_nothing_and_does_not_crash(
        self, store: StateStore, run: PipelineRun
    ) -> None:
        """[Boundary] A validate step can legitimately produce zero rules."""
        store.save_validation_results(run.run_id, "validate_spec", attempt=1, results=[])
        assert store.get_validation_results(run.run_id) == []

    def test_a_second_attempt_appends_and_both_stay_readable(
        self, store: StateStore, run: PipelineRun
    ) -> None:
        """[Boundary] Append-only (D-2). Overwriting would discard the earlier attempt's failures —
        the information `TECH-021` was filed to stop losing."""
        store.save_validation_results(
            run.run_id,
            "validate_spec",
            attempt=1,
            results=[_rule_dict("S01", _finding("round one"))],
        )
        store.save_validation_results(
            run.run_id,
            "validate_spec",
            attempt=2,
            results=[_rule_dict("S01", status="pass")],
        )

        rows = store.get_validation_results(run.run_id)
        assert [r["attempt"] for r in rows] == [1, 2]
        assert [r["rule_status"] for r in rows] == ["fail", "pass"]
        assert rows[0]["message"] == "round one"

    def test_the_step_filter_narrows_to_one_step(self, store: StateStore, run: PipelineRun) -> None:
        """[Boundary] `step=` is the only narrowing this reader offers; it must actually narrow."""
        store.save_validation_results(
            run.run_id, "validate_spec", attempt=1, results=[_rule_dict("S01", _finding("spec"))]
        )
        store.save_validation_results(
            run.run_id, "validate_code", attempt=1, results=[_rule_dict("C01", _finding("code"))]
        )

        assert len(store.get_validation_results(run.run_id)) == 2
        only_code = store.get_validation_results(run.run_id, step="validate_code")
        assert [r["rule_id"] for r in only_code] == ["C01"]

    def test_an_unknown_run_id_returns_nothing(self, store: StateStore) -> None:
        """[Boundary] A reader for a run that never wrote must be empty, not an error."""
        assert store.get_validation_results("no-such-run") == []

    def test_a_hostile_message_round_trips_through_sqlite(
        self, store: StateStore, run: PipelineRun
    ) -> None:
        """[Hostile] Finding messages quote spec content, which is user input."""
        nasty = 'he said "no"\n\tand\\or \'); DROP TABLE flow_validation_results; --' + (
            "A" * 10_000
        )
        store.save_validation_results(
            run.run_id, "validate_spec", attempt=1, results=[_rule_dict("S01", _finding(nasty))]
        )

        rows = store.get_validation_results(run.run_id)
        assert rows[0]["message"] == nasty
        with store.connect() as conn:
            still_there = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        assert "flow_validation_results" in still_there, "parameter binding must survive injection"

    def test_an_orphan_run_id_is_rejected_by_the_foreign_key(self, store: StateStore) -> None:
        """[Hostile] Rows must not outlive or precede their run. `connect()` sets foreign_keys=ON."""
        with pytest.raises(sqlite3.IntegrityError):
            store.save_validation_results(
                "never-persisted", "validate_spec", attempt=1, results=[_rule_dict("S01")]
            )
