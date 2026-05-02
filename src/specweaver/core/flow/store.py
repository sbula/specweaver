from sqlalchemy import Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from specweaver.core.config.database import StrictISODateTime


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        return cls.__name__.lower()


class ArtifactEvent(Base):
    __tablename__ = "artifact_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String, index=True, default=None)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[str] = mapped_column(StrictISODateTime, nullable=False)
    model_id: Mapped[str] = mapped_column(String, default="unknown", nullable=False)


class FlowRepository:
    """Repository for artifact events and flow tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_artifact_event(
        self,
        artifact_id: str,
        parent_id: str | None,
        run_id: str,
        event_type: str,
        model_id: str,
    ) -> None:
        """Log a creation or modification event for an artifact."""
        from datetime import UTC, datetime

        if not artifact_id or not artifact_id.strip():
            raise ValueError("artifact_id cannot be empty")
        if not run_id or not run_id.strip():
            raise ValueError("run_id cannot be empty")
        if not event_type or not event_type.strip():
            raise ValueError("event_type cannot be empty")
        if not model_id or not model_id.strip():
            raise ValueError("model_id cannot be empty")

        event = ArtifactEvent(
            artifact_id=artifact_id,
            parent_id=parent_id,
            run_id=run_id,
            event_type=event_type,
            model_id=model_id,
            timestamp=datetime.now(tz=UTC),
        )
        self.session.add(event)

    async def get_artifact_history(self, artifact_id: str) -> list[dict[str, object]]:
        """Get the full event history for an artifact, sorted oldest first."""
        from sqlalchemy import select

        stmt = (
            select(ArtifactEvent)
            .where(ArtifactEvent.artifact_id == artifact_id)
            .order_by(ArtifactEvent.id.asc())
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        return [
            {
                "id": e.id,
                "artifact_id": e.artifact_id,
                "parent_id": e.parent_id,
                "run_id": e.run_id,
                "event_type": e.event_type,
                "model_id": e.model_id,
                "timestamp": e.timestamp.isoformat()
                if hasattr(e.timestamp, "isoformat")
                else e.timestamp,
            }
            for e in events
        ]

    async def get_children(self, parent_id: str) -> list[dict[str, object]]:
        """Get all artifact events that list the given parent_id."""
        from sqlalchemy import select

        stmt = (
            select(ArtifactEvent)
            .where(ArtifactEvent.parent_id == parent_id)
            .order_by(ArtifactEvent.id.asc())
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()
        return [
            {
                "id": e.id,
                "artifact_id": e.artifact_id,
                "parent_id": e.parent_id,
                "run_id": e.run_id,
                "event_type": e.event_type,
                "model_id": e.model_id,
                "timestamp": e.timestamp.isoformat()
                if hasattr(e.timestamp, "isoformat")
                else e.timestamp,
            }
            for e in events
        ]
