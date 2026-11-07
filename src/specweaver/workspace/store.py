# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The workspace repository: projects, the active project and standards, in an async session."""

import json
import logging
import re
import shutil
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.core.config.paths import scenario_store_for
from specweaver.workspace.models import ActiveState, Project, ProjectStandard

logger = logging.getLogger(__name__)


def _validate_project_name(name: str) -> None:
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", name):
        raise ValueError(f"Invalid project name '{name}'")


def _iso(value: object) -> object:
    """A stored time as ISO-8601 text; a value that is not a `datetime` as it is."""
    return value.isoformat() if isinstance(value, datetime) else value


def _project_dict(project: Project) -> dict[str, object]:
    return {
        "name": project.name,
        "root_path": project.root_path,
        "created_at": _iso(project.created_at),
        "last_used_at": _iso(project.last_used_at),
        "log_level": project.log_level,
        "constitution_max_size": project.constitution_max_size,
        "domain_profile": project.domain_profile,
        "auto_bootstrap_constitution": project.auto_bootstrap_constitution,
        "default_dal": project.default_dal,
    }


def _standard_dict(row: ProjectStandard) -> dict[str, object]:
    return {
        "project_name": row.project_name,
        "scope": row.scope,
        "language": row.language,
        "category": row.category,
        "data": row.data,
        "confidence": row.confidence,
        "confirmed_by": row.confirmed_by,
        "scanned_at": _iso(row.scanned_at),
    }


