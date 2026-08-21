# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The kind an edge was created with is the kind the database holds.

Proves: TECH-068 FR-14

The engine writes the kind onto the networkx edge under `kind` (`core.py`); the store reads `type`
and falls back to `"CALLS"` when it is absent (`repository.py`). The keys differ, so the fallback
fires on every edge ever persisted. Measured 2026-08-21 on a real build of `src/specweaver/graph`:
**108 edges stored, all typed `CALLS`, every one of them a `CONTAINS` edge.**

The tier is integration because the claim is the seam. Each half is self-consistent — that is
exactly why twenty-two green tests never saw it, and why the existing store tests hand-build their
graph with the store's own key instead of going through the engine. A test that builds the edge
itself reproduces the blind spot rather than catching it.
"""

from __future__ import annotations

import copy
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


def _engine_with(kind: EdgeKind) -> InMemoryGraphEngine:
    engine = InMemoryGraphEngine()
    engine.upsert_node(
        GraphNode(semantic_hash="src", kind=NodeKind.FILE, name="a.py", file_id="a.py")
    )
    engine.upsert_node(
        GraphNode(semantic_hash="dst", kind=NodeKind.PROCEDURE, name="f", file_id="a.py")
    )
    engine.upsert_edge(GraphEdge(source_hash="src", target_hash="dst", kind=kind))
    return engine


def _stored_types(db: str) -> list[str]:
    return [r[0] for r in sqlite3.connect(db).cursor().execute("SELECT type FROM graph_edges")]


def test_a_contains_edge_is_stored_as_contains(tmp_path: Path) -> None:
    """Happy path. Today this stores `CALLS`, which is the defect."""
    db = str(tmp_path / "g.db")
    SqliteGraphRepository(db, "svc").persist_semantic_digraph(
        _engine_with(EdgeKind.CONTAINS).export_semantic_digraph()
    )
    assert _stored_types(db) == ["CONTAINS"]


@pytest.mark.parametrize("kind", list(EdgeKind))
def test_every_declared_kind_round_trips(kind: EdgeKind, tmp_path: Path) -> None:
    """Boundary: the ontology declares nine kinds and each must survive the seam."""
    db = str(tmp_path / f"{kind.value}.db")
    SqliteGraphRepository(db, "svc").persist_semantic_digraph(
        _engine_with(kind).export_semantic_digraph()
    )
    assert _stored_types(db) == [kind.value]


def test_an_edge_with_no_kind_is_refused(tmp_path: Path) -> None:
    """Graceful degradation: a missing kind is a defect to report, never one to invent.

    The store currently substitutes `"CALLS"`, which fabricates a dependency that reads exactly like
    a real one.
    """
    graph = copy.deepcopy(_engine_with(EdgeKind.CONTAINS).export_semantic_digraph())
    graph.edges["src", "dst"].clear()
    with pytest.raises(ValueError, match="src"):
        SqliteGraphRepository(str(tmp_path / "g.db"), "svc").persist_semantic_digraph(graph)


def test_an_edge_whose_kind_is_not_a_declared_kind_is_refused(tmp_path: Path) -> None:
    """Hostile input: a string that is not an `EdgeKind` member must not reach the column."""
    graph = copy.deepcopy(_engine_with(EdgeKind.CONTAINS).export_semantic_digraph())
    graph.edges["src", "dst"][EDGE_KIND_ATTR] = "NOT_A_KIND"
    with pytest.raises(ValueError, match="NOT_A_KIND"):
        SqliteGraphRepository(str(tmp_path / "g.db"), "svc").persist_semantic_digraph(graph)


def test_the_export_path_and_the_store_agree_on_the_key(tmp_path: Path) -> None:
    """The two halves must name the attribute identically, or they drift apart again in silence.

    `TECH-058`'s asymmetry was plainly visible in both files and in neither test.
    """
    graph = _engine_with(EdgeKind.IMPORTS).export_semantic_digraph()
    attrs = graph.edges["src", "dst"]
    db = str(tmp_path / "g.db")
    SqliteGraphRepository(db, "svc").persist_semantic_digraph(graph)
    assert _stored_types(db) == [attrs[EDGE_KIND_ATTR]]


def test_the_engine_and_the_store_name_the_attribute_identically() -> None:
    """The two halves cannot drift apart again, because there is only one name.

    Proves: TECH-068 FR-14

    This is the guardrail shipped with the fix. The defect was not a wrong value — it was two
    modules independently choosing what to call the same thing, each self-consistent, neither
    able to see the other. A shared constant removes the possibility rather than watching for it.

    The assertion deliberately names no key of its own: it takes the attribute dict the engine
    produced and asks the store's own reader to interpret it. Renaming either side breaks it.
    """
    from specweaver.graph.core.store.repository import _edge_kind

    attrs = _engine_with(EdgeKind.EXTENDS).export_semantic_digraph().edges["src", "dst"]
    assert EDGE_KIND_ATTR in attrs
    assert _edge_kind("src", "dst", attrs) == EdgeKind.EXTENDS.value
