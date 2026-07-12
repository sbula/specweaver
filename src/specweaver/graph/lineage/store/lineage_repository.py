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

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        # WAL mode to prevent Lock Contention
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        # Enable Foreign Keys
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
