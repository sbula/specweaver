import json
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import Float, ForeignKey, Integer, String, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from specweaver.core.config.database import StrictISODateTime

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _validate_project_name(name: str) -> None:
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", name):
        raise ValueError(f"Invalid project name '{name}'")


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return cls.__name__.lower()


class Project(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    root_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    log_level: Mapped[str] = mapped_column(String, default="DEBUG", nullable=False)
    constitution_max_size: Mapped[int] = mapped_column(Integer, default=5120, nullable=False)
    domain_profile: Mapped[str | None] = mapped_column(String, default=None)
    auto_bootstrap_constitution: Mapped[str] = mapped_column(
        String, default="prompt", nullable=False
    )
    stitch_mode: Mapped[str] = mapped_column(String, default="off", nullable=False)
    default_dal: Mapped[str] = mapped_column(String, default="DAL_A", nullable=False)


class ActiveState(Base):
    __tablename__ = "active_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


class ProjectStandard(Base):
    __tablename__ = "project_standards"

    project_name: Mapped[str] = mapped_column(
        String, ForeignKey("projects.name", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String, primary_key=True)
    language: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String, default=None)
    scanned_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)


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
        if project:
            return {
                "name": project.name,
                "root_path": project.root_path,
                "created_at": project.created_at.isoformat()
                if isinstance(project.created_at, datetime)
                else project.created_at,
                "last_used_at": project.last_used_at.isoformat()
                if isinstance(project.last_used_at, datetime)
                else project.last_used_at,
                "log_level": project.log_level,
                "constitution_max_size": project.constitution_max_size,
                "domain_profile": project.domain_profile,
                "auto_bootstrap_constitution": project.auto_bootstrap_constitution,
                "stitch_mode": project.stitch_mode,
                "default_dal": project.default_dal,
            }
        return None

    async def list_projects(self) -> list[dict[str, object]]:
        stmt = select(Project).order_by(Project.last_used_at.desc())
        result = await self.session.execute(stmt)
        return [
            {
                "name": project.name,
                "root_path": project.root_path,
                "created_at": project.created_at.isoformat()
                if isinstance(project.created_at, datetime)
                else project.created_at,
                "last_used_at": project.last_used_at.isoformat()
                if isinstance(project.last_used_at, datetime)
                else project.last_used_at,
                "log_level": project.log_level,
                "constitution_max_size": project.constitution_max_size,
                "domain_profile": project.domain_profile,
                "auto_bootstrap_constitution": project.auto_bootstrap_constitution,
                "stitch_mode": project.stitch_mode,
                "default_dal": project.default_dal,
            }
            for project in result.scalars()
        ]

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
    _VALID_STITCH_MODES = frozenset({"off", "prompt", "auto"})

    async def get_log_level(self, project_name: str) -> str:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.log_level

    async def set_log_level(self, project_name: str, level: str) -> None:
        level_upper = level.upper()
        if level_upper not in self._VALID_LOG_LEVELS:
            raise ValueError(
                f"Invalid log level '{level}'. Must be one of: {', '.join(sorted(self._VALID_LOG_LEVELS))}"
            )

        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        project.log_level = level_upper
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

    async def get_stitch_mode(self, project_name: str) -> str:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.stitch_mode

    async def set_stitch_mode(self, project_name: str, mode: str) -> None:
        mode_lower = mode.lower()
        if mode_lower not in self._VALID_STITCH_MODES:
            raise ValueError(
                f"Invalid stitch mode '{mode}'. Must be one of: {', '.join(sorted(self._VALID_STITCH_MODES))}"
            )

        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")

        project.stitch_mode = mode_lower
        await self.session.flush()

    async def get_default_dal(self, project_name: str) -> str:
        project = await self.session.get(Project, project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found")
        return project.default_dal

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
        return [
            {
                "project_name": row.project_name,
                "scope": row.scope,
                "language": row.language,
                "category": row.category,
                "data": row.data,
                "confidence": row.confidence,
                "confirmed_by": row.confirmed_by,
                "scanned_at": row.scanned_at.isoformat()
                if isinstance(row.scanned_at, datetime)
                else row.scanned_at,
            }
            for row in result.scalars()
        ]

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
        if not row:
            return None

        return {
            "project_name": row.project_name,
            "scope": row.scope,
            "language": row.language,
            "category": row.category,
            "data": row.data,
            "confidence": row.confidence,
            "confirmed_by": row.confirmed_by,
            "scanned_at": row.scanned_at.isoformat()
            if isinstance(row.scanned_at, datetime)
            else row.scanned_at,
        }

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
