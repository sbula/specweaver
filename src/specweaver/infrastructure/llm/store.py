# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import math
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
    delete,
    func,
    or_,
    select,
)
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
    # `None`: unknown — a row written before these existed never joins the history.
    server: Mapped[str | None] = mapped_column(String, default=None, nullable=True)
    dal_level: Mapped[str | None] = mapped_column(String, default=None, nullable=True)
    step_name: Mapped[str | None] = mapped_column(String, default=None, nullable=True)
    # `pending` from before the request until it ends; then `ok` or `failed`. Technical only:
    # how good a result was is not recorded here.
    call_status: Mapped[str] = mapped_column(
        String, default="ok", server_default="ok", nullable=False
    )
    # `None`: not reported, unknown — and on every row written before these existed.
    cached_read_tokens: Mapped[int | None] = mapped_column(Integer, default=None, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, default=None, nullable=True)
    #: A call to a local server, whose missing cost is *not applicable*.
    local: Mapped[bool | None] = mapped_column(Boolean, default=None, nullable=True)

    __table_args__ = (Index("ix_llm_usage_history", "task_type", "model", "dal_level"),)


class LlmPriceRefresh(Base):
    """The last price refresh: when it was tried, what models.dev's ETag was, and for which models."""

    __tablename__ = "llm_price_refresh"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    etag: Mapped[str | None] = mapped_column(String, nullable=True)
    #: The offerings the refresh covered; a new one means the ETag no longer speaks for it.
    offerings: Mapped[str] = mapped_column(String, nullable=False, default="")
    #: When models.dev last answered; a failed attempt sets `checked_at` only.
    reached_at: Mapped[datetime | None] = mapped_column(StrictISODateTime, nullable=True)


class LlmUsagePrice(Base):
    """The price one token kind of a call was billed at: the call's invoice line."""

    __tablename__ = "llm_usage_price"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usage_id: Mapped[int] = mapped_column(
        ForeignKey("llm_usage_log.id"), index=True, nullable=False
    )
    token_kind: Mapped[str] = mapped_column(String, nullable=False)
    usd_per_million: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)


class LlmStepOutcome(Base):
    """How a step ended: one row per step of a run, so its calls can join the history."""

    __tablename__ = "llm_step_outcome"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    step_name: Mapped[str] = mapped_column(String, primary_key=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)


class LlmOffering(Base):
    """One model at one host: the same model costs differently at different hosts."""

    __tablename__ = "llm_offering"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (UniqueConstraint("model", "host"),)


class LlmPriceRule(Base):
    """What must be true for a special price to apply; a `None` limit sets no condition."""

    __tablename__ = "llm_price_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    min_prefix_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_age_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires: Mapped[str] = mapped_column(String, default="nothing", nullable=False)


class LlmPrice(Base):
    """A price of one token kind; the default when it has no rule."""

    __tablename__ = "llm_price"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("llm_offering.id"), index=True, nullable=False
    )
    token_kind: Mapped[str] = mapped_column(String, nullable=False)
    usd_per_million: Mapped[float] = mapped_column(Float, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("llm_price_rule.id"), nullable=True)


def record_step_outcomes(db: Any, run_id: str, outcomes: dict[str, str]) -> None:
    """Store how each of a run's steps ended; a later end of the same run replaces them all."""
    with db.connect() as conn:
        conn.execute("DELETE FROM llm_step_outcome WHERE run_id = ?", (run_id,))
        conn.executemany(
            "INSERT OR REPLACE INTO llm_step_outcome (run_id, step_name, outcome) VALUES (?, ?, ?)",
            [(run_id, step, outcome) for step, outcome in outcomes.items()],
        )


def step_history_limit(
    db: Any,
    *,
    task_type: str,
    model: str,
    dal_level: str,
    unit: str,
    steps: int,
    percentile: int,
) -> float | None:
    """The `percentile` value of the newest `steps` passed steps of one group, in `unit`;
    None while the group has fewer. Only finished calls count: a step with an unpriced call has no
    money total, and a step with a failed call of unknown tokens has no token total."""
    query = """
    SELECT SUM(l.total_tokens), SUM(l.estimated_cost), SUM(l.estimated_cost IS NULL)
    FROM llm_usage_log l
    JOIN llm_step_outcome o ON o.run_id = l.run_id AND o.step_name = l.step_name
    WHERE o.outcome = 'passed' AND l.task_type = ? AND l.model = ? AND l.dal_level = ?
      AND l.call_status != 'pending'
    GROUP BY l.run_id, l.step_name
    {having}
    ORDER BY MAX(l.timestamp) DESC
    LIMIT ?
    """
    having = (
        "HAVING SUM(l.estimated_cost IS NULL) = 0"
        if unit == "usd"
        else "HAVING SUM(l.call_status = 'failed' AND l.total_tokens = 0) = 0"
    )
    with db.connect() as conn:
        rows = conn.execute(
            query.format(having=having), (task_type, model, dal_level, steps)
        ).fetchall()
    if len(rows) < steps:
        return None
    value = nearest_rank([row[1] if unit == "usd" else row[0] for row in rows], percentile)
    return value if value > 0 else None


def nearest_rank(values: list[float], percentile: int) -> float:
    """The smallest value at or above `percentile` percent of `values`."""
    ordered = sorted(values)
    return ordered[max(math.ceil(percentile / 100 * len(ordered)), 1) - 1]


