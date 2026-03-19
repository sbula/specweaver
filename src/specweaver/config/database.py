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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.config.settings import ValidationSettings

logger = logging.getLogger(__name__)

_PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

_SCHEMA_V1 = """\
CREATE TABLE IF NOT EXISTS projects (
    name         TEXT PRIMARY KEY,
    root_path    TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL,
    last_used_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_profiles (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    is_global         INTEGER NOT NULL DEFAULT 1,
    model             TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
    temperature       REAL NOT NULL DEFAULT 0.7,
    max_output_tokens INTEGER NOT NULL DEFAULT 4096,
    response_format   TEXT NOT NULL DEFAULT 'text'
);

CREATE TABLE IF NOT EXISTS project_llm_links (
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    role         TEXT NOT NULL,
    profile_id   INTEGER NOT NULL REFERENCES llm_profiles(id),
    PRIMARY KEY (project_name, role)
);

CREATE TABLE IF NOT EXISTS validation_overrides (
    project_name   TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    rule_id        TEXT NOT NULL,
    enabled        INTEGER NOT NULL DEFAULT 1,
    warn_threshold REAL DEFAULT NULL,
    fail_threshold REAL DEFAULT NULL,
    PRIMARY KEY (project_name, rule_id)
);

CREATE TABLE IF NOT EXISTS active_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""

_DEFAULT_PROFILES = [
    ("review", 1, "gemini-2.5-flash", 0.3, 4096, "text", 128_000),
    ("draft", 1, "gemini-2.5-flash", 0.7, 4096, "text", 128_000),
    ("search", 1, "gemini-2.5-flash", 0.1, 4096, "text", 128_000),
]

_SCHEMA_V2 = """\
ALTER TABLE llm_profiles ADD COLUMN context_limit INTEGER NOT NULL DEFAULT 128000;
"""

_SCHEMA_V3 = """\
ALTER TABLE projects ADD COLUMN log_level TEXT NOT NULL DEFAULT 'DEBUG';
"""

_SCHEMA_V4 = """\
ALTER TABLE projects ADD COLUMN constitution_max_size INTEGER NOT NULL DEFAULT 5120;
"""

_SCHEMA_V5 = """\
ALTER TABLE projects ADD COLUMN domain_profile TEXT DEFAULT NULL;
"""


class Database:
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
            conn.executescript(_SCHEMA_V1)

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
                    conn.executescript(_SCHEMA_V2)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (2, _now_iso()),
                )

            if current_version < 3:
                with suppress(Exception):
                    conn.executescript(_SCHEMA_V3)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (3, _now_iso()),
                )

            if current_version < 4:
                with suppress(Exception):
                    conn.executescript(_SCHEMA_V4)
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
                    conn.executescript(_SCHEMA_V5)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version "
                    "(version, applied_at) VALUES (?, ?)",
                    (5, _now_iso()),
                )
                logger.info(
                    "Database schema migrated to v5 (domain_profile)",
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
                    _DEFAULT_PROFILES,
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

    def get_project(self, name: str) -> dict | None:
        """Get project info by name, or None if not found."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = ?", (name,),
            ).fetchone()
            return dict(row) if row else None

    def list_projects(self) -> list[dict]:
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

    # ------------------------------------------------------------------
    # Logging configuration
    # ------------------------------------------------------------------

    _VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

    def get_log_level(self, project_name: str) -> str:
        """Get the log level for a project.

        Returns "DEBUG" if the project has no explicit setting.

        Raises:
            ValueError: If project not found.
        """
        with self.connect() as conn:
            row = conn.execute(
                "SELECT log_level FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not row:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)
            return row["log_level"]

    def set_log_level(self, project_name: str, level: str) -> None:
        """Set the log level for a project.

        Args:
            project_name: Name of the registered project.
            level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.

        Raises:
            ValueError: If project not found or level is invalid.
        """
        level_upper = level.upper()
        if level_upper not in self._VALID_LOG_LEVELS:
            msg = (
                f"Invalid log level '{level}'. "
                f"Must be one of: {', '.join(sorted(self._VALID_LOG_LEVELS))}"
            )
            raise ValueError(msg)

        with self.connect() as conn:
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not existing:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)

            conn.execute(
                "UPDATE projects SET log_level = ? WHERE name = ?",
                (level_upper, project_name),
            )

    # ------------------------------------------------------------------
    # Constitution configuration
    # ------------------------------------------------------------------

    def get_constitution_max_size(self, project_name: str) -> int:
        """Get the constitution max size for a project (bytes).

        Returns 5120 if the project has no explicit setting.

        Raises:
            ValueError: If project not found.
        """
        with self.connect() as conn:
            row = conn.execute(
                "SELECT constitution_max_size FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not row:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)
            return row["constitution_max_size"]

    def set_constitution_max_size(
        self, project_name: str, max_size: int,
    ) -> None:
        """Set the constitution max size for a project (bytes).

        Args:
            project_name: Name of the registered project.
            max_size: Maximum size in bytes.  Must be positive.

        Raises:
            ValueError: If project not found or size is invalid.
        """
        if max_size <= 0:
            msg = (
                f"Invalid constitution max size {max_size}. "
                "Must be positive."
            )
            raise ValueError(msg)

        with self.connect() as conn:
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not existing:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)

            conn.execute(
                "UPDATE projects SET constitution_max_size = ? WHERE name = ?",
                (max_size, project_name),
            )
            logger.debug(
                "set_constitution_max_size: %s = %d bytes",
                project_name, max_size,
            )

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    def list_llm_profiles(self, *, global_only: bool = False) -> list[dict]:
        """List LLM profiles.

        Args:
            global_only: If True, only return global (shared) profiles.
        """
        with self.connect() as conn:
            if global_only:
                rows = conn.execute(
                    "SELECT * FROM llm_profiles WHERE is_global = 1 ORDER BY name",
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM llm_profiles ORDER BY name",
                ).fetchall()
            return [dict(r) for r in rows]

    def create_llm_profile(
        self,
        name: str,
        *,
        is_global: bool = True,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
        response_format: str = "text",
    ) -> int:
        """Create an LLM profile. Returns the new profile ID."""
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO llm_profiles "
                "(name, is_global, model, temperature, max_output_tokens, response_format) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, int(is_global), model, temperature, max_output_tokens, response_format),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_llm_profile(self, profile_id: int) -> dict | None:
        """Get an LLM profile by ID, or None if not found."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM llm_profiles WHERE id = ?", (profile_id,),
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Project-LLM links
    # ------------------------------------------------------------------

    def get_project_llm_links(self, project_name: str) -> list[dict]:
        """Get all role → profile links for a project."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM project_llm_links WHERE project_name = ? ORDER BY role",
                (project_name,),
            ).fetchall()
            return [dict(r) for r in rows]

    def link_project_profile(
        self, project_name: str, role: str, profile_id: int,
    ) -> None:
        """Link (or re-link) a project role to an LLM profile.

        Raises:
            ValueError: If project or profile not found.
        """
        with self.connect() as conn:
            # Verify project exists
            proj = conn.execute(
                "SELECT name FROM projects WHERE name = ?", (project_name,),
            ).fetchone()
            if not proj:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)

            # Verify profile exists
            profile = conn.execute(
                "SELECT id FROM llm_profiles WHERE id = ?", (profile_id,),
            ).fetchone()
            if not profile:
                msg = f"Profile ID {profile_id} not found"
                raise ValueError(msg)

            conn.execute(
                "INSERT OR REPLACE INTO project_llm_links "
                "(project_name, role, profile_id) VALUES (?, ?, ?)",
                (project_name, role, profile_id),
            )

    def get_project_profile(
        self, project_name: str, role: str,
    ) -> dict | None:
        """Get the resolved LLM profile for a project + role.

        Returns the full profile dict, or None if the role is not linked.
        """
        with self.connect() as conn:
            link = conn.execute(
                "SELECT profile_id FROM project_llm_links "
                "WHERE project_name = ? AND role = ?",
                (project_name, role),
            ).fetchone()
            if not link:
                return None

            row = conn.execute(
                "SELECT * FROM llm_profiles WHERE id = ?",
                (link["profile_id"],),
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Validation overrides
    # ------------------------------------------------------------------

    def set_validation_override(
        self,
        project_name: str,
        rule_id: str,
        *,
        enabled: bool | None = None,
        warn_threshold: float | None = None,
        fail_threshold: float | None = None,
    ) -> None:
        """Set or update a validation override for a project/rule pair.

        Uses UPSERT semantics — creates the row if it doesn't exist,
        updates it if it does.

        Args:
            project_name: Must be a registered project.
            rule_id: Rule identifier (e.g. 'S08', 'C04').
            enabled: Whether the rule is enabled (None = keep existing/default 1).
            warn_threshold: Override warn threshold (None = keep existing/default).
            fail_threshold: Override fail threshold (None = keep existing/default).

        Raises:
            ValueError: If project is not registered.
        """
        with self.connect() as conn:
            proj = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not proj:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)

            # Check if override already exists
            existing = conn.execute(
                "SELECT * FROM validation_overrides "
                "WHERE project_name = ? AND rule_id = ?",
                (project_name, rule_id),
            ).fetchone()

            if existing:
                # Update only the fields that were explicitly provided
                updates: list[str] = []
                params: list[object] = []
                if enabled is not None:
                    updates.append("enabled = ?")
                    params.append(int(enabled))
                if warn_threshold is not None:
                    updates.append("warn_threshold = ?")
                    params.append(warn_threshold)
                if fail_threshold is not None:
                    updates.append("fail_threshold = ?")
                    params.append(fail_threshold)
                if updates:
                    params.extend([project_name, rule_id])
                    conn.execute(
                        f"UPDATE validation_overrides SET {', '.join(updates)} "
                        f"WHERE project_name = ? AND rule_id = ?",
                        params,
                    )
            else:
                conn.execute(
                    "INSERT INTO validation_overrides "
                    "(project_name, rule_id, enabled, warn_threshold, fail_threshold) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        project_name,
                        rule_id,
                        int(enabled) if enabled is not None else 1,
                        warn_threshold,
                        fail_threshold,
                    ),
                )

    def get_validation_override(
        self, project_name: str, rule_id: str,
    ) -> dict | None:
        """Get a single validation override, or None if not set."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM validation_overrides "
                "WHERE project_name = ? AND rule_id = ?",
                (project_name, rule_id),
            ).fetchone()
            return dict(row) if row else None

    def get_validation_overrides(self, project_name: str) -> list[dict]:
        """Get all validation overrides for a project."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM validation_overrides "
                "WHERE project_name = ? ORDER BY rule_id",
                (project_name,),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_validation_override(
        self, project_name: str, rule_id: str,
    ) -> None:
        """Delete a validation override. Idempotent."""
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM validation_overrides "
                "WHERE project_name = ? AND rule_id = ?",
                (project_name, rule_id),
            )

    def load_validation_settings(
        self, project_name: str,
    ) -> ValidationSettings:
        """Load ValidationSettings from DB overrides for a project.

        Args:
            project_name: Must be a registered project.

        Returns:
            ValidationSettings with all overrides for this project.

        Raises:
            ValueError: If project is not registered.
        """
        from specweaver.config.settings import RuleOverride, ValidationSettings

        proj = self.get_project(project_name)
        if not proj:
            msg = f"Project '{project_name}' not found"
            raise ValueError(msg)

        rows = self.get_validation_overrides(project_name)
        overrides: dict[str, RuleOverride] = {}
        for row in rows:
            overrides[row["rule_id"]] = RuleOverride(
                rule_id=row["rule_id"],
                enabled=bool(row["enabled"]),
                warn_threshold=row["warn_threshold"],
                fail_threshold=row["fail_threshold"],
            )
        return ValidationSettings(overrides=overrides)

    # ------------------------------------------------------------------
    # Domain Profiles (Feature 3.3)
    # ------------------------------------------------------------------

    def get_domain_profile(self, project_name: str) -> str | None:
        """Get the active domain profile name for a project.

        Args:
            project_name: Must be a registered project.

        Returns:
            Profile name, or None if no profile is active.

        Raises:
            ValueError: If project is not registered.
        """
        proj = self.get_project(project_name)
        if not proj:
            msg = f"Project '{project_name}' not found"
            raise ValueError(msg)
        return proj.get("domain_profile")

    def set_domain_profile(
        self,
        project_name: str,
        profile_name: str,
    ) -> None:
        """Apply a domain profile to a project.

        This:
        1. Validates the profile name exists in the built-in registry
        2. Clears all existing validation overrides for the project
        3. Writes the profile's overrides to the DB
        4. Stores the profile name

        Args:
            project_name: Must be a registered project.
            profile_name: Name of a built-in profile (e.g. 'web-app').

        Raises:
            ValueError: If project not found or profile name unknown.
        """
        from specweaver.config.profiles import get_profile

        proj = self.get_project(project_name)
        if not proj:
            msg = f"Project '{project_name}' not found"
            raise ValueError(msg)

        profile = get_profile(profile_name)
        if profile is None:
            msg = (
                f"Unknown profile '{profile_name}'. "
                "Use 'sw config profiles' to see available profiles."
            )
            raise ValueError(msg)

        # 1. Clear existing overrides
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM validation_overrides WHERE project_name = ?",
                (project_name,),
            )

        # 2. Write profile overrides
        for rule_id, override in profile.overrides.items():
            self.set_validation_override(
                project_name,
                rule_id,
                enabled=override.enabled if not override.enabled else None,
                warn_threshold=override.warn_threshold,
                fail_threshold=override.fail_threshold,
            )

        # 3. Store profile name
        with self.connect() as conn:
            conn.execute(
                "UPDATE projects SET domain_profile = ? WHERE name = ?",
                (profile_name, project_name),
            )

        logger.info(
            "Applied domain profile '%s' to project '%s' (%d overrides)",
            profile_name, project_name, len(profile.overrides),
        )

    def clear_domain_profile(self, project_name: str) -> None:
        """Clear the domain profile and all validation overrides.

        Args:
            project_name: Must be a registered project.

        Raises:
            ValueError: If project is not registered.
        """
        proj = self.get_project(project_name)
        if not proj:
            msg = f"Project '{project_name}' not found"
            raise ValueError(msg)

        with self.connect() as conn:
            conn.execute(
                "DELETE FROM validation_overrides WHERE project_name = ?",
                (project_name,),
            )
            conn.execute(
                "UPDATE projects SET domain_profile = NULL WHERE name = ?",
                (project_name,),
            )

        logger.info(
            "Cleared domain profile and overrides for project '%s'",
            project_name,
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
