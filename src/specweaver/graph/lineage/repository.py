from typing import Any, Protocol, TypedDict


class ArtifactEvent(TypedDict):
    artifact_id: str
    parent_id: str | None
    run_id: str
    event_type: str
    model_id: str


class LineageRepositoryProtocol(Protocol):
    def get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]:
        """Fetch all events for a given artifact, ordered by creation time."""
        ...

    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Fetch immediate children of a given artifact."""
        ...
