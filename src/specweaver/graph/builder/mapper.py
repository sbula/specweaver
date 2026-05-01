from typing import Any

from specweaver.graph.engine.hashing import SemanticHasher
from specweaver.graph.engine.models import GraphEdge, GraphNode
from specweaver.graph.engine.ontology import EdgeKind, NodeKind


class OntologyMapper:
    """
    Translates raw Tree-Sitter/Polyglot AST outputs into the Universal Graph Ontology.
    """
    def __init__(self) -> None:
        self.hasher = SemanticHasher()

    def map_ast_to_nodes(self, filepath: str, ast_data: dict[str, Any] | None) -> tuple[list[GraphNode], list[GraphEdge]]:
        """
        Parses an AST dictionary and returns a list of mapped GraphNodes and GraphEdges.
        Always returns at least a FILE node.
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # 1. Create the FILE node
        file_hash = self.hasher.hash_file(filepath)

        # simple basename extraction
        basename = filepath
        if "/" in filepath:
            basename = filepath.split("/")[-1]
        elif "\\" in filepath:
            basename = filepath.split("\\")[-1]

        file_node = GraphNode(
            semantic_hash=file_hash,
            kind=NodeKind.FILE,
            name=basename,
            file_id=filepath
        )
        nodes.append(file_node)

        if not ast_data or not isinstance(ast_data, dict):
            return nodes, edges

        # 2. Extract children based on type
        children = ast_data.get("children", [])
        if not isinstance(children, list):
            return nodes, edges

        for child in children:
            if not isinstance(child, dict):
                continue

            self._map_child(filepath, child, file_hash, nodes, edges)

        return nodes, edges

    def _map_child(self, filepath: str, child: dict[str, Any], file_hash: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        node_type = child.get("type", "")
        name = child.get("name", "")

        if not name:
            return

        kind = None
        if node_type in ("function_definition", "method_declaration"):
            kind = NodeKind.PROCEDURE
        elif node_type in ("class_definition", "class_declaration", "interface_declaration"):
            kind = NodeKind.DATA_STRUCTURE
        elif node_type == "module":
            kind = NodeKind.MODULE

        if kind:
            node_hash = self.hasher.hash_node(filepath, name)
            nodes.append(GraphNode(
                semantic_hash=node_hash,
                kind=kind,
                name=name,
                file_id=filepath
            ))
            # Build CONTAINS edge from FILE to this structural node
            edges.append(GraphEdge(
                source_hash=file_hash,
                target_hash=node_hash,
                kind=EdgeKind.CONTAINS
            ))
