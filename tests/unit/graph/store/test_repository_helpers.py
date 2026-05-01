import sqlite3

import networkx as nx
import pytest

from specweaver.graph.store.repository import SqliteGraphRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "graph.db"
    return SqliteGraphRepository(str(db_path), validated_service_name="test_service")

def test_get_all_file_hashes(repo):
    """Test retrieving distinct file IDs and their clone hashes."""
    g = nx.DiGraph()
    # file1 has clone_hash c1
    g.add_node("test_service:ast:1", file_id="file1", clone_hash="c1")
    g.add_node("test_service:ast:2", file_id="file1", clone_hash="c1")
    # file2 has clone_hash c2
    g.add_node("test_service:ast:3", file_id="file2", clone_hash="c2")
    # file3 has no clone hash
    g.add_node("test_service:ast:4", file_id="file3")

    repo.flush_to_db(g)

    # Also add a node for a different service to ensure isolation
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute("INSERT INTO nodes (semantic_hash, file_id, clone_hash, service_name, is_active) VALUES (?, ?, ?, ?, ?)",
                     ("other_service:ast:5", "file4", "c4", "other_service", 1))

    file_hashes = repo.get_all_file_hashes()

    assert file_hashes == {
        "file1": "c1",
        "file2": "c2",
        "file3": ""
    }
    assert "file4" not in file_hashes

def test_purge_file(repo):
    """Test tombstoning all nodes for a specific file."""
    g = nx.DiGraph()
    g.add_node("test_service:ast:1", file_id="file1")
    g.add_node("test_service:ast:2", file_id="file2")
    repo.flush_to_db(g)

    repo.purge_file("file1")

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT semantic_hash, is_active FROM nodes ORDER BY semantic_hash")
        rows = cursor.fetchall()

        assert rows == [
            ("test_service:ast:1", 0),  # Tombstoned
            ("test_service:ast:2", 1)   # Active
        ]

def test_full_graph_lifecycle(repo):
    """Test the complete Happy Path lifecycle requested by the user: Store, Update, Delete, Read."""
    # 1. Store a complete graph
    g1 = nx.DiGraph()
    g1.add_node("test_service:ast:1", file_id="file1", clone_hash="v1")
    g1.add_node("test_service:ast:2", file_id="file2", clone_hash="v1")
    g1.add_edge("test_service:ast:1", "test_service:ast:2", type="CALLS")
    repo.flush_to_db(g1)

    g_out, _ = repo.load_from_db()
    assert len(g_out.nodes) == 2
    assert len(g_out.edges) == 1

    # 2. Update it (Partial graph flush for file1 only, simulate a file change)
    g2 = nx.DiGraph()
    # Node 1 changes its hash to 1_new, node 2 is unaffected (lazy target)
    g2.add_node("test_service:ast:1_new", file_id="file1", clone_hash="v2")
    g2.add_edge("test_service:ast:1_new", "test_service:ast:2", type="CALLS")

    # In a real orchestrator, we would purge file1 before flushing its new state
    repo.purge_file("file1")
    repo.flush_to_db(g2)

    # 3. Read it back
    g_out_2, id_map = repo.load_from_db()
    assert len(g_out_2.nodes) == 2 # 1_new and 2
    assert "test_service:ast:1_new" in id_map
    assert "test_service:ast:1" not in id_map # Tombstoned

    # 4. Delete nodes (simulate deleting file2)
    repo.purge_file("file2")

    # 5. Read it back
    g_out_3, _id_map_3 = repo.load_from_db()
    assert len(g_out_3.nodes) == 1 # Only 1_new is left
    assert len(g_out_3.edges) == 0 # Edge should be gone since target is tombstoned!
