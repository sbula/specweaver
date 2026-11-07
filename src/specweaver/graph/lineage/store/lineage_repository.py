# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from specweaver.commons.timestamps import now_iso
from specweaver.infrastructure.database import open_sqlite

logger = logging.getLogger(__name__)


class LineageRepository:
    """Provides methods for recording and querying artifact lineage events."""

    def __init__(self, db_path: str | Path):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        return open_sqlite(self.db_path, row_factory=sqlite3.Row)

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

        with closing(self._get_connection()) as conn, conn:
            conn.execute(
                """
                INSERT INTO flow_artifact_events (artifact_id, parent_id, run_id, event_type, model_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, parent_id, run_id, event_type, model_id, now_iso()),
            )
            conn.commit()

    def get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]:
        """Get the full event history for an artifact, sorted oldest first."""
        with closing(self._get_connection()) as conn, conn:
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
        with closing(self._get_connection()) as conn, conn:
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
