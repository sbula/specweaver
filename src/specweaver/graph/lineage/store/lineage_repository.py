import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class LineageRepository:
    """Provides methods for recording and querying artifact lineage events."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # We no longer explicitly initialize the DB here; the Database monolith handles schema management.

    def log_artifact_event(
        self,
        artifact_id: str,
        parent_id: str | None,
        run_id: str,
        event_type: str,
        model_id: str,
    ) -> None:
        """Log a creation or modification event for an artifact."""
        import anyio

        from specweaver.core.config.database import Database
        from specweaver.core.flow.store import FlowRepository

        async def _log() -> None:
            db = Database(self.db_path)
            async with db.async_session_scope() as session:
                await FlowRepository(session).log_artifact_event(
                    artifact_id, parent_id, run_id, event_type, model_id
                )

        anyio.run(_log)

    def get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]:
        """Get the full event history for an artifact, sorted oldest first."""
        import anyio

        from specweaver.core.config.database import Database
        from specweaver.core.flow.store import FlowRepository

        async def _get() -> list[dict[str, Any]]:
            db = Database(self.db_path)
            async with db.async_session_scope() as session:
                # typing: the internal store returns dict[str, object], but Protocol expects dict[str, Any]
                results = await FlowRepository(session).get_artifact_history(artifact_id)
                return [dict(r) for r in results]

        return anyio.run(_get)

    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Get all artifact events that list the given parent_id."""
        import anyio

        from specweaver.core.config.database import Database
        from specweaver.core.flow.store import FlowRepository

        async def _get() -> list[dict[str, Any]]:
            db = Database(self.db_path)
            async with db.async_session_scope() as session:
                results = await FlowRepository(session).get_children(parent_id)
                return [dict(r) for r in results]

        return anyio.run(_get)