class WorkspaceRepository:
    """Repository for managing workspace metadata, configuration, and standards."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    async def register_project(self, name: str, root_path: str) -> None:
        _validate_project_name(name)
        now = datetime.now(UTC)

        # Check duplicate name
        existing = await self.session.get(Project, name)
        if existing:
            raise ValueError(f"Project '{name}' already exists")

        # Check duplicate path
        stmt = select(Project).where(Project.root_path == root_path)
        existing_path = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing_path:
            raise ValueError(
                f"Path '{root_path}' is already registered to project '{existing_path.name}'"
            )

        project = Project(
            name=name,
            root_path=root_path,
            created_at=now,
            last_used_at=now,
        )
        self.session.add(project)
        await self.session.flush()

    async def get_project(self, name: str) -> dict[str, object] | None:
        project = await self.session.get(Project, name)
        return _project_dict(project) if project else None

    async def list_projects(self) -> list[dict[str, object]]:
        stmt = select(Project).order_by(Project.last_used_at.desc())
        result = await self.session.execute(stmt)
        return [_project_dict(project) for project in result.scalars()]

    async def remove_project(self, name: str) -> None:
        project = await self.session.get(Project, name)
        if not project:
            raise ValueError(f"Project '{name}' not found")

        active = await self.session.get(ActiveState, "active_project")
        if active and active.value == name:
            await self.session.delete(active)

        # Explicitly delete dependent entities since aiosqlite PRAGMA cascades may be disabled
        await self.session.execute(
            delete(ProjectStandard).where(ProjectStandard.project_name == name)
        )

        await self.session.delete(project)
        await self.session.flush()
        # A removed project's hidden scenario tests have no owner any more.
        shutil.rmtree(scenario_store_for(name), ignore_errors=True)

    async def update_project_path(self, name: str, new_path: str) -> None:
        project = await self.session.get(Project, name)
        if not project:
            raise ValueError(f"Project '{name}' not found")

        stmt = select(Project).where(Project.root_path == new_path, Project.name != name)
        path_owner = (await self.session.execute(stmt)).scalar_one_or_none()
        if path_owner:
            raise ValueError(
                f"Path '{new_path}' is already registered to project '{path_owner.name}'"
            )

        project.root_path = new_path
        await self.session.flush()

    # ------------------------------------------------------------------
    # Active project
    # ------------------------------------------------------------------

    async def get_active_project(self) -> str | None:
        active = await self.session.get(ActiveState, "active_project")
        return active.value if active else None

    async def set_active_project(self, name: str) -> None:
        project = await self.session.get(Project, name)
        if not project:
            raise ValueError(f"Project '{name}' not found")

        active = await self.session.get(ActiveState, "active_project")
        if active:
            active.value = name
        else:
            self.session.add(ActiveState(key="active_project", value=name))

        project.last_used_at = datetime.now(UTC)
        await self.session.flush()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    _VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
    _VALID_BOOTSTRAP_MODES = frozenset({"off", "prompt", "auto"})

    async def get_log_level(self, project_name: str) -> str:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.log_level

    async def set_log_level(self, project_name: str, level: str) -> None:
        await self._set_level(project_name, level, "log_level")

    async def get_console_log_level(self, project_name: str) -> str:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.console_log_level

    async def set_console_log_level(self, project_name: str, level: str) -> None:
        await self._set_level(project_name, level, "console_log_level")

    async def _set_level(self, project_name: str, level: str, column: str) -> None:
        """Store one of a project's two log levels, refusing a value that is not a level."""
        level_upper = level.upper()
        if level_upper not in self._VALID_LOG_LEVELS:
            raise ValueError(
                f"Invalid log level '{level}'. Must be one of: {', '.join(sorted(self._VALID_LOG_LEVELS))}"
            )
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        setattr(project, column, level_upper)
        await self.session.flush()

    async def get_constitution_max_size(self, project_name: str) -> int:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.constitution_max_size

    async def set_constitution_max_size(self, project_name: str, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError(f"Invalid constitution max size {max_size}. Must be positive.")

        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        project.constitution_max_size = max_size
        await self.session.flush()

    async def get_auto_bootstrap(self, project_name: str) -> str:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.auto_bootstrap_constitution

    async def set_auto_bootstrap(self, project_name: str, mode: str) -> None:
        mode_lower = mode.lower()
        if mode_lower not in self._VALID_BOOTSTRAP_MODES:
            raise ValueError(
                f"Invalid auto-bootstrap mode '{mode}'. Must be one of: {', '.join(sorted(self._VALID_BOOTSTRAP_MODES))}"
            )

        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        project.auto_bootstrap_constitution = mode_lower
        await self.session.flush()

    async def set_default_dal(self, project_name: str, dal: str) -> None:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        project.default_dal = dal.upper()
        await self.session.flush()

    # ------------------------------------------------------------------
    # Domain Profiles
    # ------------------------------------------------------------------

    async def get_domain_profile(self, project_name: str) -> str | None:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.domain_profile

    async def set_domain_profile(self, project_name: str, profile_name: str) -> None:
        from specweaver.core.config.profiles import get_profile

        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        if get_profile(profile_name) is None:
            raise ValueError(
                f"Unknown profile '{profile_name}'. Use 'sw config profiles' to see available profiles."
            )

        project.domain_profile = profile_name
        await self.session.flush()

    async def clear_domain_profile(self, project_name: str) -> None:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        project.domain_profile = None
        await self.session.flush()

    # ------------------------------------------------------------------
    # Project Standards
    # ------------------------------------------------------------------

    async def save_standard(
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
        now = datetime.now(UTC)
        stmt = select(ProjectStandard).where(
            ProjectStandard.project_name == project_name,
            ProjectStandard.scope == scope,
            ProjectStandard.language == language,
            ProjectStandard.category == category,
        )
        standard = (await self.session.execute(stmt)).scalar_one_or_none()

        if standard:
            standard.data = json.dumps(data)
            standard.confidence = confidence
            standard.confirmed_by = confirmed_by
            standard.scanned_at = now
        else:
            self.session.add(
                ProjectStandard(
                    project_name=project_name,
                    scope=scope,
                    language=language,
                    category=category,
                    data=json.dumps(data),
                    confidence=confidence,
                    confirmed_by=confirmed_by,
                    scanned_at=now,
                )
            )
        await self.session.flush()

    async def get_standards(
        self,
        project_name: str,
        *,
        scope: str | None = None,
        language: str | None = None,
    ) -> list[dict[str, object]]:
        stmt = select(ProjectStandard).where(ProjectStandard.project_name == project_name)
        if scope is not None:
            stmt = stmt.where(ProjectStandard.scope == scope)
        if language is not None:
            stmt = stmt.where(ProjectStandard.language == language)

        result = await self.session.execute(stmt)
        return [_standard_dict(row) for row in result.scalars()]

    async def get_standard(
        self,
        project_name: str,
        scope: str,
        language: str,
        category: str,
    ) -> dict[str, object] | None:
        stmt = select(ProjectStandard).where(
            ProjectStandard.project_name == project_name,
            ProjectStandard.scope == scope,
            ProjectStandard.language == language,
            ProjectStandard.category == category,
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return _standard_dict(row) if row else None

    async def clear_standards(
        self,
        project_name: str,
        *,
        scope: str | None = None,
    ) -> None:
        stmt = delete(ProjectStandard).where(ProjectStandard.project_name == project_name)
        if scope is not None:
            stmt = stmt.where(ProjectStandard.scope == scope)
        await self.session.execute(stmt)

    async def list_scopes(self, project_name: str) -> list[str]:
        stmt = (
            select(ProjectStandard.scope)
            .where(ProjectStandard.project_name == project_name)
            .distinct()
            .order_by(ProjectStandard.scope)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())
