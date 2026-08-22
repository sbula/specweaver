# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A graph read back out of the database can be written to it again.

Proves: TECH-068 FR-14

`FR-14` says the persistence fallback never supplies a kind for an edge that omits one, and `SF-01`
delivered half of that: the engine writes the kind under `EDGE_KIND_ATTR` and the store now refuses
an edge that carries none, instead of defaulting it to `CALLS`.

`load_from_db` is the other half and was not looked at. It restores the kind under `type` — the name
the COLUMN uses — so every edge it returns is one the store will now refuse. Persist and load are
the two halves of one round trip, each self-consistent, and that is the same shape as the split
between the engine and the store this ticket exists to fix.

Nothing crashes on the shipped path today only by accident: `purge_stale_entries` tombstones every
file outside the current target and `load_from_db` filters `is_active = 1`, so no loaded edge
survives long enough to be re-persisted. `TECH-070` is an incremental rebuild — keeping unchanged
files loaded rather than re-ingesting them is the whole point of it, and that is exactly the state
these tests describe.

The tier is integration: the claim is that two halves of a real SQLite round trip agree, which
neither half can answer alone.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import (
    EDGE_KIND_ATTR,
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
)
from specweaver.graph.core.store.repository import SqliteGraphRepository

if TYPE_CHECKING:
    from pathlib import Path

    import networkx as nx

pytestmark = pytest.mark.integration


def _graph(*edges: tuple[str, str, EdgeKind], nodes: tuple[str, ...] = ()) -> nx.DiGraph:
    engine = InMemoryGraphEngine()
    for name in {*nodes, *(n for e in edges for n in e[:2])}:
        engine.upsert_node(
            GraphNode(semantic_hash=name, kind=NodeKind.PROCEDURE, name=name, file_id=f"{name}.py")
        )
    for source, target, kind in edges:
        engine.upsert_edge(GraphEdge(source_hash=source, target_hash=target, kind=kind))
    return engine.export_semantic_digraph()


def _stored(db: str) -> set[tuple[str, str, str]]:
    rows = (
        sqlite3.connect(db)
        .cursor()
        .execute(
            "SELECT n1.semantic_hash, n2.semantic_hash, e.type FROM graph_edges e "
            "JOIN graph_nodes n1 ON n1.id = e.source_id JOIN graph_nodes n2 ON n2.id = e.target_id"
        )
    )
    return {(a, b, t) for a, b, t in rows}


def test_a_loaded_graph_can_be_persisted_again(tmp_path: Path) -> None:
    """Happy path: persist, load, persist. The second write must not refuse the first one's work."""
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b", EdgeKind.CALLS)))

    repo.persist_semantic_digraph(repo.load_from_db())

    assert _stored(db) == {("a", "b", "CALLS")}


@pytest.mark.parametrize("kind", list(EdgeKind))
def test_every_declared_kind_survives_the_full_round_trip(kind: EdgeKind, tmp_path: Path) -> None:
    """Boundary: the ontology declares nine kinds and a reload must not flatten any of them."""
    db = str(tmp_path / f"{kind.value}.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b", kind)))

    repo.persist_semantic_digraph(repo.load_from_db())

    assert _stored(db) == {("a", "b", kind.value)}


def test_a_graph_with_no_edges_round_trips(tmp_path: Path) -> None:
    """Boundary: an empty edge set is a real state, and it must not become an error either."""
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(nodes=("a", "b")))

    repo.persist_semantic_digraph(repo.load_from_db())

    assert _stored(db) == set()


def test_an_edge_loaded_but_never_re_ingested_still_persists(tmp_path: Path) -> None:
    """Graceful degradation: the incremental state `TECH-070` is built to produce.

    A rebuild that re-ingests only the changed file leaves every other edge exactly as
    `load_from_db` returned it. Those edges are then handed straight back to the store, having
    passed through nothing that would re-stamp them.
    """
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b", EdgeKind.IMPORTS)))

    engine = InMemoryGraphEngine()
    engine.load_semantic_digraph(repo.load_from_db())
    engine.upsert_node(
        GraphNode(semantic_hash="c", kind=NodeKind.PROCEDURE, name="c", file_id="c.py")
    )
    engine.upsert_edge(GraphEdge(source_hash="a", target_hash="c", kind=EdgeKind.CALLS))
    repo.persist_semantic_digraph(engine.export_semantic_digraph())

    assert _stored(db) == {("a", "b", "IMPORTS"), ("a", "c", "CALLS")}


def test_a_stored_kind_outside_the_ontology_is_named_when_it_is_refused(tmp_path: Path) -> None:
    """Hostile: a row written by an older build, or by hand, must be reported rather than guessed.

    The refusal already exists. What it must not do is report the value as `None`, which is what a
    reader sees when the loader silently dropped the kind on the way through instead of carrying a
    bad one.
    """
    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b", EdgeKind.CALLS)))
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE graph_edges SET type = 'RETIRED_KIND'")

    with pytest.raises(ValueError, match="RETIRED_KIND"):
        repo.persist_semantic_digraph(repo.load_from_db())


def test_the_loader_and_the_store_name_the_attribute_identically(tmp_path: Path) -> None:
    """The agreement test: what the loader produces is what the store's own reader consumes.

    It names no key of its own. `EDGE_KIND_ATTR` is the single name, and this asks the store's
    reader to interpret the loader's output — so renaming either side breaks it, which is the one
    thing the engine/store split proved nobody would otherwise notice.
    """
    from specweaver.graph.core.store.repository import _edge_kind

    db = str(tmp_path / "g.db")
    repo = SqliteGraphRepository(db, "svc")
    repo.persist_semantic_digraph(_graph(("a", "b", EdgeKind.EXTENDS)))

    attrs = repo.load_from_db().edges["a", "b"]

    assert EDGE_KIND_ATTR in attrs
    assert _edge_kind("a", "b", attrs) == EdgeKind.EXTENDS.value
