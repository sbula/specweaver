from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from specweaver.core.config.database import StrictISODateTime


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return cls.__name__.lower()

class LlmProfile(Base):
    __tablename__ = "llm_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_global: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    model: Mapped[str] = mapped_column(String, default="gemini-3-flash-preview", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    response_format: Mapped[str] = mapped_column(String, default="text", nullable=False)
    context_limit: Mapped[int] = mapped_column(Integer, default=128000, nullable=False)
    provider: Mapped[str] = mapped_column(String, default="gemini", nullable=False)

class ProjectLlmLink(Base):
    __tablename__ = "project_llm_links"

    project_name: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("llm_profiles.id"), nullable=False
    )

class LlmUsageLog(Base):
    __tablename__ = "llm_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    project_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, default="", nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String, default="")

class LlmCostOverride(Base):
    __tablename__ = "llm_cost_overrides"

    model_pattern: Mapped[str] = mapped_column(String, primary_key=True)
    input_cost_per_1k: Mapped[float] = mapped_column(Float, nullable=False)
    output_cost_per_1k: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)

class LlmRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    async def list_llm_profiles(self, *, global_only: bool = False) -> Sequence[LlmProfile]:
        stmt = select(LlmProfile).order_by(LlmProfile.name)
        if global_only:
            stmt = stmt.where(LlmProfile.is_global == 1)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_llm_profile(
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
        profile = LlmProfile(
            name=name,
            is_global=int(is_global),
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_format=response_format,
            provider=provider
        )
        self.session.add(profile)
        await self.session.flush()
        return profile.id

    async def get_llm_profile(self, profile_id: int) -> LlmProfile | None:
        return await self.session.get(LlmProfile, profile_id)

    async def get_llm_profile_by_name(self, name: str) -> LlmProfile | None:
        stmt = select(LlmProfile).where(LlmProfile.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_llm_profile(self, profile_id: int, **kwargs: object) -> None:
        if not kwargs:
            return
        stmt = update(LlmProfile).where(LlmProfile.id == profile_id).values(**kwargs)
        await self.session.execute(stmt)

    # ------------------------------------------------------------------
    # Project-LLM links
    # ------------------------------------------------------------------

    async def get_project_llm_links(self, project_name: str) -> Sequence[ProjectLlmLink]:
        stmt = select(ProjectLlmLink).where(ProjectLlmLink.project_name == project_name).order_by(ProjectLlmLink.role)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def link_project_profile(
        self,
        project_name: str,
        role: str,
        profile_id: int,
    ) -> None:
        link = await self.session.get(ProjectLlmLink, (project_name, role))
        if link:
            link.profile_id = profile_id
        else:
            self.session.add(ProjectLlmLink(project_name=project_name, role=role, profile_id=profile_id))

    async def get_project_profile(self, project_name: str, role: str) -> LlmProfile | None:
        stmt = (
            select(LlmProfile)
            .join(ProjectLlmLink, LlmProfile.id == ProjectLlmLink.profile_id)
            .where(ProjectLlmLink.project_name == project_name)
            .where(ProjectLlmLink.role == role)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def unlink_project_profile(self, project_name: str, role: str) -> bool:
        stmt = delete(ProjectLlmLink).where(
            ProjectLlmLink.project_name == project_name, ProjectLlmLink.role == role
        )
        result = await self.session.execute(stmt)
        return bool(getattr(result, "rowcount", 0) > 0)

    async def get_project_routing_entries(self, project_name: str) -> list[dict[str, object]]:
        stmt = (
            select(ProjectLlmLink.role, ProjectLlmLink.profile_id, LlmProfile.name.label("profile_name"))
            .outerjoin(LlmProfile, LlmProfile.id == ProjectLlmLink.profile_id)
            .where(ProjectLlmLink.project_name == project_name)
            .where(ProjectLlmLink.role.like("task:%"))
            .order_by(ProjectLlmLink.role)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "task_type": row.role[len("task:") :],
                "profile_id": row.profile_id,
                "profile_name": row.profile_name or "[unknown]",
            }
            for row in result.all()
        ]

    async def clear_all_project_routing(self, project_name: str) -> int:
        stmt = delete(ProjectLlmLink).where(
            ProjectLlmLink.project_name == project_name, ProjectLlmLink.role.like("task:%")
        )
        result = await self.session.execute(stmt)
        return int(getattr(result, "rowcount", 0))

    # ------------------------------------------------------------------
    # Usage logging
    # ------------------------------------------------------------------

    async def log_usage(self, record: dict[str, Any]) -> None:
        log = LlmUsageLog(
            timestamp=datetime.fromisoformat(record["timestamp"]),
            project_name=record["project_name"],
            task_type=record["task_type"],
            model=record["model"],
            provider=record["provider"],
            prompt_tokens=record.get("prompt_tokens", 0),
            completion_tokens=record.get("completion_tokens", 0),
            total_tokens=record.get("total_tokens", 0),
            estimated_cost=record.get("estimated_cost_usd", 0.0),
            duration_ms=record.get("duration_ms", 0),
            run_id=record.get("run_id", ""),
        )
        self.session.add(log)

    async def get_usage_summary(
        self,
        project: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                LlmUsageLog.task_type,
                LlmUsageLog.model,
                func.count().label("call_count"),
                func.sum(LlmUsageLog.prompt_tokens).label("total_prompt_tokens"),
                func.sum(LlmUsageLog.completion_tokens).label("total_completion_tokens"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.estimated_cost).label("total_cost"),
                func.sum(LlmUsageLog.duration_ms).label("total_duration_ms"),
            )
            .group_by(LlmUsageLog.task_type, LlmUsageLog.model)
            .order_by(func.sum(LlmUsageLog.estimated_cost).desc())
        )
        if project:
            stmt = stmt.where(LlmUsageLog.project_name == project)
        if since:
            stmt = stmt.where(LlmUsageLog.timestamp >= since)

        result = await self.session.execute(stmt)
        return [
            {
                "task_type": row.task_type,
                "model": row.model,
                "call_count": row.call_count,
                "total_prompt_tokens": row.total_prompt_tokens,
                "total_completion_tokens": row.total_completion_tokens,
                "total_tokens": row.total_tokens,
                "total_cost": row.total_cost,
                "total_duration_ms": row.total_duration_ms,
            }
            for row in result.all()
        ]

    async def get_usage_by_task_type(self, project: str) -> list[dict[str, Any]]:
        stmt = (
            select(
                LlmUsageLog.task_type,
                func.count().label("call_count"),
                func.sum(LlmUsageLog.total_tokens).label("total_tokens"),
                func.sum(LlmUsageLog.estimated_cost).label("total_cost"),
            )
            .where(LlmUsageLog.project_name == project)
            .group_by(LlmUsageLog.task_type)
            .order_by(func.sum(LlmUsageLog.estimated_cost).desc())
        )
        result = await self.session.execute(stmt)
        return [
            {
                "task_type": row.task_type,
                "call_count": row.call_count,
                "total_tokens": row.total_tokens,
                "total_cost": row.total_cost,
            }
            for row in result.all()
        ]

    # ------------------------------------------------------------------
    # Cost overrides
    # ------------------------------------------------------------------

    async def get_cost_overrides(self) -> dict[str, tuple[float, float]]:
        stmt = select(LlmCostOverride)
        result = await self.session.execute(stmt)
        return {
            row.model_pattern: (row.input_cost_per_1k, row.output_cost_per_1k)
            for row in result.scalars().all()
        }

    async def set_cost_override(
        self,
        model_pattern: str,
        input_cost_per_1k: float,
        output_cost_per_1k: float,
    ) -> None:
        now = datetime.now(UTC)
        override = await self.session.get(LlmCostOverride, model_pattern)
        if override:
            override.input_cost_per_1k = input_cost_per_1k
            override.output_cost_per_1k = output_cost_per_1k
            override.updated_at = now
        else:
            self.session.add(
                LlmCostOverride(
                    model_pattern=model_pattern,
                    input_cost_per_1k=input_cost_per_1k,
                    output_cost_per_1k=output_cost_per_1k,
                    updated_at=now,
                )
            )

    async def delete_cost_override(self, model_pattern: str) -> None:
        stmt = delete(LlmCostOverride).where(LlmCostOverride.model_pattern == model_pattern)
        await self.session.execute(stmt)
