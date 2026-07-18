import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class LineageRepository:
    """Provides methods for recording and querying artifact lineage events."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_wal()

    def _ensure_wal(self) -> None:
        """Switch the DB to WAL journal mode ONCE, single-threaded, at construction.

        Switching *to* WAL requires an exclusive lock, and SQLite does not reliably invoke
        the busy handler for that mode-switch — so doing it per-connection lets 20 concurrent
        writers race and raise "database is locked". WAL is persistent in the DB header, so
        setting it once here means every later ``_get_connection`` finds the DB already in
        WAL (no mode switch, no exclusive lock) and only contends on the INSERT, which
        ``busy_timeout`` handles cleanly. Best-effort: an unavailable path surfaces later.
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass  # e.g. db_path is a directory — the error re-surfaces on real use

    def _get_connection(self) -> sqlite3.Connection:
        # ``timeout`` installs SQLite's busy handler from connection creation; combined with
        # busy_timeout, concurrent writers wait for the write lock instead of failing fast.
        # Journal mode is NOT switched here — WAL is set once in _ensure_wal (see above).
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def log_artifact_event(
        self,
        artifact_id: str,
        parent_id: str | None,
        run_id: str,
        event_type: str,
        model_id: str,
    ) -> None:
        """Log a creation or modification event for an artifact."""
        if not artifact_id or not artifact_id.strip():
            raise ValueError("artifact_id cannot be empty")
        if not run_id or not run_id.strip():
            raise ValueError("run_id cannot be empty")
        if not event_type or not event_type.strip():
            raise ValueError("event_type cannot be empty")
        if not model_id or not model_id.strip():
            raise ValueError("model_id cannot be empty")

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO flow_artifact_events (artifact_id, parent_id, run_id, event_type, model_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, parent_id, run_id, event_type, model_id, _now_iso()),
            )
            conn.commit()

    def get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]:
        """Get the full event history for an artifact, sorted oldest first."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, artifact_id, parent_id, run_id, event_type, model_id, timestamp
                FROM flow_artifact_events
                WHERE artifact_id = ?
                ORDER BY id ASC
                """,
                (artifact_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Get all artifact events that list the given parent_id."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, artifact_id, parent_id, run_id, event_type, model_id, timestamp
                FROM flow_artifact_events
                WHERE parent_id = ?
                ORDER BY id ASC
                """,
                (parent_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
