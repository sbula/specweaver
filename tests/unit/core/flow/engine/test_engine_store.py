# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for pipeline state store — SQLite persistence."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.engine.store import StateStore

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(
    *,
    run_id: str | None = None,
    parent_run_id: str | None = None,
    pipeline_name: str = "test_pipeline",
    project_name: str = "test_project",
    status: RunStatus = RunStatus.NOT_STARTED,
    step_names: list[str] | None = None,
) -> PipelineRun:
    if step_names is None:
        step_names = ["validate_spec", "review_spec"]
    return PipelineRun(
        run_id=run_id or str(uuid.uuid4()),
        parent_run_id=parent_run_id,
        pipeline_name=pipeline_name,
        project_name=project_name,
        spec_path="specs/test_spec.md",
        status=status,
        current_step=0,
        step_records=[StepRecord(step_name=name, status=StepStatus.PENDING) for name in step_names],
        started_at="2026-03-14T18:00:00Z",
        updated_at="2026-03-14T18:00:00Z",
    )


@pytest.fixture()
def store(tmp_path: Path) -> StateStore:
    """Create a StateStore with a temp DB."""
    return StateStore(tmp_path / "pipeline_state.db")


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------


class TestStoreSchema:
    """Tests for store initialization and schema."""

    def test_creates_db_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        assert not db_path.exists()
        StateStore(db_path)
        assert db_path.exists()

    def test_idempotent_creation(self, tmp_path: Path) -> None:
        """A second StateStore over the same file reuses the schema rather than clobbering it.

        Until 2026-07-26 this only ran the constructor twice with a "should not raise" comment,
        which is a weaker claim than the test's name: a second constructor that silently dropped
        and recreated the schema — losing every persisted run — would have passed.
        """
        db_path = tmp_path / "test.db"
        first = StateStore(db_path)
        conn = first.connect()
        before = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()

        second = StateStore(db_path)

        conn = second.connect()
        assert conn.execute("PRAGMA user_version").fetchone()[0] == before
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert tables, "the second construction left no tables behind"

    def test_wal_mode(self, store: StateStore) -> None:
        conn = store.connect()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_migration_v1_to_v2(self, tmp_path: Path) -> None:
        """Test that a V1 schema database is successfully migrated to V2 (parent_run_id added)."""
        db_path = tmp_path / "legacy.db"
        import sqlite3

        # Create a raw V1 database
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE state_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO state_schema_version (version, applied_at) VALUES (1, '2026-03-14T18:00:00Z')"
        )
        conn.execute(
            """
            CREATE TABLE pipeline_runs (
                run_id TEXT PRIMARY KEY,
                pipeline_name TEXT NOT NULL,
                project_name TEXT NOT NULL,
                spec_path TEXT NOT NULL,
                status TEXT NOT NULL,
                current_step INTEGER NOT NULL,
                step_records TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

        # Instantiating the store should trigger migration
        _ = StateStore(db_path)

        # Verify schema version was bumped. `INT-US-04` SF-01 CB-2 moved the current version to
        # 3 (it added `flow_validation_results`), so a v1 database now lands on 3 in one open:
        # the v1->v2 ALTER still runs, and v2->v3 needed no migration because the new table is
        # created by the `IF NOT EXISTS` script that runs on every construction.
        conn = sqlite3.connect(db_path)
        version = conn.execute("SELECT MAX(version) FROM flow_state_schema_version").fetchone()[0]
        assert version == 3

        # Verify parent_run_id column exists
        columns = [
            row[1] for row in conn.execute("PRAGMA table_info(flow_pipeline_runs)").fetchall()
        ]
        assert "parent_run_id" in columns
        conn.close()

    def test_migrates_legacy_table_names_from_v2_shape(self, tmp_path: Path) -> None:
        """TECH-005 FR-8: the more common real-world case — an installation already on the current
        V2 column shape (has `parent_run_id`), whose only gap is the pre-SF-3 unprefixed table
        names. All three tables' real row data must survive the rename exactly, and the schema
        version must NOT be spuriously re-migrated (it is already 2)."""
        db_path = tmp_path / "legacy_v2.db"
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE pipeline_runs (
                run_id        TEXT PRIMARY KEY,
                parent_run_id TEXT REFERENCES pipeline_runs(run_id),
                pipeline_name TEXT NOT NULL,
                project_name  TEXT NOT NULL,
                spec_path     TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'not_started',
                current_step  INTEGER NOT NULL DEFAULT 0,
                step_records  TEXT NOT NULL DEFAULT '[]',
                started_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );
            CREATE TABLE audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id    TEXT NOT NULL REFERENCES pipeline_runs(run_id),
                timestamp TEXT NOT NULL,
                event     TEXT NOT NULL,
                step_name TEXT,
                details   TEXT
            );
            CREATE TABLE state_schema_version (
                version    INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO state_schema_version (version, applied_at) VALUES (2, '2026-03-14T18:00:00Z')"
        )
        conn.execute(
            "INSERT INTO pipeline_runs (run_id, parent_run_id, pipeline_name, project_name, "
            "spec_path, status, current_step, step_records, started_at, updated_at) VALUES "
            "('run-legacy', NULL, 'p', 'proj', 'spec.md', 'completed', 1, '[]', "
            "'2026-03-14T18:00:00Z', '2026-03-14T18:00:00Z')"
        )
        conn.execute(
            "INSERT INTO audit_log (run_id, timestamp, event, step_name, details) VALUES "
            "('run-legacy', '2026-03-14T18:00:00Z', 'step_started', 'validate_spec', NULL)"
        )
        conn.commit()
        conn.close()

        store = StateStore(db_path)

        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not {"pipeline_runs", "audit_log", "state_schema_version"} & tables
        assert {"flow_pipeline_runs", "flow_audit_log", "flow_state_schema_version"} <= tables

        assert (
            conn.execute("SELECT MAX(version) FROM flow_state_schema_version").fetchone()[0] == 3
        )  # renamed, not re-migrated -- 3 is the current version since CB-2 added a table

        run_row = conn.execute(
            "SELECT run_id, pipeline_name, status FROM flow_pipeline_runs"
        ).fetchone()
        assert run_row == ("run-legacy", "p", "completed")

        audit_row = conn.execute("SELECT run_id, event FROM flow_audit_log").fetchone()
        assert audit_row == ("run-legacy", "step_started")
        conn.close()

        # The store's own public API must work normally against the migrated tables.
        loaded = store.load_run("run-legacy")
        assert loaded is not None
        assert loaded.status == RunStatus.COMPLETED

    def test_legacy_table_migration_preserves_foreign_key_integrity(self, tmp_path: Path) -> None:
        """TECH-005 FR-8/D-5: after migrating a legacy DB, the `audit_log.run_id ->
        pipeline_runs(run_id)` foreign key must still enforce against the renamed tables — an
        insert referencing a nonexistent run_id must still raise, not silently succeed."""
        db_path = tmp_path / "legacy_fk.db"
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE pipeline_runs (run_id TEXT PRIMARY KEY, pipeline_name TEXT NOT NULL, "
            "project_name TEXT NOT NULL, spec_path TEXT NOT NULL, status TEXT NOT NULL, "
            "current_step INTEGER NOT NULL, step_records TEXT NOT NULL, started_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id TEXT NOT NULL REFERENCES pipeline_runs(run_id), timestamp TEXT NOT NULL, "
            "event TEXT NOT NULL, step_name TEXT, details TEXT)"
        )
        conn.execute(
            "CREATE TABLE state_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO state_schema_version (version, applied_at) VALUES (2, '2026-03-14T18:00:00Z')"
        )
        conn.commit()
        conn.close()

        StateStore(db_path)

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO flow_audit_log (run_id, timestamp, event) "
                "VALUES ('does-not-exist', '2026-03-14T18:00:00Z', 'x')"
            )
        conn.close()

    def test_legacy_table_rename_is_idempotent_across_repeated_construction(
        self, tmp_path: Path
    ) -> None:
        """[Robustness] Two `StateStore` instances constructed back-to-back against the same
        legacy-named DB (simulating a second process racing at startup) must not raise on the
        second construction."""
        db_path = tmp_path / "legacy_race.db"
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE state_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        conn.commit()
        conn.close()

        StateStore(db_path)
        StateStore(db_path)  # must not raise

        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "flow_state_schema_version" in tables
        assert "state_schema_version" not in tables

    def test_resumes_a_half_migrated_state(self, tmp_path: Path) -> None:
        """[Robustness] `ALTER TABLE`/`CREATE TABLE` are DDL — each auto-commits independently in
        Python's `sqlite3` module, NOT as one atomic unit protected by `with conn:` (empirically
        verified). A process killed partway through `_rename_legacy_tables`'s three renames
        (`pipeline_runs`, `audit_log`, `state_schema_version`, in that order) leaves a genuinely
        half-migrated DB — the first two renamed, the third still old-named. The next construction
        must complete the interrupted migration, not error or silently skip the pending table."""
        db_path = tmp_path / "half_migrated.db"
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE flow_pipeline_runs (run_id TEXT PRIMARY KEY, parent_run_id TEXT, "
            "pipeline_name TEXT NOT NULL, project_name TEXT NOT NULL, spec_path TEXT NOT NULL, "
            "status TEXT NOT NULL, current_step INTEGER NOT NULL, step_records TEXT NOT NULL, "
            "started_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE flow_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT "
            "NULL, timestamp TEXT NOT NULL, event TEXT NOT NULL, step_name TEXT, details TEXT)"
        )
        # `state_schema_version` deliberately still old-named -- the interrupted table.
        conn.execute(
            "CREATE TABLE state_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO state_schema_version (version, applied_at) VALUES (2, '2026-03-14T18:00:00Z')"
        )
        conn.execute(
            "INSERT INTO flow_pipeline_runs (run_id, pipeline_name, project_name, spec_path, "
            "status, current_step, step_records, started_at, updated_at) VALUES "
            "('run-half', 'p', 'proj', 'spec.md', 'completed', 1, '[]', "
            "'2026-03-14T18:00:00Z', '2026-03-14T18:00:00Z')"
        )
        conn.commit()
        conn.close()

        store = StateStore(db_path)

        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "state_schema_version" not in tables
        assert "flow_state_schema_version" in tables

        loaded = store.load_run("run-half")
        assert loaded is not None
        assert loaded.status == RunStatus.COMPLETED

    def test_skips_rename_when_both_old_and_new_tables_exist(self, tmp_path: Path) -> None:
        """[Graceful degradation] A partially-migrated or corrupt DB with BOTH the old-named and
        new-named tables present must not raise and must not drop either — `repository.py` and
        `reservation.py` both have this test already (D-3); this store never did."""
        db_path = tmp_path / "legacy_both.db"
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE pipeline_runs (run_id TEXT PRIMARY KEY, pipeline_name TEXT NOT NULL, "
            "project_name TEXT NOT NULL, spec_path TEXT NOT NULL, status TEXT NOT NULL, "
            "current_step INTEGER NOT NULL, step_records TEXT NOT NULL, started_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE flow_pipeline_runs (run_id TEXT PRIMARY KEY, parent_run_id TEXT, "
            "pipeline_name TEXT NOT NULL, project_name TEXT NOT NULL, spec_path TEXT NOT NULL, "
            "status TEXT NOT NULL, current_step INTEGER NOT NULL, step_records TEXT NOT NULL, "
            "started_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.commit()
        conn.close()

        StateStore(db_path)  # must not raise

        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "pipeline_runs" in tables
        assert "flow_pipeline_runs" in tables

    def test_rename_swallows_concurrent_operational_error(self) -> None:
        """[Graceful degradation] `_rename_legacy_tables` must swallow `sqlite3.OperationalError`
        raised by `ALTER TABLE` itself when a RE-CHECK proves another process already finished the
        rename (`flow_pipeline_runs` now exists) — not just reach the same outcome via the
        membership-check skip already covered by the idempotent-construction test above."""
        import sqlite3
        from unittest import mock

        store = StateStore.__new__(StateStore)
        select_call_count = 0

        def fake_execute(sql, *_args, **_kwargs):
            nonlocal select_call_count
            stripped = sql.strip()
            if stripped.startswith("SELECT name FROM sqlite_master"):
                select_call_count += 1
                if select_call_count == 1:
                    return [("pipeline_runs",)]
                return [("pipeline_runs",), ("flow_pipeline_runs",)]
            if stripped.startswith("ALTER TABLE pipeline_runs RENAME"):
                raise sqlite3.OperationalError("no such table: pipeline_runs")
            raise AssertionError(f"unexpected SQL: {sql}")

        mock_conn = mock.MagicMock()
        mock_conn.execute.side_effect = fake_execute

        store._rename_legacy_tables(mock_conn)  # must not raise

        mock_conn.execute.assert_any_call("ALTER TABLE pipeline_runs RENAME TO flow_pipeline_runs")

    def test_rename_reraises_genuine_operational_errors(self) -> None:
        """[Hostile] A genuine `OperationalError` during the `ALTER TABLE` (disk I/O failure, lock
        contention, corruption) that is NOT explained by "another process already finished the
        rename" must propagate, not be silently swallowed. Swallowing it unconditionally would let
        `_ensure_schema()` proceed straight to `executescript(_STATE_SCHEMA_V2)`, creating an empty
        new `flow_pipeline_runs` table and silently orphaning the untouched old table's data."""
        import sqlite3
        from unittest import mock

        store = StateStore.__new__(StateStore)

        def fake_execute(sql, *_args, **_kwargs):
            stripped = sql.strip()
            if stripped.startswith("SELECT name FROM sqlite_master"):
                return [("pipeline_runs",)]  # flow_pipeline_runs never appears
            if stripped.startswith("ALTER TABLE pipeline_runs RENAME"):
                raise sqlite3.OperationalError("disk I/O error")
            raise AssertionError(f"unexpected SQL: {sql}")

        mock_conn = mock.MagicMock()
        mock_conn.execute.side_effect = fake_execute

        with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
            store._rename_legacy_tables(mock_conn)


