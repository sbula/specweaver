# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pipeline state store — SQLite persistence for pipeline runs.

Stores runtime data (pipeline runs, step results, audit log) in a separate
``pipeline_state.db`` file, keeping it isolated from the configuration
database (``specweaver.db``).

Uses WAL mode for concurrent read/write and ``CREATE TABLE IF NOT EXISTS``
for idempotent schema creation.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from specweaver.commons import json
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)

logger = logging.getLogger(__name__)

_STATE_SCHEMA_V2 = """\
CREATE TABLE IF NOT EXISTS flow_pipeline_runs (
    run_id        TEXT PRIMARY KEY,
    parent_run_id TEXT REFERENCES flow_pipeline_runs(run_id),
    pipeline_name TEXT NOT NULL,
    project_name  TEXT NOT NULL,
    spec_path     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'not_started',
    current_step  INTEGER NOT NULL DEFAULT 0,
    step_records  TEXT NOT NULL DEFAULT '[]',
    started_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flow_audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT NOT NULL REFERENCES flow_pipeline_runs(run_id),
    timestamp TEXT NOT NULL,
    event     TEXT NOT NULL,
    step_name TEXT,
    details   TEXT
);

CREATE TABLE IF NOT EXISTS flow_state_schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

# TECH-005 FR-8: pre-SF-3 installations used these unprefixed names. Order matters — rename
# `flow_pipeline_runs`' predecessor before `flow_audit_log`'s (which references it), and
# `state_schema_version` last since `_ensure_schema` reads it immediately afterward to decide
# whether this is a fresh DB or one needing the v1->v2 column migration.
_LEGACY_TABLE_RENAMES = (
    ("pipeline_runs", "flow_pipeline_runs"),
    ("audit_log", "flow_audit_log"),
    ("state_schema_version", "flow_state_schema_version"),
)


class StateStore:
    """SQLite persistence for pipeline run state.

    Args:
        db_path: Path to the SQLite database file. Parent directories
            are created automatically.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def connect(self) -> sqlite3.Connection:
        """Return a new connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def _rename_legacy_tables(self, conn: sqlite3.Connection) -> None:
        """TECH-005 FR-8: migrate a pre-SF-3 installation's `pipeline_runs`/`audit_log`/
        `state_schema_version` tables to their `flow_`-prefixed equivalents in place, preserving
        all data. MUST run before the version-check logic below — that logic reads
        `flow_state_schema_version` to decide fresh-DB vs. needs-v1-to-v2-migration, and if the
        rename ran after, a real existing installation's data would be misread as a brand-new DB.

        Skips (does not raise) when a table's new name already exists alongside the old one —
        a partially-migrated or corrupt state must degrade safely. Also tolerates a concurrent
        second construction racing to rename the same table: an `OperationalError` from the
        `ALTER TABLE` is swallowed ONLY if a re-check proves the new name now exists (the race
        really did happen and finished elsewhere) — any other cause (disk I/O, lock contention,
        corruption) re-raises, since silently swallowing it would let `_ensure_schema()` proceed to
        `executescript(_STATE_SCHEMA_V2)` and orphan the untouched old table's data instead of
        surfacing a loud construction failure.
        """
        existing = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for old_name, new_name in _LEGACY_TABLE_RENAMES:
            if old_name not in existing or new_name in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
            except sqlite3.OperationalError:
                still_missing = new_name not in {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if still_missing:
                    raise

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist. Idempotent."""
        with self.connect() as conn:
            self._rename_legacy_tables(conn)
            conn.executescript(_STATE_SCHEMA_V2)

            existing = conn.execute(
                "SELECT COUNT(*) FROM flow_state_schema_version",
            ).fetchone()[0]
            if existing == 0:
                conn.execute(
                    "INSERT INTO flow_state_schema_version (version, applied_at) VALUES (?, ?)",
                    (2, _now_iso()),
                )
                logger.debug("StateStore: created schema v2 at '%s'", self._db_path)
            else:
                version = conn.execute(
                    "SELECT MAX(version) FROM flow_state_schema_version"
                ).fetchone()[0]
                if version == 1:
                    conn.execute(
                        "ALTER TABLE flow_pipeline_runs ADD COLUMN parent_run_id TEXT REFERENCES flow_pipeline_runs(run_id);"
                    )
                    conn.execute(
                        "INSERT INTO flow_state_schema_version (version, applied_at) VALUES (?, ?)",
                        (2, _now_iso()),
                    )
                    logger.debug("StateStore: migrated schema v1 -> v2 at '%s'", self._db_path)

    # ------------------------------------------------------------------
    # Pipeline runs
    # ------------------------------------------------------------------

    def save_run(self, run: PipelineRun) -> None:
        """Save or update a pipeline run.

        Uses UPSERT semantics — creates the row if it doesn't exist,
        replaces it if it does. Step records are serialized as JSON.
        """
        logger.debug(
            "StateStore.save_run: run_id=%s status=%s step=%d/%d",
            run.run_id,
            run.status.value,
            run.current_step,
            len(run.step_records),
        )
        records_json = json.dumps(
            [r.model_dump() for r in run.step_records],
            default=str,
        )
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO flow_pipeline_runs "
                "(run_id, parent_run_id, pipeline_name, project_name, spec_path, "
                "status, current_step, step_records, started_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.run_id,
                    run.parent_run_id,
                    run.pipeline_name,
                    run.project_name,
                    run.spec_path,
                    run.status.value,
                    run.current_step,
                    records_json,
                    run.started_at,
                    run.updated_at,
                ),
            )

    def load_run(self, run_id: str) -> PipelineRun | None:
        """Load a pipeline run by ID, or None if not found."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM flow_pipeline_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                logger.debug("StateStore.load_run: run_id=%s not found", run_id)
                return None
            logger.debug("StateStore.load_run: loaded run_id=%s status=%s", run_id, row["status"])
            return _row_to_run(row)

    def get_latest_run(
        self,
        project_name: str,
        pipeline_name: str,
    ) -> PipelineRun | None:
        """Get the most recent run for a project+pipeline, or None."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM flow_pipeline_runs "
                "WHERE project_name = ? AND pipeline_name = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (project_name, pipeline_name),
            ).fetchone()
            if row is None:
                return None
            return _row_to_run(row)

    def list_runs(self, limit: int = 50) -> list[PipelineRun]:
        """List recent pipeline runs, ordered by most recently updated."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM flow_pipeline_runs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [_row_to_run(row) for row in rows]

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def log_event(
        self,
        run_id: str,
        event: str,
        *,
        step_name: str | None = None,
        details: str = "",
    ) -> None:
        """Record an audit event for a pipeline run."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO flow_audit_log "
                "(run_id, timestamp, event, step_name, details) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, _now_iso(), event, step_name, details or None),
            )

    def get_audit_log(self, run_id: str) -> list[dict[str, object]]:
        """Get all audit events for a run, ordered by timestamp."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM flow_audit_log WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_run(row: sqlite3.Row) -> PipelineRun:
    """Convert a database row to a PipelineRun."""
    records_data = json.loads(row["step_records"])
    step_records = []
    for rec in records_data:
        result_data = rec.get("result")
        result = StepResult.model_validate(result_data) if result_data else None
        step_records.append(
            StepRecord(
                step_name=rec["step_name"],
                status=StepStatus(rec["status"]),
                result=result,
                attempt=rec.get("attempt", 1),
            )
        )
    return PipelineRun(
        run_id=row["run_id"],
        parent_run_id=row["parent_run_id"],
        pipeline_name=row["pipeline_name"],
        project_name=row["project_name"],
        spec_path=row["spec_path"],
        status=RunStatus(row["status"]),
        current_step=row["current_step"],
        step_records=step_records,
        started_at=row["started_at"],
        updated_at=row["updated_at"],
    )


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()
