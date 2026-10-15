# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The engine's public API: hash keys, a file index, copies out and REPLACE in.

Proves: TECH-004 FR-1
Proves: TECH-004 FR-2
"""

import inspect

import networkx as nx

from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import GraphEdge, GraphNode
from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind


def _protocol_methods():
    from specweaver.graph.core.engine.protocol import GraphEngineProtocol

    return {
        name: member
        for name, member in vars(GraphEngineProtocol).items()
        if callable(member) and not name.startswith("_")
    }


def test_the_engine_has_every_protocol_method_with_its_parameters():
    """Every method a future engine must offer exists here, taking the same parameters.

    Checked against the protocol's own list, so a method added to the protocol and missing here
    fails; two names were all the old check looked at.
    """
    methods = _protocol_methods()
    assert len(methods) >= 11
    for name, member in methods.items():
        implemented = getattr(InMemoryGraphEngine, name, None)
        assert callable(implemented), name
        assert list(inspect.signature(implemented).parameters) == list(
            inspect.signature(member).parameters
        ), name


def test_export_semantic_digraph_returns_copy():
    engine = InMemoryGraphEngine()
    node = GraphNode(semantic_hash="hash1", kind=NodeKind.FILE, name="f", file_id="f.py")
    engine.upsert_node(node)

    exported = engine.export_semantic_digraph()
    assert "hash1" in exported.nodes

    # Mutating export shouldn't mutate engine
    exported.add_node("hash2")
    assert "hash2" not in engine._nx_graph.nodes


def test_load_semantic_digraph_replaces_state():
    engine = InMemoryGraphEngine()
    engine.upsert_node(
        GraphNode(semantic_hash="hash1", kind=NodeKind.FILE, name="f", file_id="f.py")
    )

    new_graph = nx.DiGraph()
    new_graph.add_node("hash2", file_id="g.py")

    engine.load_semantic_digraph(new_graph)
    assert "hash1" not in engine._nx_graph.nodes
    assert "hash2" in engine._nx_graph.nodes
    assert engine.get_nodes_for_file("g.py") == {"hash2"}


def test_get_nodes_for_file_returns_correct_hashes():
    engine = InMemoryGraphEngine()
    engine.upsert_node(GraphNode(semantic_hash="h1", kind=NodeKind.FILE, name="f1", file_id="a.py"))
    engine.upsert_node(
        GraphNode(semantic_hash="h2", kind=NodeKind.PROCEDURE, name="p1", file_id="A.PY")
    )  # Case normalization test

    assert engine.get_nodes_for_file("a.py") == {"h1", "h2"}
    assert engine.get_nodes_for_file("b.py") == set()


def test_get_edges_involving():
    engine = InMemoryGraphEngine()
    engine.upsert_node(GraphNode(semantic_hash="h1", kind=NodeKind.FILE, name="f1", file_id="a.py"))
    engine.upsert_node(
        GraphNode(semantic_hash="h2", kind=NodeKind.PROCEDURE, name="p1", file_id="a.py")
    )
    engine.upsert_edge(GraphEdge(source_hash="h1", target_hash="h2", kind=EdgeKind.CONTAINS))

    edges = engine.get_edges_involving({"h1"})
    assert edges == {("h1", "h2")}


def test_roundtrip_export_load():
    engine = InMemoryGraphEngine()
    engine.upsert_node(GraphNode(semantic_hash="h1", kind=NodeKind.FILE, name="f1", file_id="a.py"))

    exported = engine.export_semantic_digraph()

    engine2 = InMemoryGraphEngine()
    engine2.load_semantic_digraph(exported)

    assert list(engine2._nx_graph.nodes) == ["h1"]
