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
from typing import Any

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

-- INT-US-04 SF-01 CB-2 (FR-2): the queryable surface `INT-US-04` C1 claimed and never had.
-- ONE ROW PER FINDING (plan D-11), not per rule: a per-rule grain leaves each rule's findings
-- nowhere to go but a JSON column, which is the opaque blob CB-1 rescued them from. A rule with
-- no findings still gets a row with NULL finding columns, so "did S01 run and pass?" stays
-- answerable. Append-only -- a retried step adds rows rather than replacing them, because
-- overwriting discards the earlier attempt's failures (the loss `TECH-021` was filed for).
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
);

CREATE INDEX IF NOT EXISTS idx_flow_validation_results_run
    ON flow_validation_results(run_id);
"""

#: Bumped to 3 by CB-2. The new table needs no data migration -- every statement above is
#: `IF NOT EXISTS` and the script runs on every construction -- so the version records what the
#: schema contains rather than gating a migration step.
_CURRENT_SCHEMA_VERSION = 3

# Legacy installations used these unprefixed names. Order matters — rename
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
        """Migrate a legacy installation's `pipeline_runs`/`audit_log`/
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
                self._record_version(conn)
                logger.debug(
                    "StateStore: created schema v%d at '%s'",
                    _CURRENT_SCHEMA_VERSION,
                    self._db_path,
                )
                return

            version = conn.execute("SELECT MAX(version) FROM flow_state_schema_version").fetchone()[
                0
            ]
            if version == 1:
                # v1 -> v2 is the only step needing a real ALTER; v2 -> v3 added a table, which
                # the `IF NOT EXISTS` script above has already created.
                conn.execute(
                    "ALTER TABLE flow_pipeline_runs ADD COLUMN parent_run_id TEXT REFERENCES flow_pipeline_runs(run_id);"
                )
            if version < _CURRENT_SCHEMA_VERSION:
                self._record_version(conn)
                logger.debug(
                    "StateStore: migrated schema v%s -> v%d at '%s'",
                    version,
                    _CURRENT_SCHEMA_VERSION,
                    self._db_path,
                )

    @staticmethod
    def _record_version(conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO flow_state_schema_version (version, applied_at) VALUES (?, ?)",
            (_CURRENT_SCHEMA_VERSION, _now_iso()),
        )

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

    def get_latest_resumable_run(self, project_name: str) -> PipelineRun | None:
        """The newest parked-or-failed run for a project, whatever pipeline produced it.

        `sw resume` used to build this answer itself, by asking `get_latest_run` for each of the 14
        **bundled** pipeline names in turn. That could not see a run of a pipeline loaded from a
        YAML path — an input `sw run` documents and accepts — and it returned the first bundled
        name with a resumable run rather than the most recent one. Both are the same missing query.

        The status filter is inside the SQL rather than applied to the result: filtering afterwards
        would pick the newest run of any kind and then discard it, reporting nothing to resume while
        a parked run waits.
        """
        resumable = (RunStatus.PARKED.value, RunStatus.FAILED.value)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM flow_pipeline_runs "
                "WHERE project_name = ? AND status IN (?, ?) "
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
        started_at=row["started_at"],
        updated_at=row["updated_at"],
    )


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()
