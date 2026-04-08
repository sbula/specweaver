# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Database mixin — validation overrides, domain profiles, and standards CRUD."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


class DataExtensionsMixin:
    """Methods for validation overrides, domain profiles, and standards.

    Requires ``self.connect()`` and ``self.get_project()`` from the  # type: ignore[attr-defined]
    Database base class.
    """



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
        proj = self.get_project(project_name)  # type: ignore[attr-defined]
        if not proj:
            msg = f"Project '{project_name}' not found"
            raise ValueError(msg)
        return str(proj["domain_profile"]) if proj.get("domain_profile") is not None else None

    def set_domain_profile(
        self,
        project_name: str,
        profile_name: str,
    ) -> None:
        """Set the active domain profile for a project.

        Args:
            project_name: Must be a registered project.
            profile_name: Name of an available profile (e.g. 'web-app').

        Raises:
            ValueError: If project not found or profile YAML not found.
        """
        from specweaver.config.profiles import get_profile

        proj = self.get_project(project_name)  # type: ignore[attr-defined]
        if not proj:
            logger.warning("set_domain_profile: project '%s' not found", project_name)
            msg = f"Project '{project_name}' not found"
            raise ValueError(msg)

        if get_profile(profile_name) is None:
            msg = (
                f"Unknown profile '{profile_name}'. "
                "Use 'sw config profiles' to see available profiles."
            )
            logger.warning("set_domain_profile: unknown profile '%s'", profile_name)
            raise ValueError(msg)

        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                "UPDATE projects SET domain_profile = ? WHERE name = ?",
                (profile_name, project_name),
            )

        logger.info(
            "Domain profile '%s' activated for project '%s' (pipeline: validation_spec_%s.yaml)",
            profile_name,
            project_name,
            profile_name.replace("-", "_"),
        )

    def clear_domain_profile(self, project_name: str) -> None:
        """Clear the active domain profile for a project.

        Args:
            project_name: Must be a registered project.

        Raises:
            ValueError: If project is not registered.
        """
        proj = self.get_project(project_name)  # type: ignore[attr-defined]
        if not proj:
            msg = f"Project '{project_name}' not found"
            raise ValueError(msg)

        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                "UPDATE projects SET domain_profile = NULL WHERE name = ?",
                (project_name,),
            )

        logger.info(
            "Domain profile cleared for project '%s' (per-rule overrides preserved)",
            project_name,
        )

    # ------------------------------------------------------------------
    # Project Standards CRUD
    # ------------------------------------------------------------------

    def save_standard(
        self,
        project_name: str,
        scope: str,
        language: str,
        category: str,
        data: dict[str, object],
        confidence: float,
        *,
        confirmed_by: str | None = None,
    ) -> None:
        """Save or update a coding standard (upsert).

        Args:
            project_name: Must be a registered project.
            scope: Scope name (e.g., ``"user-service"`` or ``"."``).
            language: Language name (e.g., ``"python"``).
            category: Category name (e.g., ``"naming"``).
            data: Findings as a dictionary (serialized to JSON).
            confidence: Confidence score (0.0-1.0).
            confirmed_by: ``"hitl"`` if user-confirmed, else None.
        """
        import json

        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(
                "INSERT OR REPLACE INTO project_standards "
                "(project_name, scope, language, category, data, "
                "confidence, confirmed_by, scanned_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    project_name,
                    scope,
                    language,
                    category,
                    json.dumps(data),
                    confidence,
                    confirmed_by,
                    _now_iso(),
                ),
            )

    def get_standards(
        self,
        project_name: str,
        *,
        scope: str | None = None,
        language: str | None = None,
    ) -> list[dict[str, object]]:
        """Query standards for a project, optionally filtered.

        Args:
            project_name: Project to query.
            scope: Filter by scope (optional).
            language: Filter by language (optional).

        Returns:
            List of dicts with keys: scope, language, category, data,
            confidence, confirmed_by, scanned_at.
        """
        query = "SELECT * FROM project_standards WHERE project_name = ?"
        params: list[str] = [project_name]

        if scope is not None:
            query += " AND scope = ?"
            params.append(scope)
        if language is not None:
            query += " AND language = ?"
            params.append(language)

        with self.connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_standard(
        self,
        project_name: str,
        scope: str,
        language: str,
        category: str,
    ) -> dict[str, object] | None:
        """Get a single standard by exact key.

        Returns:
            Dict with all fields, or None if not found.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT * FROM project_standards "
                "WHERE project_name = ? AND scope = ? "
                "AND language = ? AND category = ?",
                (project_name, scope, language, category),
            ).fetchone()
            return dict(row) if row else None

    def clear_standards(
        self,
        project_name: str,
        *,
        scope: str | None = None,
    ) -> None:
        """Delete standards for a project, optionally scoped.

        Args:
            project_name: Project to clear.
            scope: If provided, only delete standards for this scope.
                If None, delete all standards for the project.
        """
        if scope is not None:
            query = "DELETE FROM project_standards WHERE project_name = ? AND scope = ?"
            params: tuple[str, str] | tuple[str] = (project_name, scope)
        else:
            query = "DELETE FROM project_standards WHERE project_name = ?"
            params = (project_name,)

        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(query, params)

    def list_scopes(self, project_name: str) -> list[str]:
        """List distinct scopes that have stored standards.

        Returns:
            Sorted list of scope names.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                "SELECT DISTINCT scope FROM project_standards "
                "WHERE project_name = ? ORDER BY scope",
                (project_name,),
            ).fetchall()
            return [row[0] for row in rows]
