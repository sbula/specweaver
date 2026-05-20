import networkx as nx
import pytest

from specweaver.graph.core.store.repository import SqliteGraphRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "graph.db"
    return SqliteGraphRepository(str(db_path), validated_service_name="test_service")


def test_roundtrip_preserves_nodes_and_edges(repo):
    """[Happy Path] A semantic-hash keyed graph should survive a DB roundtrip."""
    g_in = nx.DiGraph()
    g_in.add_node(
        "test_service:ast:123",
        file_id="src/foo.py",
        package_name="pkg",
        metadata={"key": "val"},
        clone_hash="c1",
    )
    g_in.add_node(
        "test_service:ast:456",
        file_id="src/bar.py",
        package_name="pkg",
        metadata={"key2": "val2"},
        clone_hash="c2",
    )
    g_in.add_edge(
        "test_service:ast:123", "test_service:ast:456", type="CALLS", metadata={"weight": 1}
    )

    repo.persist_semantic_digraph(g_in)

    g_out = repo.load_from_db()

    assert isinstance(g_out, nx.DiGraph)
    assert len(g_out.nodes) == 2
    assert len(g_out.edges) == 1

    # Keys must be semantic hash strings
    node_ids = list(g_out.nodes())
    assert all(isinstance(nid, str) for nid in node_ids)
    assert "test_service:ast:123" in node_ids
    assert "test_service:ast:456" in node_ids

    assert g_out.nodes["test_service:ast:123"]["metadata"] == {"key": "val"}
    assert g_out.has_edge("test_service:ast:123", "test_service:ast:456")
    assert g_out.edges["test_service:ast:123", "test_service:ast:456"]["type"] == "CALLS"


def test_roundtrip_empty_graph(repo):
    """[Boundary] Roundtripping an empty graph works."""
    g_in = nx.DiGraph()
    repo.persist_semantic_digraph(g_in)
    g_out = repo.load_from_db()
    assert len(g_out.nodes) == 0
    assert len(g_out.edges) == 0


def test_roundtrip_preserves_metadata_defaults(repo):
    """[Graceful Degradation] Missing metadata defaults to {}."""
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="f1", package_name="p", clone_hash="c")
    repo.persist_semantic_digraph(g_in)

    g_out = repo.load_from_db()

    # Metadata should default to {}
    assert g_out.nodes["test_service:ast:123"].get("metadata") == {}
