# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SQLite database for SpecWeaver multi-project configuration.

The database lives at ~/.specweaver/specweaver.db — outside any project
directory, so agents cannot modify their own guardrails.

Tables:
- projects              — registered projects (name, root_path, timestamps)
- llm_profiles          — global and project-specific LLM configurations
- project_llm_links     — links projects to LLM profiles by role
- validation_overrides  — (Removed in v14)
- active_state          — singleton key-value (currently active project)
- schema_version        — for future DB migrations
"""

from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from specweaver.core.config._db_config_mixin import ConfigSettingsMixin
from specweaver.core.config._db_extensions_mixin import DataExtensionsMixin
from specweaver.core.config._db_llm_mixin import LlmProfilesMixin
from specweaver.core.config._db_telemetry_mixin import TelemetryMixin
from specweaver.core.config._schema import (
    DEFAULT_PROFILES,
    SCHEMA_V1,
    SCHEMA_V2,
    SCHEMA_V3,
    SCHEMA_V4,
    SCHEMA_V5,
    SCHEMA_V6,
    SCHEMA_V7,
    SCHEMA_V8,
    SCHEMA_V9,
    SCHEMA_V10,
    SCHEMA_V11,
    SCHEMA_V12,
    SCHEMA_V13,
    SCHEMA_V14,
)

# Backward-compatible aliases (tests import with underscore prefix)
_SCHEMA_V1 = SCHEMA_V1
_SCHEMA_V2 = SCHEMA_V2
_SCHEMA_V3 = SCHEMA_V3
_SCHEMA_V4 = SCHEMA_V4
_SCHEMA_V5 = SCHEMA_V5
_SCHEMA_V6 = SCHEMA_V6
_SCHEMA_V7 = SCHEMA_V7
_SCHEMA_V8 = SCHEMA_V8
_SCHEMA_V9 = SCHEMA_V9
_SCHEMA_V10 = SCHEMA_V10
_SCHEMA_V11 = SCHEMA_V11
_SCHEMA_V12 = SCHEMA_V12
_SCHEMA_V13 = SCHEMA_V13
_SCHEMA_V14 = SCHEMA_V14
_DEFAULT_PROFILES = DEFAULT_PROFILES

logger = logging.getLogger(__name__)

_PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Data-driven migration table: (version, sql_script, description)
_MIGRATIONS: list[tuple[int, str, str]] = [
    (2, SCHEMA_V2, "context_limit"),
    (3, SCHEMA_V3, "log_level"),
    (4, SCHEMA_V4, "constitution_max_size"),
    (5, SCHEMA_V5, "domain_profile"),
    (6, SCHEMA_V6, "project_standards"),
    (7, SCHEMA_V7, "auto_bootstrap_constitution"),
    (8, SCHEMA_V8, "stitch_mode"),
    (9, SCHEMA_V9, "llm_usage_log, llm_cost_overrides"),
    (10, SCHEMA_V10, "llm_profiles.provider"),
    (11, SCHEMA_V11, "artifact_events & usage correlation"),
    (12, SCHEMA_V12, "model_id for artifact_events"),
    (13, SCHEMA_V13, "default_dal on projects"),
    (14, SCHEMA_V14, "drop validation_overrides"),
]


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _validate_project_name(name: str) -> None:
    if not name or not _PROJECT_NAME_RE.match(name):
        msg = (
            f"Invalid project name '{name}'. Must match ^[a-z0-9][a-z0-9_-]*$ "
            "(lowercase letters, digits, hyphens, underscores; "
            "must start with letter or digit)."
        )
        raise ValueError(msg)


class Database(
    ConfigSettingsMixin,
    DataExtensionsMixin,
    LlmProfilesMixin,
    TelemetryMixin,
):
    """Multi-project configuration database.

    Mixins supply domain methods (config settings, LLM profiles,
    data extensions, telemetry). This class owns the connection and
    schema lifecycle.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug("Database initialized at %s", self._db_path)
        self._ensure_schema()

    def connect(self) -> sqlite3.Connection:
        """Return a new connection with WAL + foreign keys enabled."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create tables and apply migrations. Idempotent."""
        with self.connect() as conn:
            conn.executescript(SCHEMA_V1)

            # Seed schema version if empty
            existing = conn.execute(
                "SELECT COUNT(*) FROM schema_version",
            ).fetchone()[0]
            if existing == 0:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (1, _now_iso()),
                )

            current_version = (
                conn.execute(
                    "SELECT MAX(version) FROM schema_version",
                ).fetchone()[0]
                or 0
            )

            self._apply_migrations(conn, current_version)

            # Seed default LLM profiles if empty
            profile_count = conn.execute(
                "SELECT COUNT(*) FROM llm_profiles",
            ).fetchone()[0]
            if profile_count == 0:
                conn.executemany(
                    "INSERT INTO llm_profiles "
                    "(name, is_global, model, temperature, "
                    "max_output_tokens, response_format, context_limit, provider) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    DEFAULT_PROFILES,
                )

    @staticmethod
    def _apply_migrations(
        conn: sqlite3.Connection,
        current_version: int,
    ) -> None:
        """Apply all pending schema migrations from _MIGRATIONS table."""
        for version, sql, description in _MIGRATIONS:
            if current_version < version:
                with suppress(Exception):
                    conn.executescript(sql)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (version, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v%d (%s)",
                    version,
                    description,
                )

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def register_project(self, name: str, root_path: str) -> None:
        """Register a new project.

        Args:
            name: Project identifier. Must match ^[a-z0-9][a-z0-9_-]*$.
            root_path: Absolute path to the project root directory.

        Raises:
            ValueError: If name is invalid, already exists, or path is
                already registered to another project.
        """
        _validate_project_name(name)
        logger.debug("register_project called for name=%s, path=%s", name, root_path)
        now = _now_iso()

        with self.connect() as conn:
            # Check duplicate name
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (name,),
            ).fetchone()
            if existing:
                logger.warning("register_project failed: name '%s' already exists", name)
                msg = f"Project '{name}' already exists"
                raise ValueError(msg)

            # Check duplicate path
            existing_path = conn.execute(
                "SELECT name FROM projects WHERE root_path = ?",
                (root_path,),
            ).fetchone()
            if existing_path:
                logger.warning(
                    "register_project failed: path '%s' already registered to '%s'",
                    root_path,
                    existing_path["name"],
                )
                msg = (
                    f"Path '{root_path}' is already registered to project '{existing_path['name']}'"
                )
                raise ValueError(msg)

            conn.execute(
                "INSERT INTO projects (name, root_path, created_at, last_used_at) "
                "VALUES (?, ?, ?, ?)",
                (name, root_path, now, now),
            )

            # Auto-link all global profiles
            globals_ = conn.execute(
                "SELECT id, name FROM llm_profiles WHERE is_global = 1",
            ).fetchall()
            for profile in globals_:
                conn.execute(
                    "INSERT INTO project_llm_links (project_name, role, profile_id) "
                    "VALUES (?, ?, ?)",
                    (name, profile["name"], profile["id"]),
                )

    def get_project(self, name: str) -> dict[str, object] | None:
        """Get project info by name, or None if not found."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = ?",
                (name,),
            ).fetchone()
            return dict(row) if row else None

    def list_projects(self) -> list[dict[str, object]]:
        """List all registered projects, ordered by last_used_at desc."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY last_used_at DESC",
            ).fetchall()
            return [dict(r) for r in rows]

    def remove_project(self, name: str) -> None:
        """Unregister a project and cascade-delete its links.

        Raises:
            ValueError: If project not found.
        """
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (name,),
            ).fetchone()
            if not existing:
                logger.warning("remove_project failed: '%s' not found", name)
                msg = f"Project '{name}' not found"
                raise ValueError(msg)

            # Clear active state if it pointed to this project
            active = conn.execute(
                "SELECT value FROM active_state WHERE key = 'active_project'",
            ).fetchone()
            if active and active["value"] == name:
                conn.execute(
                    "DELETE FROM active_state WHERE key = 'active_project'",
                )

            conn.execute("DELETE FROM projects WHERE name = ?", (name,))

    def update_project_path(self, name: str, new_path: str) -> None:
        """Change a project's root_path.

        Raises:
            ValueError: If project not found, or new_path already registered.
        """
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (name,),
            ).fetchone()
            if not existing:
                logger.warning("update_project_path failed: '%s' not found", name)
                msg = f"Project '{name}' not found"
                raise ValueError(msg)

            # Check path collision
            path_owner = conn.execute(
                "SELECT name FROM projects WHERE root_path = ? AND name != ?",
                (new_path, name),
            ).fetchone()
            if path_owner:
                msg = f"Path '{new_path}' is already registered to project '{path_owner['name']}'"
                raise ValueError(msg)

            conn.execute(
                "UPDATE projects SET root_path = ? WHERE name = ?",
                (new_path, name),
            )

    # ------------------------------------------------------------------
    # Active project
    # ------------------------------------------------------------------

    def get_active_project(self) -> str | None:
        """Get the currently active project name, or None."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM active_state WHERE key = 'active_project'",
            ).fetchone()
            return row["value"] if row else None

    def set_active_project(self, name: str) -> None:
        """Set the active project. Updates last_used_at.

        Raises:
            ValueError: If project not found.
        """
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (name,),
            ).fetchone()
            if not existing:
                logger.warning("set_active_project failed: '%s' not found", name)
                msg = f"Project '{name}' not found"
                raise ValueError(msg)

            conn.execute(
                "INSERT OR REPLACE INTO active_state (key, value) VALUES ('active_project', ?)",
                (name,),
            )
            conn.execute(
                "UPDATE projects SET last_used_at = ? WHERE name = ?",
                (_now_iso(), name),
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
