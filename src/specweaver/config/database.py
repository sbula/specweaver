# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SQLite database for SpecWeaver multi-project configuration.

The database lives at ~/.specweaver/specweaver.db — outside any project
directory, so agents cannot modify their own guardrails.

Tables:
- projects              — registered projects (name, root_path, timestamps)
- llm_profiles          — global and project-specific LLM configurations
- project_llm_links     — links projects to LLM profiles by role
- validation_overrides  — per-project validation rule overrides
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

from specweaver.config._db_config_mixin import ConfigSettingsMixin
from specweaver.config._db_extensions_mixin import DataExtensionsMixin
from specweaver.config._db_llm_mixin import LlmProfilesMixin
from specweaver.config._db_telemetry_mixin import TelemetryMixin
from specweaver.config._schema import (
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
_DEFAULT_PROFILES = DEFAULT_PROFILES

logger = logging.getLogger(__name__)

_PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class Database(ConfigSettingsMixin, LlmProfilesMixin, DataExtensionsMixin, TelemetryMixin):
    """SpecWeaver SQLite configuration database.

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

            # Apply v2 migration before seeding (profiles need context_limit)
            current_version = conn.execute(
                "SELECT MAX(version) FROM schema_version",
            ).fetchone()[0] or 0

            if current_version < 2:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V2)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (2, _now_iso()),
                )

            if current_version < 3:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V3)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (3, _now_iso()),
                )

            if current_version < 4:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V4)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (4, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v4 (constitution_max_size)",
                )

            if current_version < 5:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V5)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (5, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v5 (domain_profile)",
                )

            if current_version < 6:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V6)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (6, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v6 (project_standards)",
                )

            if current_version < 7:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V7)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (7, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v7 (auto_bootstrap_constitution)",
                )

            if current_version < 8:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V8)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (8, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v8 (stitch_mode)",
                )

            if current_version < 9:
                with suppress(Exception):
                    conn.executescript(SCHEMA_V9)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (9, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v9 (llm_usage_log, llm_cost_overrides)",
                )


            # Seed default LLM profiles if empty
            profile_count = conn.execute(
                "SELECT COUNT(*) FROM llm_profiles",
            ).fetchone()[0]
            if profile_count == 0:
                conn.executemany(
                    "INSERT INTO llm_profiles "
                    "(name, is_global, model, temperature, "
                    "max_output_tokens, response_format, context_limit) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    DEFAULT_PROFILES,
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
        now = _now_iso()

        with self.connect() as conn:
            # Check duplicate name
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?", (name,),
            ).fetchone()
            if existing:
                msg = f"Project '{name}' already exists"
                raise ValueError(msg)

            # Check duplicate path
            existing_path = conn.execute(
                "SELECT name FROM projects WHERE root_path = ?", (root_path,),
            ).fetchone()
            if existing_path:
                msg = (
                    f"Path '{root_path}' is already registered "
                    f"to project '{existing_path['name']}'"
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
                "SELECT * FROM projects WHERE name = ?", (name,),
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
                "SELECT name FROM projects WHERE name = ?", (name,),
            ).fetchone()
            if not existing:
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
                "SELECT name FROM projects WHERE name = ?", (name,),
            ).fetchone()
            if not existing:
                msg = f"Project '{name}' not found"
                raise ValueError(msg)

            # Check path collision
            path_owner = conn.execute(
                "SELECT name FROM projects WHERE root_path = ? AND name != ?",
                (new_path, name),
            ).fetchone()
            if path_owner:
                msg = (
                    f"Path '{new_path}' is already registered "
                    f"to project '{path_owner['name']}'"
                )
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
                "SELECT name FROM projects WHERE name = ?", (name,),
            ).fetchone()
            if not existing:
                msg = f"Project '{name}' not found"
                raise ValueError(msg)

            conn.execute(
                "INSERT OR REPLACE INTO active_state (key, value) "
                "VALUES ('active_project', ?)",
                (name,),
            )
            conn.execute(
                "UPDATE projects SET last_used_at = ? WHERE name = ?",
                (_now_iso(), name),
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_project_name(name: str) -> None:
    """Validate project name against ^[a-z0-9][a-z0-9_-]*$.

    Raises:
        ValueError: If name is invalid.
    """
    if not name or not _PROJECT_NAME_RE.match(name):
        msg = (
            f"Invalid project name '{name}'. "
            "Must match ^[a-z0-9][a-z0-9_-]*$ "
            "(lowercase, digits, hyphens, underscores; "
            "must start with letter or digit)."
        )
        raise ValueError(msg)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()
