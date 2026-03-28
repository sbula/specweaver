# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Database mixin — LLM profiles and project-profile links."""

from __future__ import annotations


class LlmProfilesMixin:
    """Methods for LLM profile CRUD and project-role linking.

    Requires ``self.connect()`` from the Database base class.  # type: ignore[attr-defined]
    """

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    def list_llm_profiles(self, *, global_only: bool = False) -> list[dict[str, object]]:
        """List LLM profiles.

        Args:
            global_only: If True, only return global (shared) profiles.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
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
        model: str,
        is_global: bool = True,
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
        response_format: str = "text",
        provider: str = "gemini",
    ) -> int:
        """Create an LLM profile. Returns the new profile ID."""
        with self.connect() as conn:  # type: ignore[attr-defined]
            cursor = conn.execute(
                "INSERT INTO llm_profiles "
                "(name, is_global, model, temperature, max_output_tokens, response_format, provider) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, int(is_global), model, temperature, max_output_tokens, response_format, provider),
            )
            return cursor.lastrowid  # type: ignore[no-any-return]

    def get_llm_profile(self, profile_id: int) -> dict[str, object] | None:
        """Get an LLM profile by ID, or None if not found."""
        with self.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT * FROM llm_profiles WHERE id = ?", (profile_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_llm_profile_by_name(self, name: str) -> dict[str, object] | None:
        """Get an LLM profile by name, or None if not found."""
        with self.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(
                "SELECT * FROM llm_profiles WHERE name = ?", (name,),
            ).fetchone()
            return dict(row) if row else None

    def update_llm_profile(self, profile_id: int, **kwargs: object) -> None:
        """Update fields on an existing LLM profile."""
        if not kwargs:
            return

        fields = []
        values = []
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(profile_id)

        sql = f"UPDATE llm_profiles SET {', '.join(fields)} WHERE id = ?"
        with self.connect() as conn:  # type: ignore[attr-defined]
            conn.execute(sql, tuple(values))

    # ------------------------------------------------------------------
    # Project-LLM links
    # ------------------------------------------------------------------

    def get_project_llm_links(self, project_name: str) -> list[dict[str, object]]:
        """Get all role → profile links for a project."""
        with self.connect() as conn:  # type: ignore[attr-defined]
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
        with self.connect() as conn:  # type: ignore[attr-defined]
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
    ) -> dict[str, object] | None:
        """Get the resolved LLM profile for a project + role.

        Returns the full profile dict, or None if the role is not linked.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
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

    def unlink_project_profile(self, project_name: str, role: str) -> bool:
        """Remove a project-role → profile link.

        Args:
            project_name: Name of the project.
            role: Role key (e.g. ``"task:implement"``).

        Returns:
            True if a row was deleted, False if no entry existed.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            cursor = conn.execute(
                "DELETE FROM project_llm_links WHERE project_name = ? AND role = ?",
                (project_name, role),
            )
            return bool(cursor.rowcount > 0)

    def get_project_routing_entries(
        self, project_name: str,
    ) -> list[dict[str, object]]:
        """Return all per-task routing entries for a project.

        Routing entries are those whose ``role`` column starts with ``"task:"``
        (e.g. ``"task:implement"``, ``"task:review"``). Plain roles such as
        ``"review"`` or ``"draft"`` are excluded.

        Returns a list of dicts with keys: ``task_type``, ``profile_id``,
        ``profile_name``.
        """
        with self.connect() as conn:  # type: ignore[attr-defined]
            rows = conn.execute(
                "SELECT pll.role, pll.profile_id, lp.name AS profile_name "
                "FROM project_llm_links pll "
                "JOIN llm_profiles lp ON lp.id = pll.profile_id "
                "WHERE pll.project_name = ? AND pll.role LIKE 'task:%' "
                "ORDER BY pll.role",
                (project_name,),
            ).fetchall()
            return [
                {
                    "task_type": row["role"][len("task:"):],
                    "profile_id": row["profile_id"],
                    "profile_name": row["profile_name"],
                }
                for row in rows
            ]

