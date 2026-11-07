# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Agent Memory Bank — SQLAlchemy entity models.

Defines Task, Epic, TaskDependency, StateTransition, and Defect entities
for the persistent Agent Memory Bank (US-28). All models reuse
workspace.models.Base to share the MetaData registry with Project.
"""

import enum
import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Table, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from specweaver.infrastructure.database import StrictISODateTime
from specweaver.workspace.models import Base

# ── Enums ──────────────────────────────────────────────────────────────


class TaskStatus(enum.Enum):
    """Finite state machine states for Task entities."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    UPSTREAM_BLOCKED = "UPSTREAM_BLOCKED"
    ARCHIVED = "ARCHIVED"


class EpicStatus(enum.Enum):
    """Simple open/closed status for Epic grouping containers."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class DefectStatus(enum.Enum):
    """Formalized status tracking for defects."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class TransitionReason(enum.Enum):
    """Bounded reason enum for StateTransition audit trail (AD-19)."""

    ACQUIRED = "ACQUIRED"
    RELEASED = "RELEASED"
    COMPLETED = "COMPLETED"
    ZOMBIE_TIMEOUT = "ZOMBIE_TIMEOUT"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    MANUAL_UNBLOCK = "MANUAL_UNBLOCK"
    PR_REJECTION = "PR_REJECTION"
    UPSTREAM_BLOCKED = "UPSTREAM_BLOCKED"
    UPSTREAM_CLEARED = "UPSTREAM_CLEARED"
    AGENT_FAILURE = "AGENT_FAILURE"
    ABANDONED = "ABANDONED"
    ARCHIVED = "ARCHIVED"


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.UPSTREAM_BLOCKED},
    TaskStatus.IN_PROGRESS: {TaskStatus.PENDING, TaskStatus.DONE, TaskStatus.BLOCKED},
    TaskStatus.DONE: {TaskStatus.IN_PROGRESS, TaskStatus.ARCHIVED},
    TaskStatus.BLOCKED: {TaskStatus.PENDING, TaskStatus.ARCHIVED},
    TaskStatus.UPSTREAM_BLOCKED: {TaskStatus.PENDING, TaskStatus.ARCHIVED},
    TaskStatus.ARCHIVED: set(),
}


def _project_name_column() -> Mapped[str]:
    """The owning project; renaming or removing the project carries to the row."""
    return mapped_column(
        String,
        ForeignKey("workspace_projects.name", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )


def _task_id_column() -> Mapped[uuid.UUID]:
    """The owning task, indexed; removing the task removes the row."""
    return mapped_column(
        Uuid,
        ForeignKey("memory_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


# ── Models ─────────────────────────────────────────────────────────────


class Epic(Base):
    """Grouping container for related tasks. No state machine (AD-18)."""

    __tablename__ = "memory_epics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = _project_name_column()
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[EpicStatus] = mapped_column(default=EpicStatus.OPEN, nullable=False)
    created_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)


class Task(Base):
    """Core task entity with OCC, heartbeat, and state machine support."""

    __tablename__ = "memory_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_name: Mapped[str] = _project_name_column()
    epic_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("memory_epics.id", ondelete="SET NULL"),
        default=None,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[TaskStatus] = mapped_column(default=TaskStatus.PENDING, nullable=False)
    assigned_worker_id: Mapped[str | None] = mapped_column(String, default=None)
    locked_at: Mapped[datetime | None] = mapped_column(StrictISODateTime, default=None)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(StrictISODateTime, default=None)
    handover_context: Mapped[str | None] = mapped_column(String, default=None)  # Stored as String
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)

    __table_args__ = (
        Index("idx_task_status_project", "status", "project_name"),
        Index("idx_task_heartbeat", "status", "last_heartbeat_at"),
        Index("idx_task_worker", "assigned_worker_id"),
        Index("idx_task_epic", "epic_id"),
        CheckConstraint("length(handover_context) <= 8192", name="chk_handover_length"),
        CheckConstraint("version >= 1", name="chk_version_positive"),
        CheckConstraint("attempt_count >= 0", name="chk_attempts_non_negative"),
    )


class TaskDependency(Base):
    """DAG junction table for task dependencies (AD-2)."""

    __tablename__ = "memory_task_dependencies"

    parent_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("memory_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    child_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("memory_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        Index("idx_dep_child", "child_task_id"),
        Index("idx_dep_parent", "parent_task_id"),
        CheckConstraint("parent_task_id != child_task_id", name="chk_no_self_dependency"),
    )


class StateTransition(Base):
    """Immutable audit trail entry for task state changes (AD-16)."""

    __tablename__ = "memory_state_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = _task_id_column()
    from_status: Mapped[TaskStatus] = mapped_column(nullable=False)
    to_status: Mapped[TaskStatus] = mapped_column(nullable=False)
    reason: Mapped[TransitionReason] = mapped_column(nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String, default=None)
    timestamp: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)


class Defect(Base):
    """Defect entity linked to a task, blocking DONE transition (AD-8)."""

    __tablename__ = "memory_defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = _task_id_column()
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[DefectStatus] = mapped_column(default=DefectStatus.OPEN, nullable=False)
    created_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(StrictISODateTime, default=None)

    __table_args__ = (
        CheckConstraint("length(description) <= 8192", name="chk_defect_desc_length"),
    )


#: The tables, in the order a step creates them (a foreign key's target first).
MEMORY_TABLES: tuple[Table, ...] = tuple(
    cast("Table", model.__table__)
    for model in (Epic, Task, TaskDependency, StateTransition, Defect)
)
