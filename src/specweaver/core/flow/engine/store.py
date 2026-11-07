# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pipeline state store — SQLite persistence for pipeline runs.

Stores runtime data (pipeline runs, step results, audit log) in a separate
``pipeline_state.db`` file, keeping it isolated from the configuration
database (``specweaver.db``).

Opened through the one opener (WAL, foreign keys, the lock wait); the schema is a numbered step
list in ``PRAGMA user_version``.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from specweaver.commons import json
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.infrastructure.database import Step, open_sqlite, rename_legacy_tables, upgrade

logger = logging.getLogger(__name__)

_RUNS = """
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
    updated_at    TEXT NOT NULL,
    spend_state   TEXT NOT NULL DEFAULT '{}'
)"""

_AUDIT = """
CREATE TABLE IF NOT EXISTS flow_audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT NOT NULL REFERENCES flow_pipeline_runs(run_id),
    timestamp TEXT NOT NULL,
    event     TEXT NOT NULL,
    step_name TEXT,
    details   TEXT
)"""

# One row per finding, not per rule: a per-rule grain leaves each rule's findings nowhere to go but
# a JSON column. A rule with no findings still gets a row with NULL finding columns, so "did S01 run
# and pass?" stays answerable. Append-only: a retried step adds rows rather than replacing them.
_VALIDATION = """
CREATE TABLE IF NOT EXISTS flow_validation_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES flow_pipeline_runs(run_id),
    step_name     TEXT NOT NULL,
    attempt       INTEGER NOT NULL DEFAULT 1,
    rule_id       TEXT NOT NULL,
    rule_status   TEXT NOT NULL,
    rule_message  TEXT,
    finding_index INTEGER,
    message       TEXT,
    line          INTEGER,
    severity      TEXT,
    suggestion    TEXT,
    recorded_at   TEXT NOT NULL
)"""

_VALIDATION_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_flow_validation_results_run ON flow_validation_results(run_id)"
)

#: Columns old files lack, with what adds them.
_ADDED_COLUMNS = (
    ("parent_run_id", "TEXT REFERENCES flow_pipeline_runs(run_id)"),
    ("spend_state", "TEXT NOT NULL DEFAULT '{}'"),
)

# Old releases used unprefixed names. `state_schema_version` is renamed too, so that `_adopt` finds
# the version an old file recorded.
_LEGACY_TABLE_RENAMES = (
    ("pipeline_runs", "flow_pipeline_runs"),
    ("audit_log", "flow_audit_log"),
    ("state_schema_version", "flow_state_schema_version"),
)

#: The version table an old file kept, and the `user_version` each of its values means: 1..3 lack
#: columns or a table that step 1 adds, so they start at 0; 4 is today's schema, so step 1 is done.
#: An empty table (`None`) is what the old code read as "new file": 0, so step 1 checks everything.
_OLD_VERSIONS: dict[int | None, int] = {None: 0, 1: 0, 2: 0, 3: 0, 4: 1}
_OLD_VERSION_TABLE = "flow_state_schema_version"


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _create_state(conn: sqlite3.Connection) -> None:
    """Today's schema: the tables if missing, and the columns an old file lacks."""
    for statement in (_RUNS, _AUDIT, _VALIDATION, _VALIDATION_INDEX):
        conn.execute(statement)
    present = {row[1] for row in conn.execute("PRAGMA table_info(flow_pipeline_runs)")}
    for column, definition in _ADDED_COLUMNS:
        if column not in present:
            conn.execute(f"ALTER TABLE flow_pipeline_runs ADD COLUMN {column} {definition}")


def _drop_old_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"DROP TABLE {_OLD_VERSION_TABLE}")


def _adopt_old_version(conn: sqlite3.Connection) -> None:
    """Turn an old file's version table into `user_version`: read, set, check, then drop.

    Runs inside step 1's transaction, so a failure anywhere leaves the old table and version.
    """
    rename_legacy_tables(conn, _LEGACY_TABLE_RENAMES)
    if _OLD_VERSION_TABLE not in _tables(conn):
        return
    old = conn.execute(f"SELECT MAX(version) FROM {_OLD_VERSION_TABLE}").fetchone()[0]
    if old not in _OLD_VERSIONS:
        raise ValueError(f"the old schema version {old} is not one this SpecWeaver knows")
    conn.execute(f"PRAGMA user_version = {_OLD_VERSIONS[old]}")
    if conn.execute("PRAGMA user_version").fetchone()[0] != _OLD_VERSIONS[old]:
        raise RuntimeError(f"user_version did not take the value {_OLD_VERSIONS[old]}")
    _drop_old_version_table(conn)


