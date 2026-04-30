from specweaver.graph.models import GranularityLevel, GraphEdge, GraphNode, NodeType
from specweaver.workspace.parsers.interfaces import CodeStructureInterface


class OntologyMapper:
    """
    Translates raw workspace parser outputs into the Universal Ontology.
    Implements Lazy Polyglot Edge Resolution and Granularity boundaries.
    """

    def __init__(self, parser: CodeStructureInterface):
        self.parser = parser

    def map_file_to_nodes(self, file_id: str, code: str) -> list[GraphNode]:
        """
        Parses a file and generates universal GraphNodes.
        Employs RT-14: Gracefully handles declarative/empty structures.
        Employs RT-15: Explicitly skips syntax errors inside parsers.
        """
        nodes = []

        # Root FILE node
        file_node = GraphNode(
            id=-1,  # Temporary, assigned by Engine
            semantic_hash=f"FILE:{file_id}",
            node_type=NodeType.FILE,
            granularity=GranularityLevel.SYSTEM,
            name=file_id,
            file_id=file_id
        )
        nodes.append(file_node)

        # Map Classes (APPLICATION level)
        # Note: CodeStructureInterface does not directly expose class vs function currently
        # via list_symbols without parsing it further, but we treat all symbols broadly.
        try:
            symbols = self.parser.list_symbols(code)
            for sym in symbols:
                if sym == "ERROR":
                    continue

                if sym.startswith("@") or sym.startswith("/api/"):
                    node_type = NodeType.API_CONTRACT
                    gran_level = GranularityLevel.APPLICATION
                else:
                    node_type = NodeType.CLASS if sym[0].isupper() else NodeType.PROCEDURE
                    gran_level = GranularityLevel.APPLICATION if node_type == NodeType.CLASS else GranularityLevel.IMPLEMENTATION

                nodes.append(GraphNode(
                    id=-1,
                    semantic_hash=f"{node_type.name}:{file_id}:{sym}",
                    node_type=node_type,
                    granularity=gran_level,
                    name=sym,
                    file_id=file_id
                ))
        except Exception:
            # Trap RT-15 (Syntax errors)
            file_node.is_partial = True

        return nodes

    def map_file_to_edges(self, file_id: str, code: str) -> list[GraphEdge]:
        """
        Extracts imports and dependencies, yielding dangling Lazy Edges.
        """
        edges = []
        try:
            imports = self.parser.extract_imports(code)
            for imp in imports:
                edges.append(GraphEdge(
                    source_id=-1,  # Requires resolution by engine
                    target_id=-1,  # Dangling target ID
                    edge_type="IMPORTS",
                    metadata={"target_name": imp}  # Lazy Polyglot Resolution
                ))
        except Exception:
            pass
        return edges
