import sqlite3

import networkx as nx
import pytest

from specweaver.graph.core.store.repository import SqliteGraphRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "graph.db"
    return SqliteGraphRepository(str(db_path), validated_service_name="test_service")

def test_load_happy_path(repo):
    """Test loading a basic graph."""
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={"key": "value"}, clone_hash="c1")
    g_in.add_node("test_service:ast:456", file_id="file1", package_name="pkg1", metadata={"key": "value2"}, clone_hash="c2")
    g_in.add_edge("test_service:ast:123", "test_service:ast:456", type="CALLS", metadata={"weight": 1})

    repo.flush_to_db(g_in)

    g_out, hash_to_id = repo.load_from_db()

    assert isinstance(g_out, nx.DiGraph)
    assert len(g_out.nodes) == 2
    assert len(g_out.edges) == 1

    # Internal NetworkX nodes should use the fast integer IDs
    node_ids = list(g_out.nodes())
    assert isinstance(node_ids[0], int)

    # The attributes must be mapped back correctly
    id_123 = hash_to_id["test_service:ast:123"]
    id_456 = hash_to_id["test_service:ast:456"]

    assert g_out.nodes[id_123]["semantic_hash"] == "test_service:ast:123"
    assert g_out.nodes[id_123]["metadata"] == {"key": "value"}
    assert g_out.nodes[id_123]["clone_hash"] == "c1"

    # Verify edges
    assert g_out.has_edge(id_123, id_456)
    edge_data = g_out.edges[id_123, id_456]
    assert edge_data["type"] == "CALLS"
    assert edge_data["metadata"] == {"weight": 1}

def test_load_ignores_tombstoned_nodes(repo):
    """Test that load_from_db skips nodes with is_active=0."""
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    repo.flush_to_db(g_in)

    # Manually tombstone it
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute("UPDATE nodes SET is_active=0;")

    g_out, hash_to_id = repo.load_from_db()

    assert len(g_out.nodes) == 0
    assert "test_service:ast:123" not in hash_to_id

def test_load_ignores_ghost_nodes(repo):
    """Test that load_from_db ignores lazy targets that were never resolved."""
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    g_in.add_edge("test_service:ast:123", "test_service:ast:GHOST", type="CALLS", metadata={})
    repo.flush_to_db(g_in)

    g_out, _hash_to_id = repo.load_from_db()

    # The GHOST node is inserted as is_active=0 by flush_to_db.
    # Therefore, it should NOT be in the loaded graph.
    assert len(g_out.nodes) == 1
    # Because the edge target is missing, the edge should be dropped during load!
    assert len(g_out.edges) == 0

def test_load_corrupted_node_metadata(repo):
    """[Hostile] Test load_from_db recovers from invalid node JSON metadata."""
    # Manually insert invalid JSON into DB
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute('''
            INSERT INTO nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("test_service:ast:bad_node", "c1", "file1", "test_service", "pkg1", 1, "INVALID_JSON_STRING"))

    g_out, hash_to_id = repo.load_from_db()

    # It should not crash, and should load the node with empty metadata {}
    assert len(g_out.nodes) == 1
    node_id = hash_to_id["test_service:ast:bad_node"]
    assert g_out.nodes[node_id]["metadata"] == {}

def test_load_corrupted_edge_metadata(repo):
    """[Hostile] Test load_from_db recovers from invalid edge JSON metadata."""
    # Insert two valid nodes, but a corrupted edge
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute('''
            INSERT INTO nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("test_service:ast:1", "c1", "f1", "test_service", "p1", 1, "{}"))
        conn.execute('''
            INSERT INTO nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("test_service:ast:2", "c1", "f1", "test_service", "p1", 1, "{}"))

        # Get their IDs
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM nodes ORDER BY id")
        rows = cursor.fetchall()
        id1, id2 = rows[0][0], rows[1][0]

        # Insert corrupted edge
        conn.execute('''
            INSERT INTO edges (source_id, target_id, type, metadata)
            VALUES (?, ?, ?, ?)
        ''', (id1, id2, "CALLS", "INVALID_JSON_EDGE"))

    g_out, _hash_to_id = repo.load_from_db()

    assert len(g_out.edges) == 1
    edge_data = g_out.edges[id1, id2]
    assert edge_data["metadata"] == {}