#: The file's schema, one step per version; never edit a step that has shipped.
_STEPS = (Step(1, "create the pipeline state tables", _create_state),)


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
        """A connection through the one opener, returning rows as `sqlite3.Row`."""
        return open_sqlite(self._db_path, row_factory=sqlite3.Row)

    def _ensure_schema(self) -> None:
        """Bring the file to the current schema version."""
        upgrade(self._db_path, _STEPS, adopt=_adopt_old_version)

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
                "status, current_step, step_records, started_at, updated_at, spend_state) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    json.dumps(run.spend_state),
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

    def get_latest_resumable_run(self, project_name: str) -> PipelineRun | None:
        """The newest parked, failed or aborted run for a project, whatever pipeline produced it.

        `sw resume` used to build this answer itself, by asking `get_latest_run` for each of the 14
        **bundled** pipeline names in turn. That could not see a run of a pipeline loaded from a
        YAML path — an input `sw run` documents and accepts — and it returned the first bundled
        name with a resumable run rather than the most recent one. Both are the same missing query.

        The status filter is inside the SQL rather than applied to the result: filtering afterwards
        would pick the newest run of any kind and then discard it, reporting nothing to resume while
        a parked run waits.
        """
        resumable = (RunStatus.PARKED.value, RunStatus.FAILED.value, RunStatus.ABORTED.value)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM flow_pipeline_runs "
                "WHERE project_name = ? AND status IN (?, ?, ?) "
                "ORDER BY updated_at DESC LIMIT 1",
                (project_name, *resumable),
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
    # Validation results
    # ------------------------------------------------------------------

    def save_validation_results(
        self,
        run_id: str,
        step_name: str,
        *,
        attempt: int,
        results: list[dict[str, Any]],
    ) -> None:
        """Append one row per finding for a validate step's rule results.

        `results` is `StepResult.output["results"]` exactly as `_rule_payload` builds it, so this
        takes primitives and imports nothing from `assurance.validation` — the store stays a store.

        **A rule with no findings still writes one row**, with `finding_index` and the four finding
        columns `NULL`. Dropping it would make a passing rule invisible, and *"did S01 run, and did
        it pass?"* is the first question anyone asks of validation history.

        **Append-only.** A retried step adds rows under a higher `attempt` rather than replacing the
        earlier ones; overwriting would discard the failures that triggered the retry.

        Raises on a `run_id` with no run row — the foreign key is the point, and a row that cannot
        name its run is not worth keeping. The pipeline-loop caller swallows it; a store
        method that silently dropped writes would be lying to every other caller.
        """
        now = _now_iso()
        rows: list[tuple[Any, ...]] = []
        for rule in results:
            base = (
                run_id,
                step_name,
                attempt,
                rule.get("rule_id", ""),
                rule.get("status", ""),
                rule.get("message"),
            )
            findings = rule.get("findings") or []
            if not findings:
                rows.append((*base, None, None, None, None, None, now))
                continue
            rows.extend(
                (
                    *base,
                    index,
                    finding.get("message"),
                    finding.get("line"),
                    finding.get("severity"),
                    finding.get("suggestion"),
                    now,
                )
                for index, finding in enumerate(findings)
            )

        if not rows:
            return

        logger.debug(
            "StateStore.save_validation_results: run_id=%s step=%s attempt=%d rows=%d",
            run_id,
            step_name,
            attempt,
            len(rows),
        )
        with self.connect() as conn:
            conn.executemany(
                "INSERT INTO flow_validation_results "
                "(run_id, step_name, attempt, rule_id, rule_status, rule_message, "
                "finding_index, message, line, severity, suggestion, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def get_validation_results(
        self,
        run_id: str,
        *,
        step: str | None = None,
    ) -> list[dict[str, object]]:
        """Every persisted rule result for a run, oldest first, optionally one step only.

        Run-scoped by signature: cross-run history is deliberately out of scope for this
        sub-feature, and a reader that cannot express it cannot accidentally grow into it.
        """
        sql = "SELECT * FROM flow_validation_results WHERE run_id = ?"
        params: list[object] = [run_id]
        if step is not None:
            sql += " AND step_name = ?"
            params.append(step)
        sql += " ORDER BY id"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

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
        spend_state=json.loads(row["spend_state"]),
        started_at=row["started_at"],
        updated_at=row["updated_at"],
    )


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()
