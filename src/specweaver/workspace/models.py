# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The workspace's tables in `specweaver.db`: projects, the active project, and their standards."""

from datetime import datetime
from typing import cast

from sqlalchemy import Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from specweaver.commons.enums.dal import DALLevel
from specweaver.commons.limits import DEFAULT_MAX_CONSTITUTION_SIZE
from specweaver.infrastructure.database import StrictISODateTime

#: The DAL of a project nobody set one for, and of a folder outside every project `[agreed 2026-10-08]`.
DEFAULT_DAL = DALLevel.DAL_C


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "workspace_projects"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    root_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)
    log_level: Mapped[str] = mapped_column(String, default="DEBUG", nullable=False)
    #: What reaches the console; `log_level` is what reaches the log file.
    console_log_level: Mapped[str] = mapped_column(
        String, default="WARNING", server_default="WARNING", nullable=False
    )
    constitution_max_size: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_MAX_CONSTITUTION_SIZE, nullable=False
    )
    domain_profile: Mapped[str | None] = mapped_column(String, default=None)
    auto_bootstrap_constitution: Mapped[str] = mapped_column(
        String, default="prompt", nullable=False
    )
    #: Unused; a database that has this NOT NULL column needs a value on every insert.
    stitch_mode: Mapped[str] = mapped_column(String, default="off", nullable=False)
    default_dal: Mapped[str] = mapped_column(String, default=DEFAULT_DAL.value, nullable=False)


class ActiveState(Base):
    __tablename__ = "workspace_active_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


class ProjectStandard(Base):
    __tablename__ = "workspace_project_standards"

    project_name: Mapped[str] = mapped_column(
        String, ForeignKey("workspace_projects.name", ondelete="CASCADE"), primary_key=True
    )
    scope: Mapped[str] = mapped_column(String, primary_key=True)
    language: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String, default=None)
    scanned_at: Mapped[datetime] = mapped_column(StrictISODateTime, nullable=False)


#: The tables, in the order a step creates them (a foreign key's target first).
WORKSPACE_TABLES: tuple[Table, ...] = tuple(
    cast("Table", model.__table__) for model in (Project, ActiveState, ProjectStandard)
)
