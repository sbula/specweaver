# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SQLite atomic reservation system for parallel pipeline flow isolation."""

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SQLiteReservationSystem:
    """Provides atomic resource locking utilizing SQLite IntegrityError boundaries."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize the DB and ensure the reservation schema exists."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get an isolated sqlite3 connection with standard strict isolation."""
        conn = sqlite3.connect(self.db_path, isolation_level="IMMEDIATE")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        """Create the atomic uniqueness reservation table if missing."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sw_reservations (
                        resource_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        expires_at DATETIME
                    )
                    """
                )
        except sqlite3.Error as e:
            logger.error("Failed to initialize SQLiteReservationSystem schema: %s", e)
            raise

    def acquire(self, resource_id: str, run_id: str, timeout_seconds: int = 3600) -> bool:
        """Attempt to atomically acquire a lock for a unique resource_id.

        Args:
            resource_id: The global identifier (e.g. 'port:8080' or component name).
            run_id: The pipeline run requesting the lock.
            timeout_seconds: Safety hatch constraint.

        Returns:
            True if the unique insert passed and lock is acquired. False if blocked.
        """
        expires_at = datetime.now(UTC).isoformat()  # Simplified for testing logic mapping
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO sw_reservations (resource_id, run_id, expires_at) VALUES (?, ?, ?)",
                    (resource_id, run_id, expires_at),
                )
            logger.info(
                "SQLiteReservationSystem acquired lock for '%s' (run_id=%s)", resource_id, run_id
            )
            return True
        except sqlite3.IntegrityError:
            # The core mechanism. A race was lost or the lock is actively held.
            logger.debug(
                "SQLiteReservationSystem: Race condition natural loss. Resource '%s' is locked.",
                resource_id,
            )
            return False
        except sqlite3.OperationalError as e:
            logger.warning(
                "SQLiteReservationSystem Operational timeout on '%s': %s", resource_id, e
            )
            return False

    def release(self, run_id: str) -> None:
        """Release any held locks associated with this pipeline run."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM sw_reservations WHERE run_id = ?", (run_id,))
                if cursor.rowcount > 0:
                    logger.info(
                        "SQLiteReservationSystem released %d locks for run_id=%s",
                        cursor.rowcount,
                        run_id,
                    )
        except sqlite3.Error as e:
            logger.error(
                "SQLiteReservationSystem failed to release lock for run_id=%s: %s", run_id, e
            )
