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
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # WAL mode to prevent Lock Contention
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifact_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artifact_id TEXT NOT NULL,
                    parent_id TEXT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_events_artifact_id ON artifact_events(artifact_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_events_parent_id ON artifact_events(parent_id)"
            )

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
                INSERT INTO artifact_events (
                    artifact_id, parent_id, run_id, event_type, model_id, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, parent_id, run_id, event_type, model_id, _now_iso()),
            )
            logger.debug(
                "Logged artifact event %s for %s (parent=%s, run=%s, model=%s)",
                event_type,
                artifact_id,
                parent_id,
                run_id,
                model_id,
            )

    def get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]:
        """Get the full event history for an artifact, sorted oldest first."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM artifact_events
                WHERE artifact_id = ?
                ORDER BY id ASC
                """,
                (artifact_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Get all artifact events that list the given parent_id."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM artifact_events
                WHERE parent_id = ?
                ORDER BY id ASC
                """,
                (parent_id,),
            ).fetchall()
            return [dict(r) for r in rows]
