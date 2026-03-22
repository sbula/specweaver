# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Database mixin — project config settings (logging, constitution, bootstrap)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ConfigSettingsMixin:
    """Methods for per-project configuration settings.

    Requires ``self.connect()`` from the Database base class.  # type: ignore[attr-defined]
    """

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
        with self.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT log_level FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not row:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)
            return str(row["log_level"])

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

        with self.connect() as conn:  # type: ignore[attr-defined]
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
        with self.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT constitution_max_size FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not row:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)
            return int(row["constitution_max_size"])

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

        with self.connect() as conn:  # type: ignore[attr-defined]
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
    # Auto-bootstrap constitution configuration
    # ------------------------------------------------------------------

    _VALID_BOOTSTRAP_MODES = frozenset({"off", "prompt", "auto"})

    def get_auto_bootstrap(self, project_name: str) -> str:
        """Get the auto-bootstrap mode for a project.

        Returns ``"prompt"`` if the project has no explicit setting.

        Raises:
            ValueError: If project not found.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT auto_bootstrap_constitution FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not row:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)
            return str(row["auto_bootstrap_constitution"])

    def set_auto_bootstrap(
        self, project_name: str, mode: str,
    ) -> None:
        """Set the auto-bootstrap mode for a project.

        Args:
            project_name: Name of the registered project.
            mode: One of ``"off"``, ``"prompt"``, ``"auto"``.

        Raises:
            ValueError: If project not found or mode is invalid.
        """
        mode_lower = mode.lower()
        if mode_lower not in self._VALID_BOOTSTRAP_MODES:
            msg = (
                f"Invalid auto-bootstrap mode '{mode}'. "
                f"Must be one of: {', '.join(sorted(self._VALID_BOOTSTRAP_MODES))}"
            )
            raise ValueError(msg)

        with self.connect() as conn:  # type: ignore[attr-defined]
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not existing:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)

            conn.execute(
                "UPDATE projects SET auto_bootstrap_constitution = ? WHERE name = ?",
                (mode_lower, project_name),
            )
            logger.debug(
                "set_auto_bootstrap: %s = %s",
                project_name, mode_lower,
            )

    # ------------------------------------------------------------------
    # Stitch mode configuration
    # ------------------------------------------------------------------

    _VALID_STITCH_MODES = frozenset({"off", "prompt", "auto"})

    def get_stitch_mode(self, project_name: str) -> str:
        """Get the stitch mode for a project.

        Returns ``"off"`` if the project has no explicit setting.

        Raises:
            ValueError: If project not found.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT stitch_mode FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not row:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)
            return str(row["stitch_mode"])

    def set_stitch_mode(
        self, project_name: str, mode: str,
    ) -> None:
        """Set the stitch mode for a project.

        Args:
            project_name: Name of the registered project.
            mode: One of ``"off"``, ``"prompt"``, ``"auto"``.

        Raises:
            ValueError: If project not found or mode is invalid.
        """
        mode_lower = mode.lower()
        if mode_lower not in self._VALID_STITCH_MODES:
            msg = (
                f"Invalid stitch mode '{mode}'. "
                f"Must be one of: {', '.join(sorted(self._VALID_STITCH_MODES))}"
            )
            raise ValueError(msg)

        with self.connect() as conn:  # type: ignore[attr-defined]
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?",
                (project_name,),
            ).fetchone()
            if not existing:
                msg = f"Project '{project_name}' not found"
                raise ValueError(msg)

            conn.execute(
                "UPDATE projects SET stitch_mode = ? WHERE name = ?",
                (mode_lower, project_name),
            )
            logger.debug(
                "set_stitch_mode: %s = %s",
                project_name, mode_lower,
            )
