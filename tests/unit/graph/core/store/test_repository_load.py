# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import sqlite3

import networkx as nx
import pytest

from specweaver.graph.core.engine.models import EDGE_KIND_ATTR
from specweaver.graph.core.store.repository import SqliteGraphRepository, _edge_kind


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "graph.db"
    return SqliteGraphRepository(str(db_path), validated_service_name="test_service")


def test_load_happy_path(repo):
    """Test loading a basic graph."""
    g_in = nx.DiGraph()
    g_in.add_node(
        "test_service:ast:123",
        file_id="file1",
        package_name="pkg1",
        metadata={"key": "value"},
        clone_hash="c1",
    )
    g_in.add_node(
        "test_service:ast:456",
        file_id="file1",
        package_name="pkg1",
        metadata={"key": "value2"},
        clone_hash="c2",
    )
    g_in.add_edge(
        "test_service:ast:123", "test_service:ast:456", kind="CALLS", metadata={"weight": 1}
    )

    repo.persist_semantic_digraph(g_in)

    g_out = repo.load_from_db()

    assert isinstance(g_out, nx.DiGraph)
    assert len(g_out.nodes) == 2
    assert len(g_out.edges) == 1

    # Internal NetworkX nodes should use semantic hashes
    node_ids = list(g_out.nodes())
    assert isinstance(node_ids[0], str)

    # The attributes must be mapped back correctly
    id_123 = "test_service:ast:123"
    id_456 = "test_service:ast:456"

    assert g_out.nodes[id_123]["metadata"] == {"key": "value"}
    assert g_out.nodes[id_123]["clone_hash"] == "c1"

    # Verify edges
    assert g_out.has_edge(id_123, id_456)
    edge_data = g_out.edges[id_123, id_456]
    # Read through `EDGE_KIND_ATTR` and the store's own reader, never through a literal key. This
    # assertion used to name `"type"` -- the COLUMN's name -- and so pinned the very split that
    # made a loaded graph unpersistable: `_edge_kind` refuses an edge carrying no kind.
    assert _edge_kind(id_123, id_456, edge_data) == "CALLS"
    assert EDGE_KIND_ATTR in edge_data
    assert edge_data["metadata"] == {"weight": 1}


def test_load_ignores_tombstoned_nodes(repo):
    """Test that load_from_db skips nodes with is_active=0."""
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    repo.persist_semantic_digraph(g_in)

    # Manually tombstone it
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute("UPDATE graph_nodes SET is_active=0;")

    g_out = repo.load_from_db()

    assert len(g_out.nodes) == 0
    assert "test_service:ast:123" not in g_out.nodes


def test_load_keeps_ghost_edges(repo):
    """A reload holds the unresolved dependencies the build found.

    Proves: TECH-068 FR-12

    **This test asserted the opposite until 2026-08-22**, and its own words say why that was
    wrong. It described the target as a *"lazy target that was never resolved"* — the
    `target_id = -1` dangling-edge model that `AD-4` retired in this same ticket, and which
    `ontology_mapping.md` no longer describes because the code cannot express it. Ghosts are not
    placeholders awaiting a later pass; there is no later pass. They are the answer.

    Its reasoning was also circular: *"the GHOST node is inserted as is_active=0, THEREFORE it
    should not be in the loaded graph"* derives the requirement from the mechanism, so it could
    never have failed for a reason anybody chose.

    What it cost: a graph read back out of the database said "nothing depends on this" about every
    dependency outside the parsed set — the exact confusion `FR-12` exists to remove, and the one
    the design's "this ticket makes the graph true" rules out.
    """
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    g_in.add_edge(
        "test_service:ast:123", "test_service:ast:GHOST", kind="CALLS", metadata={"raw": "mystery"}
    )
    repo.persist_semantic_digraph(g_in)

    g_out = repo.load_from_db()

    assert g_out.has_edge("test_service:ast:123", "test_service:ast:GHOST")
    assert g_out.edges["test_service:ast:123", "test_service:ast:GHOST"]["metadata"] == {
        "raw": "mystery"
    }


