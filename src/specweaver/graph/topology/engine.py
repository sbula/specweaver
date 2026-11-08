# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The module graph's engine: module names and their dependencies, on networkx.

The answers are the ones the hand-written engine gave before it: a traversal reaches its own start
when the start is on a cycle, a neighbourhood never holds its centre, and a name the graph never
saw answers empty. networkx alone answers all three differently, so each is written out here.
"""

import threading

import networkx as nx

from specweaver.graph.core.engine.models import MAX_NEIGHBOURHOOD_DEPTH


class TopologyEngine:
    """Generic directed graph engine for topology math; every read and write holds one lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._graph: nx.DiGraph[str] = nx.DiGraph()

    @property
    def nodes(self) -> set[str]:
        with self._lock:
            return set(self._graph.nodes)

    def add_node(self, node: str) -> None:
        with self._lock:
            self._graph.add_node(node)

    def add_edge(self, source: str, target: str) -> None:
        with self._lock:
            self._graph.add_edge(source, target)

    def get_forward(self, node: str) -> set[str]:
        with self._lock:
            return set(self._graph.successors(node)) if node in self._graph else set()

    def get_reverse(self, node: str) -> set[str]:
        with self._lock:
            return set(self._graph.predecessors(node)) if node in self._graph else set()

    def traverse(self, start: str, forward: bool = True) -> set[str]:
        """Every node reachable from `start`; `start` itself only when it is on a cycle."""
        with self._lock:
            if start not in self._graph:
                return set()
            reach = nx.descendants if forward else nx.ancestors
            reached: set[str] = set(reach(self._graph, start))
            if self._on_a_cycle(start, reached, forward):
                reached.add(start)
            return reached

    def _on_a_cycle(self, start: str, reached: set[str], forward: bool) -> bool:
        """A path leads back to `start`: a self-loop, or a node it reaches points back at it."""
        if self._loops(start):
            return True
        back = self._graph.predecessors(start) if forward else self._graph.successors(start)
        return any(node in reached for node in back)

    def cycles(self) -> list[list[str]]:
        """Every circular dependency, each sorted, the list sorted too; a self-loop is one."""
        with self._lock:
            found = [
                sorted(component)
                for component in nx.strongly_connected_components(self._graph)
                if len(component) > 1 or self._loops(next(iter(component)))
            ]
            return sorted(found)

    def _loops(self, node: str) -> bool:
        return bool(self._graph.has_edge(node, node))

    def neighbors_within(self, module: str, depth: int = 1) -> set[str]:
        """Nodes within `depth` hops either way, never `module` itself; capped at the limit."""
        if depth < 1:
            return set()
        with self._lock:
            if module not in self._graph:
                return set()
            radius = min(depth, MAX_NEIGHBOURHOOD_DEPTH)
            around = nx.ego_graph(self._graph, module, radius=radius, undirected=True)
            return set(around.nodes) - {module}