# ---------------------------------------------------------------------------
# Save / load pipeline runs
# ---------------------------------------------------------------------------


class TestSaveLoadRun:
    """Tests for saving and loading pipeline runs."""

    def test_save_and_load(self, store: StateStore) -> None:
        parent_run = _make_run(run_id="parent-001")
        store.save_run(parent_run)

        run = _make_run(run_id="run-001", parent_run_id="parent-001")
        store.save_run(run)
        loaded = store.load_run("run-001")
        assert loaded is not None
        assert loaded.run_id == "run-001"
        assert loaded.parent_run_id == "parent-001"
        assert loaded.pipeline_name == "test_pipeline"
        assert loaded.status == RunStatus.NOT_STARTED
        assert len(loaded.step_records) == 2

    def test_load_nonexistent(self, store: StateStore) -> None:
        assert store.load_run("does-not-exist") is None

    def test_save_overwrites_existing(self, store: StateStore) -> None:
        run = _make_run(run_id="run-002")
        store.save_run(run)
        run.status = RunStatus.RUNNING
        run.current_step = 1
        store.save_run(run)
        loaded = store.load_run("run-002")
        assert loaded is not None
        assert loaded.status == RunStatus.RUNNING
        assert loaded.current_step == 1

    def test_save_with_step_results(self, store: StateStore) -> None:
        run = _make_run(run_id="run-003")
        result = StepResult(
            status=StepStatus.PASSED,
            output={"rule_count": 11, "all_passed": True},
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.complete_current_step(result)
        store.save_run(run)
        loaded = store.load_run("run-003")
        assert loaded is not None
        assert loaded.step_records[0].status == StepStatus.PASSED
        assert loaded.step_records[0].result is not None
        assert loaded.step_records[0].result.output["rule_count"] == 11

    def test_get_latest_run(self, store: StateStore) -> None:
        run1 = _make_run(run_id="run-old")
        run1.updated_at = "2026-03-14T17:00:00Z"
        store.save_run(run1)

        run2 = _make_run(run_id="run-new")
        run2.updated_at = "2026-03-14T19:00:00Z"
        store.save_run(run2)

        latest = store.get_latest_run("test_project", "test_pipeline")
        assert latest is not None
        assert latest.run_id == "run-new"

    def test_get_latest_run_no_match(self, store: StateStore) -> None:
        assert store.get_latest_run("no_project", "no_pipeline") is None

    def test_list_runs_with_limit(self, store: StateStore) -> None:
        """list_runs respects the limit parameter."""
        runs = [_make_run(run_id=f"run-{i}") for i in range(5)]
        for i, run in enumerate(runs):
            run.updated_at = f"2026-03-14T1{i}:00:00Z"
            store.save_run(run)

        # Default limit is 50, but we can list exactly 2
        listed = store.list_runs(limit=2)
        assert len(listed) == 2
        # Should be ordered by updated_at DESC (so run-4 and run-3)
        assert listed[0].run_id == "run-4"
        assert listed[1].run_id == "run-3"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    """Tests for the audit log."""

    def test_log_event(self, store: StateStore) -> None:
        run = _make_run(run_id="run-audit")
        store.save_run(run)
        store.log_event("run-audit", "step_started", step_name="validate_spec")
        store.log_event("run-audit", "step_completed", step_name="validate_spec")

        events = store.get_audit_log("run-audit")
        assert len(events) == 2
        assert events[0]["event"] == "step_started"
        assert events[1]["event"] == "step_completed"

    def test_log_event_with_details(self, store: StateStore) -> None:
        run = _make_run(run_id="run-detail")
        store.save_run(run)
        store.log_event(
            "run-detail",
            "run_parked",
            step_name="draft_spec",
            details="Waiting for user to run 'sw draft'",
        )
        events = store.get_audit_log("run-detail")
        assert len(events) == 1
        assert events[0]["details"] == "Waiting for user to run 'sw draft'"

    def test_audit_log_empty(self, store: StateStore) -> None:
        events = store.get_audit_log("nonexistent")
        assert events == []


# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------


class TestResume:
    """Tests for resume-from-checkpoint pattern."""

    def test_resume_parked_run(self, store: StateStore) -> None:
        run = _make_run(run_id="run-parked", status=RunStatus.RUNNING)
        park_result = StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={"message": "Please draft the spec"},
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:00Z",
        )
        run.park_current_step(park_result)
        store.save_run(run)

        loaded = store.load_run("run-parked")
        assert loaded is not None
        assert loaded.status == RunStatus.PARKED
        assert loaded.current_step == 0
        assert loaded.step_records[0].status == StepStatus.WAITING_FOR_INPUT

    def test_resume_failed_run(self, store: StateStore) -> None:
        run = _make_run(run_id="run-failed", status=RunStatus.RUNNING)
        fail_result = StepResult(
            status=StepStatus.FAILED,
            error_message="3 rules failed",
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.fail_current_step(fail_result)
        store.save_run(run)

        loaded = store.load_run("run-failed")
        assert loaded is not None
        assert loaded.status == RunStatus.FAILED
        assert loaded.current_step == 0

    def test_completed_run_persists(self, store: StateStore) -> None:
        run = _make_run(
            run_id="run-done",
            status=RunStatus.RUNNING,
            step_names=["s1"],
        )
        result = StepResult(
            status=StepStatus.PASSED,
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.complete_current_step(result)
        assert run.status == RunStatus.COMPLETED
        store.save_run(run)

        loaded = store.load_run("run-done")
        assert loaded is not None
        assert loaded.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


class TestStoreEdgeCases:
    """Additional edge case tests for the store."""

    def test_multiple_runs_different_pipelines(self, store: StateStore) -> None:
        """Multiple runs for same project, different pipelines."""
        run1 = _make_run(run_id="run-pipe1", pipeline_name="pipeline_a")
        run2 = _make_run(run_id="run-pipe2", pipeline_name="pipeline_b")
        store.save_run(run1)
        store.save_run(run2)

        latest_a = store.get_latest_run("test_project", "pipeline_a")
        latest_b = store.get_latest_run("test_project", "pipeline_b")
        assert latest_a is not None
        assert latest_a.run_id == "run-pipe1"
        assert latest_b is not None
        assert latest_b.run_id == "run-pipe2"

    def test_large_nested_output_roundtrip(self, store: StateStore) -> None:
        """Step result with deeply nested output serializes correctly."""
        run = _make_run(run_id="run-nested")
        result = StepResult(
            status=StepStatus.PASSED,
            output={
                "rules": [{"id": f"S{i:02d}", "status": "pass", "findings": []} for i in range(15)],
                "metadata": {"nested": {"deep": {"value": 42}}},
            },
            started_at="2026-03-14T18:00:00Z",
            completed_at="2026-03-14T18:00:01Z",
        )
        run.complete_current_step(result)
        store.save_run(run)

        loaded = store.load_run("run-nested")
        assert loaded is not None
        assert len(loaded.step_records[0].result.output["rules"]) == 15
        assert loaded.step_records[0].result.output["metadata"]["nested"]["deep"]["value"] == 42

    def test_schema_version_persisted(self, store: StateStore) -> None:
        """Schema version table should have exactly one entry."""
        conn = store.connect()
        row = conn.execute("SELECT MAX(version) FROM flow_state_schema_version").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 3, "current schema version -- CB-2 added flow_validation_results"

    def test_foreign_keys_enabled(self, store: StateStore) -> None:
        """Foreign key constraints should be active."""
        conn = store.connect()
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.close()
        assert fk == 1

    def test_store_load_run_corrupt_json(self, store: StateStore) -> None:
        """Loading a run with corrupt JSON in step_records handles safely."""
        run = _make_run(run_id="run-corrupt")
        store.save_run(run)

        # Manually corrupt the DB payload
        conn = store.connect()
        conn.execute(
            "UPDATE flow_pipeline_runs SET step_records = ? WHERE run_id = ?",
            ("{bad_json:", "run-corrupt"),
        )
        conn.commit()
        conn.close()

        import json

        try:
            loaded = store.load_run("run-corrupt")
            assert loaded is None
        except json.JSONDecodeError:
            pass
