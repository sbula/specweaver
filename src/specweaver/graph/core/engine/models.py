# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind

METADATA_MAX_BYTES = 2048
"""RT-25's cap on a node's or an edge's metadata, named once so both can honour the same number.

It was a literal inside `GraphNode`'s validator. `FR-12` puts an unresolved raw name on an edge and
that name comes from source nobody controls, so a second place needed the same limit -- and a limit
spelled twice is the shape that produced this ticket's two worst defects.
"""


_TRUNCATION_MARK = "…"


def _encoded_size(value: str) -> int:
    """How many bytes `{"raw": value}` costs on disk. BYTES, not characters: `é` is two."""
    return len(json.dumps({"raw": value}).encode("utf-8"))


def fit_metadata_value(value: str) -> str:
    """`value`, shortened until the metadata holding it fits `METADATA_MAX_BYTES`.

    Shortened rather than refused. The validators raise, which is right for metadata a caller
    assembled; this string is an identifier read out of source nobody controls, and the raise would
    happen inside the mapper where nothing catches it -- one absurd identifier would abort an entire
    build, which `NFR-6` forbids.

    The mark is visible on purpose: a silently shortened name reads as a real, different name, and
    a reader chasing it would look for a symbol that does not exist.
    """
    if _encoded_size(value) <= METADATA_MAX_BYTES:
        return value
    low, high = 0, len(value)
    while low < high:
        mid = (low + high + 1) // 2
        if _encoded_size(value[:mid] + _TRUNCATION_MARK) <= METADATA_MAX_BYTES:
            low = mid
        else:
            high = mid - 1
    return value[:low] + _TRUNCATION_MARK


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
        payload_size = len(json.dumps(v).encode("utf-8"))
        if payload_size > METADATA_MAX_BYTES:
            raise ValueError(f"Metadata size {payload_size} bytes exceeds 2KB limit.")
        return v


EDGE_KIND_ATTR = "kind"
"""The networkx edge attribute an edge's `EdgeKind` is stored under.

Named once because naming it twice is what broke it. The engine wrote `kind`, the store read
`type`, each half self-consistent and neither able to see the other, so every edge ever persisted
took the store's `"CALLS"` fallback. Both sides import this now; the `graph_edges` column keeps its
own name because it is part of the primary key.
"""


class GraphEdge(BaseModel):
    """
    Represents a directional relationship between two GraphNodes.
    """

    source_hash: str
    target_hash: str
    kind: EdgeKind
    metadata: dict[str, Any] = Field(default_factory=dict)
    """What the edge knows that its endpoints do not.

    `FR-12`: an edge to a `GHOST` carries the raw name it could not resolve. The store materialises
    a ghost node from an unknown target hash, by which point the name is gone -- a hash is one-way.
    The edge is the only place that still has it.
    """

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        """RT-25 again, and for the same reason: `graph_edges.metadata` is a column like any other.

        The mapper truncates before it reaches here, so this is the backstop for a caller that
        builds an edge by hand rather than the path a build takes.
        """
        payload_size = len(json.dumps(v).encode("utf-8"))
        if payload_size > METADATA_MAX_BYTES:
            raise ValueError(f"Metadata size {payload_size} bytes exceeds 2KB limit.")
        return v
