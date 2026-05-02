from enum import StrEnum


class NodeKind(StrEnum):
    """
    The Universal Ontology for Knowledge Graph Nodes.
    Represents the structural and semantic types of nodes across the enterprise graph.
    """
    # Macro Architecture
    SYSTEM = "SYSTEM"
    MICROSERVICE = "MICROSERVICE"

    # Code Structure
    FILE = "FILE"
    MODULE = "MODULE"
    NAMESPACE = "NAMESPACE"
    DATA_STRUCTURE = "DATA_STRUCTURE"

    # Execution
    PROCEDURE = "PROCEDURE"
    STATE = "STATE"

    # Boundaries & Events
    API_CONTRACT = "API_CONTRACT"
    MESSAGE_QUEUE = "MESSAGE_QUEUE"

    # External
    GHOST = "GHOST"


class EdgeKind(StrEnum):
    """
    The Universal Ontology for Knowledge Graph Edges.
    Represents the semantic relationships between nodes.
    """
    # Structural
    CONTAINS = "CONTAINS"

    # Code
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"

    # Dataflow
    CONSUMES = "CONSUMES"
    FULFILLS = "FULFILLS"
    PUBLISHES = "PUBLISHES"
    SUBSCRIBES = "SUBSCRIBES"
