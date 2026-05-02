import sqlite3

import networkx as nx
import pytest

from specweaver.graph.core.store.repository import SqliteGraphRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "graph.db"
    return SqliteGraphRepository(str(db_path), validated_service_name="test_service")

def test_flush_happy_path(repo):
    """Test inserting a basic graph."""
    g = nx.DiGraph()
    g.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={"key": "value"})
    g.add_node("test_service:ast:456", file_id="file1", package_name="pkg1", metadata={"key": "value2"})
    g.add_edge("test_service:ast:123", "test_service:ast:456", type="CALLS", metadata={"weight": 1})

    repo.flush_to_db(g)

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT semantic_hash, file_id, service_name, package_name, metadata, is_active FROM nodes ORDER BY semantic_hash;")
        nodes = cursor.fetchall()

        assert len(nodes) == 2
        assert nodes[0] == ("test_service:ast:123", "file1", "test_service", "pkg1", '{"key": "value"}', 1)
        assert nodes[1] == ("test_service:ast:456", "file1", "test_service", "pkg1", '{"key": "value2"}', 1)

        # Verify edges
        cursor.execute("""
            SELECT n1.semantic_hash, n2.semantic_hash, e.type, e.metadata
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
        """)
        edges = cursor.fetchall()
        assert len(edges) == 1
        assert edges[0] == ("test_service:ast:123", "test_service:ast:456", "CALLS", '{"weight": 1}')

def test_flush_large_graph_chunking(repo):
    """Test chunking logic with 6000 nodes (batch size is 5000)."""
    g = nx.DiGraph()
    for i in range(6000):
        g.add_node(f"test_service:ast:{i}", file_id="file1", package_name="pkg1", metadata={})
        if i > 0:
            g.add_edge(f"test_service:ast:{i-1}", f"test_service:ast:{i}", type="CALLS", metadata={})

    repo.flush_to_db(g)

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nodes;")
        assert cursor.fetchone()[0] == 6000
        cursor.execute("SELECT COUNT(*) FROM edges;")
        assert cursor.fetchone()[0] == 5999

def test_flush_tombstone_recovery(repo):
    """Test that ON CONFLICT DO UPDATE SET is_active=1 resurrects tombstoned nodes."""
    # First, insert a node manually as tombstoned
    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO nodes (semantic_hash, file_id, service_name, package_name, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("test_service:ast:999", "file1", "test_service", "pkg1", 0, '{"old": "data"}'))

    # Now flush the node again from the graph
    g = nx.DiGraph()
    g.add_node("test_service:ast:999", file_id="file1", package_name="pkg1", metadata={"new": "data"}, clone_hash="new_clone")
    repo.flush_to_db(g)

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active, clone_hash, metadata FROM nodes WHERE semantic_hash = 'test_service:ast:999';")
        row = cursor.fetchone()

        assert row[0] == 1  # Resurrected!
        assert row[1] == "new_clone" # clone_hash updated
        assert row[2] == '{"new": "data"}' # Metadata overwritten

def test_flush_lazy_target(repo):
    """Test inserting an edge pointing to a non-existent target node (lazy resolution)."""
    # SQLite FK constraints would usually crash here, but we disabled strict target_id FK.
    # However, source_id has an FK! Wait, source_id exists. What about target_id?
    # Because target_id doesn't exist in nodes table, how does edge get the target_id integer?
    # The flush logic needs to handle this. Since the target node isn't in `nx_graph` (lazy edge),
    # it won't be in the DB.
    # A lazy edge is just an edge to a string semantic hash that isn't in the graph nodes yet.
    # Wait, if target_id is an INTEGER, how do we insert an edge to a non-existent node?
    # We must insert a placeholder (ghost) node for the target to get an ID!
    # Let's test that flush handles this.

    g = nx.DiGraph()
    g.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    g.add_edge("test_service:ast:123", "test_service:ast:GHOST", type="CALLS", metadata={})
    # Notice "test_service:ast:GHOST" is NOT added as a node with metadata.

    repo.flush_to_db(g)

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        # Verify the ghost node was created so the edge has a target
        cursor.execute("SELECT id, is_active FROM nodes WHERE semantic_hash = 'test_service:ast:GHOST';")
        row = cursor.fetchone()
        assert row is not None
        # Ghost nodes might be inserted as is_active=0 or 1, but they exist.

        cursor.execute("SELECT COUNT(*) FROM edges;")
        assert cursor.fetchone()[0] == 1

def test_flush_unserializable_metadata(repo):
    """Test that json.dumps with default=str prevents crashes on unserializable objects."""
    g = nx.DiGraph()
    g.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={"unserializable": set([1, 2, 3])})
    g.add_edge("test_service:ast:123", "test_service:ast:123", type="CALLS", metadata={"unserializable": set([4, 5])})

    repo.flush_to_db(g) # Should not raise InterfaceError

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT metadata FROM nodes WHERE semantic_hash = 'test_service:ast:123';")
        meta = cursor.fetchone()[0]
        assert "{" in meta # Successfully serialized as string

        cursor.execute("SELECT metadata FROM edges WHERE type='CALLS'")
        metadata_str = cursor.fetchone()[0]
        # In json.dumps, a set raises TypeError, so if our default=str caught it, it will be the string repr of a set.
        assert "{" in metadata_str

def test_flush_empty_graph(repo):
    """[Boundary] Flushing an empty graph should not crash and leave DB empty."""
    g = nx.DiGraph()
    repo.flush_to_db(g)

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM nodes")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT count(*) FROM edges")
        assert cursor.fetchone()[0] == 0

def test_flush_prefix_spoofing(repo):
    """Test that GraphRepository silently overwrites the service_name attribute."""
    g = nx.DiGraph()
    g.add_node("hacked_service:ast:123", file_id="file1", package_name="pkg1", metadata={}, service_name="hacked_service")

    repo.flush_to_db(g)

    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        # It should prepend the validated service name to the hash if missing, or replace the service_name column.
        cursor.execute("SELECT semantic_hash, service_name FROM nodes;")
        row = cursor.fetchone()

        # The service_name column MUST be the validated one
        assert row[1] == "test_service"
