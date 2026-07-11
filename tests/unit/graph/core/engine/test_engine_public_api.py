# mypy: ignore-errors
from typing import TYPE_CHECKING

import networkx as nx

from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import GraphEdge, GraphNode
from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind

if TYPE_CHECKING:
    from specweaver.graph.core.engine.protocol import GraphEngineProtocol


def test_protocol_structural_conformance():
    """Verify that InMemoryGraphEngine implements GraphEngineProtocol."""
    engine: GraphEngineProtocol = InMemoryGraphEngine()
    assert hasattr(engine, "upsert_node")
    assert hasattr(engine, "export_semantic_digraph")


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
