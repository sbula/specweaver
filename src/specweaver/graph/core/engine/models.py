import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind


class GraphNode(BaseModel):
    """
    Represents a single node in the Universal Knowledge Graph.
    """

    semantic_hash: str = Field(..., description="Primary string ID (Semantic Hash)")
    kind: NodeKind
    name: str
    file_id: str = Field(..., description="The ID or path of the file containing this node")
    embedding_id: str | None = Field(default=None, description="Future-proofing for Hybrid RAG")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("file_id")
    @classmethod
    def normalize_file_id(cls, v: str) -> str:
        """
        RT-21: Normalize file_id to prevent case-insensitive OS thrashing.
        """
        return v.replace("\\", "/").lower()

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """
        RT-25: Strictly enforce a 2KB limit on metadata to prevent DB bloat.
        """
        payload_size = len(json.dumps(v))
        if payload_size > 2048:
            raise ValueError(f"Metadata size {payload_size} bytes exceeds 2KB limit.")
        return v


class GraphEdge(BaseModel):
    """
    Represents a directional relationship between two GraphNodes.
    """

    source_hash: str
    target_hash: str
    kind: EdgeKind
