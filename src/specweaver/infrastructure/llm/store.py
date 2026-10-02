# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from datetime import datetime
from typing import Any

from sqlalchemy import Float, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from specweaver.core.config.database import StrictISODateTime


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return cls.__name__.lower()


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
    # `None`: the model has no known price. Never 0, which would claim the call was free.
    estimated_cost: Mapped[float | None] = mapped_column(Float, default=None, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String, default="")


class LlmRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # LLM Profiles
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
            estimated_cost=record.get("estimated_cost_usd"),
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
                func.count().filter(LlmUsageLog.estimated_cost.is_(None)).label("unpriced_calls"),
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
                "unpriced_calls": row.unpriced_calls,
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
