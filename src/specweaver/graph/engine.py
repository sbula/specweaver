from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

import networkx as nx

from specweaver.graph.models import GranularityLevel, GraphNode

if TYPE_CHECKING:
    from specweaver.graph.ontology import OntologyMapper


class InMemoryGraphEngine:
    """
    SF-1: In-Memory Knowledge Graph Engine using NetworkX.
    Mathematically decouples from SQLite (SF-2) via internal Integer IDs.
    """

    def __init__(self, ontology_mapper: OntologyMapper):
        self._graph: nx.DiGraph[Any] = nx.DiGraph()
        self._lock = threading.Lock()
        self._ontology = ontology_mapper

        # RT-17: Completely decoupled integer tracking
        self._next_id = 1
        self._hash_to_id: dict[str, int] = {}
        self._id_to_node: dict[int, GraphNode] = {}
        self._file_to_node_ids: dict[str, list[int]] = {}

    def _get_or_create_id(self, semantic_hash: str) -> int:
        if semantic_hash not in self._hash_to_id:
            self._hash_to_id[semantic_hash] = self._next_id
            self._next_id += 1
        return self._hash_to_id[semantic_hash]

    def ingest_file(self, file_path: str, code: str) -> None:
        """
        Parses and ingests a file into the graph.
        Employs RT-18: Coarse-grained thread safety.
        """
        # RT-20: Prevent symlink loops / escape
        # Moved to orchestrator layer to preserve pure-logic boundary.

        # RT-19: Skip memory bombs (> 1MB)
        if len(code.encode('utf-8')) > 1024 * 1024:
            return

        nodes = self._ontology.map_file_to_nodes(file_path, code)
        edges = self._ontology.map_file_to_edges(file_path, code)

        with self._lock:
            # RT-12: Hard reset nodes for this file (Tombstoning/Delete phase)
            if file_path in self._file_to_node_ids:
                old_ids = self._file_to_node_ids[file_path]
                for old_id in old_ids:
                    if self._graph.has_node(old_id):
                        self._graph.remove_node(old_id)

            self._file_to_node_ids[file_path] = []

            # Insert Nodes
            for node in nodes:
                node.id = self._get_or_create_id(node.semantic_hash)
                self._id_to_node[node.id] = node
                self._file_to_node_ids[file_path].append(node.id)
                self._graph.add_node(node.id, **node.to_dict())

            # Insert Lazy Edges
            for edge in edges:
                # Resolve source. Target is lazy, we attach it as a string attribute.
                source_hash = f"FILE:{file_path}"
                edge.source_id = self._get_or_create_id(source_hash)
                # target is unresolved (lazy polyglot resolution)
                self._graph.add_edge(edge.source_id, "LAZY", **edge.metadata)

    def query_subgraph(self, target_node_id: int, depth: int = 3, whitelist_namespaces: list[str] | None = None) -> nx.DiGraph[Any]:
        """
        Extracts a localized subgraph context.
        Implements Microservice Boundary Firewall.
        """
        with self._lock:
            if not self._graph.has_node(target_node_id):
                return nx.DiGraph()

            # BFS up to depth
            subgraph = nx.ego_graph(self._graph, target_node_id, radius=depth)
            result: nx.DiGraph[Any] = nx.DiGraph()

            whitelist = whitelist_namespaces or []

            # Microservice Boundary Firewall
            for n in subgraph.nodes():
                node_data = self._graph.nodes[n]
                # If node is an integer (actual node)
                if isinstance(n, int):
                    granularity = node_data.get("granularity")
                    file_id = node_data.get("file_id", "")

                    # Cross-microservice check: If it's outside our namespace
                    in_whitelist = any(file_id.startswith(ns) for ns in whitelist)
                    if whitelist and not in_whitelist and granularity in [GranularityLevel.APPLICATION.value, GranularityLevel.IMPLEMENTATION.value]:
                        # Drop any application or implementation details from foreign services
                        continue

                result.add_node(n, **node_data)

            # Copy edges for kept nodes
            for u, v, data in subgraph.edges(data=True):
                if result.has_node(u) and result.has_node(v):
                    result.add_edge(u, v, **data)

            return result

    def clear_cache(self) -> None:
        with self._lock:
            self._graph.clear()
            self._hash_to_id.clear()
            self._id_to_node.clear()
            self._file_to_node_ids.clear()
            self._next_id = 1
