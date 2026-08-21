# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An edge the rebuilt graph no longer holds does not survive in the database.

Proves: TECH-068 FR-16

`persist_semantic_digraph` only ever `INSERT OR REPLACE`s; nothing deletes. The in-memory engine
does drop stale edges on re-ingest, so the graph is right in memory and wrong on disk from the next
`load_from_db` onward. Invisible while `CONTAINS` was the only kind — it dies with its symbol, and
`purge_stale_entries` tombstones the node. Once `CALLS` lands, every deleted or renamed call leaves
a permanent phantom dependency and the set only grows.

Deletion is scoped to the nodes in the current write. `graph_edges` carries no `service_name` of its
own, so a global diff would delete another service's edges; node ids are what carry the service.

The tier is integration: the claim is about what survives a persist cycle, which only a real
database can answer.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import EdgeKind, GraphEdge, GraphNode, NodeKind
from specweaver.graph.core.store.repository import SqliteGraphRepository

if TYPE_CHECKING:
    from pathlib import Path

    import networkx as nx


def _graph(*edges: tuple[str, str], nodes: tuple[str, ...] = ()) -> nx.DiGraph:
    engine = InMemoryGraphEngine()
    for name in {*nodes, *(n for e in edges for n in e)}:
        engine.upsert_node(
            GraphNode(semantic_hash=name, kind=NodeKind.PROCEDURE, name=name, file_id=f"{name}.py")
        )
    for source, target in edges:
        engine.upsert_edge(GraphEdge(source_hash=source, target_hash=target, kind=EdgeKind.CALLS))
    return engine.export_semantic_digraph()


def _edges(db: str) -> set[tuple[str, str]]:
    rows = (
        sqlite3.connect(db)
        .cursor()
        .execute(
            "SELECT n1.semantic_hash, n2.semantic_hash FROM graph_edges e "
            "JOIN graph_nodes n1 ON n1.id = e.source_id JOIN graph_nodes n2 ON n2.id = e.target_id"
        )
    )
    return {(a, b) for a, b in rows}


def test_a_removed_edge_does_not_survive_a_second_persist(tmp_path: Path) -> None:
    """Happy path: the call was deleted from the source, so the dependency is gone."""
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b")))
    assert _edges(db) == {("a", "b")}
    repo.persist_semantic_digraph(_graph(nodes=("a", "b")))
    assert _edges(db) == set()


def test_only_the_removed_edge_goes(tmp_path: Path) -> None:
    """Happy path: deletion is a difference, not a purge."""
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b"), ("a", "c")))
    repo.persist_semantic_digraph(_graph(("a", "c"), nodes=("b",)))
    assert _edges(db) == {("a", "c")}


def test_a_graph_with_no_edges_at_all_clears_them(tmp_path: Path) -> None:
    """Boundary: an empty edge set is a real state, not a no-op guard."""
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b"), ("b", "c")))
    repo.persist_semantic_digraph(_graph(nodes=("a", "b", "c")))
    assert _edges(db) == set()


def test_many_removed_edges_are_all_deleted(tmp_path: Path) -> None:
    """Boundary: past the 5,000-row chunk RT-4 requires, so the delete must chunk too."""
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    names = tuple(f"n{i}" for i in range(6000))
    repo.persist_semantic_digraph(_graph(*((names[0], n) for n in names[1:])))
    assert len(_edges(db)) == 5999
    repo.persist_semantic_digraph(_graph(nodes=names))
    assert _edges(db) == set()


def test_edges_between_nodes_this_write_never_saw_survive(tmp_path: Path) -> None:
    """Graceful degradation: a partial build must not delete what it cannot see.

    `build_target` persists whatever the engine holds. A build scoped to one directory must not
    treat the rest of the repository's edges as removed.
    """
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b"), ("x", "y")))
    repo.persist_semantic_digraph(_graph(("a", "b")))
    assert ("x", "y") in _edges(db)


def test_another_services_edges_are_untouched(tmp_path: Path) -> None:
    """Hostile: `graph_edges` has no service column, so scoping rests entirely on node ids."""
    db = str(tmp_path / "g.db")
    SqliteGraphRepository(db, "other").persist_semantic_digraph(_graph(("p", "q")))
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b")))
    repo.persist_semantic_digraph(_graph(nodes=("a", "b")))
    assert ("p", "q") in _edges(db)


def test_a_purged_file_leaves_no_edges_behind(tmp_path: Path) -> None:
    """Composition: node tombstoning and edge deletion must agree, not fight.

    `purge_stale_entries` tombstones the nodes of a vanished file. Its edges are this FR's job —
    each half is self-consistent and the pair is the claim.
    """
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b")))
    repo.purge_stale_entries({"a.py"})
    repo.persist_semantic_digraph(_graph(nodes=("a",)))
    assert _edges(db) == set()
