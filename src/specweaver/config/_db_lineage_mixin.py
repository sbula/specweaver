# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Artifact event lineage mixin for Database."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class LineageMixin:
    """Provides methods for recording and querying artifact lineage events.

    This mixin expects the parent class to provide a ``connect()`` method
    that yields a connected ``sqlite3.Connection`` object.
    """

    def connect(self) -> sqlite3.Connection:
        """Type hint stub; implementation provided by Database."""
        raise NotImplementedError

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

        with self.connect() as conn:
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
        with self.connect() as conn:
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
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM artifact_events
                WHERE parent_id = ?
                ORDER BY id ASC
                """,
                (parent_id,),
            ).fetchall()
            return [dict(r) for r in rows]
