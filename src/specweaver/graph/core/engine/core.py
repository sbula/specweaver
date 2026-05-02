import asyncio
import threading
from enum import Enum
from typing import Any

import networkx as nx  # type: ignore

from specweaver.graph.core.engine.models import GraphEdge, GraphNode


class InMemoryGraphEngine:
    """
    Pure-logic graph engine wrapping NetworkX.
    Handles semantic hash mapping, concurrency limits, and GraphML serialization.
    """

    def __init__(self) -> None:
        self._graph = nx.DiGraph()
        self._lock = threading.Lock()

        # RT-17: Internal integer routing for fast matrix math
        self._hash_to_int: dict[str, int] = {}
        self._int_to_hash: dict[int, str] = {}
        self._next_int_id = 0

        # RT-31: Semaphore for concurrent subgraph extractions
        self._extraction_semaphore = asyncio.Semaphore(3)

    def _get_or_create_int_id(self, semantic_hash: str) -> int:
        if semantic_hash not in self._hash_to_int:
            self._hash_to_int[semantic_hash] = self._next_int_id
            self._int_to_hash[self._next_int_id] = semantic_hash
            self._next_int_id += 1
        return self._hash_to_int[semantic_hash]

    def upsert_node(self, node: GraphNode) -> None:
        """Add or update a node in the graph."""
        with self._lock:
            int_id = self._get_or_create_int_id(node.semantic_hash)
            # Store the raw Pydantic dict in node attributes
            self._graph.add_node(int_id, **node.model_dump())

    def upsert_edge(self, edge: GraphEdge) -> None:
        """Add or update an edge in the graph."""
        with self._lock:
            src_id = self._get_or_create_int_id(edge.source_hash)
            tgt_id = self._get_or_create_int_id(edge.target_hash)
            self._graph.add_edge(src_id, tgt_id, kind=edge.kind.value)

    def remove_edge(self, source_hash: str, target_hash: str) -> None:
        """Remove an edge from the graph."""
        with self._lock:
            if source_hash in self._hash_to_int and target_hash in self._hash_to_int:
                src_id = self._hash_to_int[source_hash]
                tgt_id = self._hash_to_int[target_hash]
                if self._graph.has_edge(src_id, tgt_id):
                    self._graph.remove_edge(src_id, tgt_id)

    def remove_node(self, semantic_hash: str) -> None:
        """Remove a node and its edges from the graph."""
        with self._lock:
            if semantic_hash in self._hash_to_int:
                int_id = self._hash_to_int[semantic_hash]
                if self._graph.has_node(int_id):
                    self._graph.remove_node(int_id)
                # Note: We do not eagerly reclaim int_ids to avoid remapping overhead.

    def clear_cache(self) -> None:
        """RT-13: Evict memory bloat."""
        with self._lock:
            self._graph.clear()
            self._hash_to_int.clear()
            self._int_to_hash.clear()
            self._next_int_id = 0

    async def extract_subgraph(self, start_hash: str, requested_depth: int) -> nx.DiGraph:
        """
        Extracts a subgraph centered around the start_hash.
        RT-31: Limits concurrency.
        RT-27: Limits depth.
        """
        # RT-27: Hard-coded max depth protection
        max_depth = min(requested_depth, 5)

        async with self._extraction_semaphore:
            with self._lock:
                if start_hash not in self._hash_to_int:
                    return nx.DiGraph()

                start_id = self._hash_to_int[start_hash]
                if not self._graph.has_node(start_id):
                    return nx.DiGraph()

                # nx.ego_graph supports radius (depth). undirected=True searches incoming and outgoing.
                subgraph_int = nx.ego_graph(
                    self._graph, start_id, radius=max_depth, undirected=True
                )

                # Convert back to semantic hashes for the returned subgraph
                subgraph_semantic = nx.DiGraph()
                for n, data in subgraph_int.nodes(data=True):
                    subgraph_semantic.add_node(self._int_to_hash[n], **data)
                for u, v, data in subgraph_int.edges(data=True):
                    subgraph_semantic.add_edge(self._int_to_hash[u], self._int_to_hash[v], **data)

                return subgraph_semantic

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
            export_graph = nx.DiGraph()
            for n, data in self._graph.nodes(data=True):
                safe_data = self._serialize_attributes(data)
                export_graph.add_node(self._int_to_hash[n], **safe_data)

            for u, v, data in self._graph.edges(data=True):
                safe_data = self._serialize_attributes(data)
                export_graph.add_edge(self._int_to_hash[u], self._int_to_hash[v], **safe_data)

            return "".join(nx.generate_graphml(export_graph))