_CLOSED = frozenset({"ok", "failed"})
#: A call that has not ended is never spend: its row holds a worst case.
_FINISHED = LlmUsageLog.call_status != "pending"
#: A local call with no price costs *not applicable*; only a hosted one is *unknown*.
_NOT_APPLICABLE = and_(LlmUsageLog.estimated_cost.is_(None), LlmUsageLog.local.is_(True))
_UNPRICED = and_(
    LlmUsageLog.estimated_cost.is_(None),
    or_(LlmUsageLog.local.is_(None), LlmUsageLog.local.is_(False)),
)


def _columns(record: dict[str, Any]) -> dict[str, Any]:
    """A usage record as the ledger's columns."""
    return {
        "timestamp": datetime.fromisoformat(record["timestamp"]),
        "project_name": record["project_name"],
        "task_type": record["task_type"],
        "model": record["model"],
        "provider": record["provider"],
        "prompt_tokens": record.get("prompt_tokens", 0),
        "completion_tokens": record.get("completion_tokens", 0),
        "total_tokens": record.get("total_tokens", 0),
        "estimated_cost": record.get("estimated_cost_usd"),
        "duration_ms": record.get("duration_ms", 0),
        "run_id": record.get("run_id", ""),
        "server": record.get("server") or None,
        "dal_level": record.get("dal_level") or None,
        "step_name": record.get("step_name") or None,
        "cached_read_tokens": record.get("billed", {}).get("cached_read_tokens"),
        "cache_write_tokens": record.get("billed", {}).get("cache_write_tokens"),
        "local": record.get("billed", {}).get("local"),
    }


class LlmRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    async def open_call(self, record: dict[str, Any]) -> int:
        """Write a call's row as `pending`, with its worst case, before the request is sent."""
        log = LlmUsageLog(**_columns(record), call_status="pending")
        self.session.add(log)
        await self.session.flush()
        return log.id

    async def widen_call(self, call_id: int, record: dict[str, Any]) -> bool:
        """Raise a `pending` row to a larger worst case, as a tool loop starts another round."""
        log = await self.session.get(LlmUsageLog, call_id)
        if log is None or log.call_status != "pending":
            return False
        for name, value in _columns(record).items():
            setattr(log, name, value)
        return True

    async def close_call(self, call_id: int, record: dict[str, Any], status: str) -> bool:
        """Set a call's real numbers and `ok` or `failed`; False when the row is not there."""
        if status not in _CLOSED:
            msg = f"a call closes as ok or failed, not {status!r}"
            raise ValueError(msg)
        log = await self.session.get(LlmUsageLog, call_id)
        if log is None:
            return False
        for name, value in _columns(record).items():
            setattr(log, name, value)
        log.call_status = status
        await self.session.execute(delete(LlmUsagePrice).where(LlmUsagePrice.usage_id == call_id))
        self.session.add_all(
            LlmUsagePrice(
                usage_id=call_id,
                token_kind=line["kind"],
                usd_per_million=line["usd_per_million"],
                source=line["source"],
            )
            for line in record.get("billed", {}).get("price_lines", [])
        )
        return True

    async def get_spend_by_server(self, project: str, since: datetime) -> list[dict[str, Any]]:
        """Spend per model and server since `since`: USD known, and calls with no price."""
        stmt = (
            select(
                LlmUsageLog.model,
                LlmUsageLog.server,
                func.sum(LlmUsageLog.estimated_cost).label("total_cost"),
                func.count().filter(LlmUsageLog.estimated_cost.is_(None)).label("unpriced_calls"),
            )
            .where(LlmUsageLog.project_name == project, LlmUsageLog.timestamp >= since, _FINISHED)
            .group_by(LlmUsageLog.model, LlmUsageLog.server)
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result]

    async def get_status_totals(
        self, project: str | None, since: datetime | None
    ) -> dict[str, dict[str, Any]]:
        """Calls, tokens, known USD and unpriced calls of the `failed` and the `pending` rows."""
        stmt = (
            select(
                LlmUsageLog.call_status,
                func.count().label("calls"),
                func.sum(LlmUsageLog.total_tokens).label("tokens"),
                func.sum(LlmUsageLog.estimated_cost).label("cost"),
                func.count().filter(LlmUsageLog.estimated_cost.is_(None)).label("unpriced_calls"),
            )
            .where(LlmUsageLog.call_status.in_(("failed", "pending")))
            .group_by(LlmUsageLog.call_status)
        )
        if project is not None:
            stmt = stmt.where(LlmUsageLog.project_name == project)
        if since is not None:
            stmt = stmt.where(LlmUsageLog.timestamp >= since)
        result = await self.session.execute(stmt)
        return {row.call_status: dict(row._mapping) for row in result}

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
                func.count().filter(_UNPRICED).label("unpriced_calls"),
                func.count().filter(_NOT_APPLICABLE).label("local_calls"),
                func.sum(LlmUsageLog.cached_read_tokens).label("total_cached"),
                func.count()
                .filter(LlmUsageLog.cached_read_tokens.is_(None))
                .label("unknown_cached"),
                func.sum(LlmUsageLog.duration_ms).label("total_duration_ms"),
            )
            .where(_FINISHED)
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
                "local_calls": row.local_calls,
                "total_cached": row.total_cached,
                "unknown_cached": row.unknown_cached,
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
            .where(LlmUsageLog.project_name == project, _FINISHED)
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
