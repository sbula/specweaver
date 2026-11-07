# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The artifact-event table, created by `specweaver.db`'s step 1; `graph.lineage` writes and reads it."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from specweaver.infrastructure.database import StrictISODateTime


class Base(DeclarativeBase):
    pass


class ArtifactEvent(Base):
    __tablename__ = "flow_artifact_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String, index=True, default=None)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[str] = mapped_column(StrictISODateTime, nullable=False)
    model_id: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
