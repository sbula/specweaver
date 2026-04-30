from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GranularityLevel(StrEnum):
    """
    Zero-Trust Sandbox Boundary Enforcements.
    Defines the architectural level of a node to prevent internal microservice
    bloat from leaking across API_CONTRACT boundaries during graph queries.
    """
    SYSTEM = "SYSTEM"
    APPLICATION = "APPLICATION"
    IMPLEMENTATION = "IMPLEMENTATION"

class NodeType(StrEnum):
    """Universal Ontology Types for Polyglot AST Nodes."""
    FILE = "FILE"
    CLASS = "CLASS"
    PROCEDURE = "PROCEDURE"
    DATA_STRUCTURE = "DATA_STRUCTURE"
    API_CONTRACT = "API_CONTRACT"
    VARIABLE = "VARIABLE"
    GHOST = "GHOST"  # Represents a missing or unresolved dependency

@dataclass
class GraphNode:
    """Represents a vertex in the Knowledge Graph."""
    id: int
    semantic_hash: str
    node_type: NodeType
    granularity: GranularityLevel
    name: str
    file_id: str
    is_partial: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for NetworkX insertion."""
        return {
            "semantic_hash": self.semantic_hash,
            "node_type": self.node_type.value,
            "granularity": self.granularity.value,
            "name": self.name,
            "file_id": self.file_id,
            "is_partial": self.is_partial,
            **self.metadata
        }

@dataclass
class GraphEdge:
    """Represents a directed link between GraphNodes."""
    source_id: int
    target_id: int
    edge_type: str  # IMPORTS, CALLS, IMPLEMENTS, CONSUMES, FULFILLS
    metadata: dict[str, Any] = field(default_factory=dict)