def test_a_reloaded_ghost_carries_no_attributes(repo):
    """Boundary: the in-memory convention for a ghost is a node with NO attributes.

    `_extract_nodes` decides what is a ghost by `if not data`, so a ghost restored with attributes
    would be written back as an ACTIVE node — resurrecting every unresolved target as though the
    build had found it. Left to `add_edge`, which creates a missing node bare, the two halves agree.
    """
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    g_in.add_edge("test_service:ast:123", "test_service:ast:GHOST", kind="CALLS", metadata={})
    repo.persist_semantic_digraph(g_in)

    g_out = repo.load_from_db()

    assert g_out.nodes["test_service:ast:GHOST"] == {}


def test_a_reloaded_ghost_is_not_written_back_as_active(repo):
    """Composition: load and persist hold different notions of "ghost" and must agree.

    One reads `is_active`, the other reads "has no attributes". Only the round trip says they mean
    the same thing, and each half's own tests pass either way.
    """
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    g_in.add_edge("test_service:ast:123", "test_service:ast:GHOST", kind="CALLS", metadata={})
    repo.persist_semantic_digraph(g_in)

    repo.persist_semantic_digraph(repo.load_from_db())

    with sqlite3.connect(repo.db_path) as conn:
        resurrected = conn.execute(
            "SELECT count(*) FROM graph_nodes WHERE is_active = 1 AND file_id = ''"
        ).fetchone()[0]
    assert resurrected == 0


def test_load_still_ignores_a_tombstoned_node(repo):
    """Hostile: `is_active = 0` means two things and only `file_id` separates them.

    A ghost carries no file; a tombstone carries the path its file came from. Loading ghosts must
    not smuggle deleted files back in beside them — that would undo `purge_stale_entries` entirely.
    """
    g_in = nx.DiGraph()
    g_in.add_node("test_service:ast:123", file_id="file1", package_name="pkg1", metadata={})
    g_in.add_node("test_service:ast:456", file_id="file2", package_name="pkg1", metadata={})
    g_in.add_edge("test_service:ast:123", "test_service:ast:456", kind="CALLS", metadata={})
    repo.persist_semantic_digraph(g_in)
    repo.purge_stale_entries({"file1"})

    g_out = repo.load_from_db()

    assert "test_service:ast:456" not in g_out.nodes
    assert not g_out.edges


def test_load_corrupted_node_metadata(repo):
    """[Hostile] Test load_from_db recovers from invalid node JSON metadata."""
    # Manually insert invalid JSON into DB
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute(
            """
            INSERT INTO graph_nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "test_service:ast:bad_node",
                "c1",
                "file1",
                "test_service",
                "pkg1",
                1,
                "INVALID_JSON_STRING",
            ),
        )

    g_out = repo.load_from_db()

    # It should not crash, and should load the node with empty metadata {}
    assert len(g_out.nodes) == 1
    node_id = "test_service:ast:bad_node"
    assert g_out.nodes[node_id]["metadata"] == {}


def test_load_corrupted_edge_metadata(repo):
    """[Hostile] Test load_from_db recovers from invalid edge JSON metadata."""
    # Insert two valid nodes, but a corrupted edge
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute(
            """
            INSERT INTO graph_nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            ("test_service:ast:1", "c1", "f1", "test_service", "p1", 1, "{}"),
        )
        conn.execute(
            """
            INSERT INTO graph_nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            ("test_service:ast:2", "c1", "f1", "test_service", "p1", 1, "{}"),
        )

        # Get their IDs
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM graph_nodes ORDER BY id")
        rows = cursor.fetchall()
        id1, id2 = rows[0][0], rows[1][0]

        # Insert corrupted edge
        conn.execute(
            """
            INSERT INTO graph_edges (source_id, target_id, type, metadata)
            VALUES (?, ?, ?, ?)
        """,
            (id1, id2, "CALLS", "INVALID_JSON_EDGE"),
        )

    g_out = repo.load_from_db()

    assert len(g_out.edges) == 1

    # We must retrieve by semantic hash keys, but here we only have the integer IDs.
    # We can retrieve the semantic hashes by fetching them.
    with sqlite3.connect(repo.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT semantic_hash FROM graph_nodes WHERE id=?", (id1,))
        hash1 = cursor.fetchone()[0]
        cursor.execute("SELECT semantic_hash FROM graph_nodes WHERE id=?", (id2,))
        hash2 = cursor.fetchone()[0]

    edge_data = g_out.edges[hash1, hash2]
    assert edge_data["metadata"] == {}
