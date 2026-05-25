import threading
from enum import Enum
from typing import Any

import networkx as nx

from specweaver.graph.core.engine.models import GraphEdge, GraphNode


class InMemoryGraphEngine:
    """
    Pure-logic graph engine wrapping NetworkX.
    Handles semantic hash mapping and GraphML serialization.
    """

    def __init__(self) -> None:
        self._nx_graph = nx.DiGraph()  # type: ignore[var-annotated]
        self._lock = threading.Lock()
        self._file_index: dict[str, set[str]] = {}

    def upsert_node(self, node: GraphNode) -> None:
        """Add or update a node in the graph."""
        with self._lock:
            # node.file_id is already normalized by Pydantic validator
            file_id = node.file_id

            self._nx_graph.add_node(node.semantic_hash, **node.model_dump())

            if file_id not in self._file_index:
                self._file_index[file_id] = set()
            self._file_index[file_id].add(node.semantic_hash)

    def upsert_edge(self, edge: GraphEdge) -> None:
        """Add or update an edge in the graph."""
        with self._lock:
            self._nx_graph.add_edge(edge.source_hash, edge.target_hash, kind=edge.kind.value)

    def remove_edge(self, source_hash: str, target_hash: str) -> None:
        """Remove an edge from the graph."""
        with self._lock:
            if self._nx_graph.has_edge(source_hash, target_hash):
                self._nx_graph.remove_edge(source_hash, target_hash)

    def remove_node(self, semantic_hash: str) -> None:
        """Remove a node and its edges from the graph."""
        with self._lock:
            if self._nx_graph.has_node(semantic_hash):
                # Remove from file_index
                node_data = self._nx_graph.nodes[semantic_hash]
                file_id = node_data.get("file_id")
                if file_id and file_id in self._file_index:
                    self._file_index[file_id].discard(semantic_hash)
                    if not self._file_index[file_id]:
                        del self._file_index[file_id]

                self._nx_graph.remove_node(semantic_hash)

    def clear_cache(self) -> None:
        """RT-13: Evict memory bloat."""
        with self._lock:
            self._nx_graph.clear()
            self._file_index.clear()

    def extract_subgraph(self, start_hash: str, requested_depth: int) -> nx.DiGraph:  # type: ignore[type-arg]
        """
        Extracts a subgraph centered around the start_hash.
        RT-27: Limits depth.
        """
        if not isinstance(start_hash, str):
            raise ValueError(f"extract_subgraph requires a string hash, got {type(start_hash)}")

        max_depth = min(requested_depth, 5)

        with self._lock:
            if not self._nx_graph.has_node(start_hash):
                from specweaver.graph.core.engine.protocol import NodeNotFoundError

                raise NodeNotFoundError(f"Node {start_hash} does not exist in the graph.")

            # nx.ego_graph supports radius (depth). undirected=True searches incoming and outgoing.
            subgraph_semantic = nx.ego_graph(
                self._nx_graph, start_hash, radius=max_depth, undirected=True
            )
            return subgraph_semantic  # type: ignore[no-any-return]

    def _serialize_attributes(self, data: dict[str, Any]) -> dict[str, Any]:
        """Helper to safely serialize dictionaries and enums for GraphML."""
        safe_data: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                safe_data[k] = str(v)
            elif v is None:
                safe_data[k] = ""
            elif isinstance(v, Enum):
                safe_data[k] = v.value
            else:
                safe_data[k] = str(v) if not isinstance(v, (int, float, str, bool)) else v
        return safe_data

    def to_graphml_string(self) -> str:
        """
        Exports the entire graph to a GraphML string representation.
        RT-22: Serialization must handle complex types (like metadata dicts).
        """
        with self._lock:
            export_graph = nx.DiGraph()  # type: ignore[var-annotated]
            for n, data in self._nx_graph.nodes(data=True):
                safe_data = self._serialize_attributes(data)
                export_graph.add_node(n, **safe_data)

            for u, v, data in self._nx_graph.edges(data=True):
                safe_data = self._serialize_attributes(data)
                export_graph.add_edge(u, v, **safe_data)

            return "".join(nx.generate_graphml(export_graph))

    def export_semantic_digraph(self) -> nx.DiGraph:  # type: ignore[type-arg]
        """
        Exports a shallow copy of the internal graph.
        WARNING: Node attribute dicts are shared references. Treat as read-only.
        """
        with self._lock:
            return nx.DiGraph(self._nx_graph)

    def load_semantic_digraph(self, semantic_digraph: nx.DiGraph) -> None:  # type: ignore[type-arg]
        """
        Replaces the engine's internal state with the provided graph.
        Rebuilds the file index.
        """
        with self._lock:
            self._nx_graph.clear()
            self._file_index.clear()

            self._nx_graph = semantic_digraph
            for n, data in self._nx_graph.nodes(data=True):
                file_id = data.get("file_id")
                if file_id:
                    if file_id not in self._file_index:
                        self._file_index[file_id] = set()
                    self._file_index[file_id].add(n)

    def get_nodes_for_file(self, file_id: str) -> set[str]:
        """O(1) lookup of nodes associated with a normalized file_id."""
        with self._lock:
            # We must normalize here because incoming file_id might not be a GraphNode
            normalized = file_id.replace("\\", "/").lower()
            return self._file_index.get(normalized, set()).copy()

    def get_edges_involving(self, semantic_hashes: set[str]) -> set[tuple[str, str]]:
        """Returns all edges where the source or target is in semantic_hashes."""
        with self._lock:
            # NetworkX nbunch API is optimized for this
            return set(self._nx_graph.edges(semantic_hashes))
