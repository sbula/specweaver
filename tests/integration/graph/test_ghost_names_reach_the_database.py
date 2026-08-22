# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The unresolved name the mapper recorded is the one a reader gets back out of the database.

Proves: TECH-068 FR-12

Four things have to agree for `FR-12` to mean anything, and each was written by a different
sub-feature: the mapper puts the name on the edge, `upsert_edge` carries it onto the graph,
`persist_semantic_digraph` writes the column, and `load_from_db` restores it. Every one of them
passes its own tests while the chain delivers `{}` — which is exactly what it did, because
`upsert_edge` never wrote the attribute the other three were already handling.

The tier is integration because the claim is the chain. A unit test of the mapper proves the mapper.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pytest

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import METADATA_MAX_BYTES
from specweaver.graph.core.store.repository import SqliteGraphRepository
from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _build_and_persist(tmp_path: Path, files: dict[str, str]) -> str:
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    engine = InMemoryGraphEngine()
    GraphBuilder(engine=engine, parser=extract_ast_dict).ingest_target(tmp_path)
    db = str(tmp_path / "g.db")
    SqliteGraphRepository(db, "svc").persist_semantic_digraph(engine.export_semantic_digraph())
    return db


def _raw_names(db: str) -> set[str]:
    rows = sqlite3.connect(db).cursor().execute("SELECT metadata FROM graph_edges")
    return {json.loads(m or "{}").get("raw") for m in (r[0] for r in rows)} - {None}


def test_an_unresolved_call_is_named_in_the_database(tmp_path: Path) -> None:
    """Happy path: the whole chain, ending at a column a reader can query."""
    db = _build_and_persist(tmp_path, {"a.py": "def f():\n    mystery_call()\n"})

    assert "mystery_call" in _raw_names(db)


def test_two_different_unknowns_are_told_apart(tmp_path: Path) -> None:
    """Happy path, and the reason the requirement exists.

    Before this, both were a hash with no name attached — a reader could see two ghosts and had no
    way to learn which was `os.getcwd` and which was `mystery_call`.
    """
    db = _build_and_persist(
        tmp_path, {"a.py": "import os\n\n\ndef f():\n    os.getcwd()\n    mystery_call()\n"}
    )

    names = _raw_names(db)
    assert {"getcwd", "mystery_call"} <= names, names


def test_a_resolved_edge_is_still_anonymous(tmp_path: Path) -> None:
    """Boundary: the control. If every edge carried a name the field would say nothing."""
    db = _build_and_persist(
        tmp_path, {"a.py": "def helper():\n    pass\n\n\ndef caller():\n    helper()\n"}
    )

    assert "helper" not in _raw_names(db)


def test_a_reload_drops_ghost_edges_today(tmp_path: Path) -> None:
    """The recorded limit of `FR-12`, asserted so it cannot change without somebody noticing.

    `load_from_db` filters both endpoints on `is_active = 1` and a ghost is stored with `0`, so a
    reloaded graph holds none of them — the raw name is in the column and does not survive the trip
    back into memory. `test_load_ignores_ghost_nodes` calls that deliberate, and it is: a build that
    re-ingests every file rebuilds its ghosts, so nothing is lost today.

    This test exists so the day it stops being true is loud. `TECH-070` is that day: an incremental
    rebuild leaves unchanged files loaded rather than re-ingested, and their ghost edges would go
    missing on every pass. Overturning a tested decision is `T-DIVERGE` and belongs to the user, so
    this asserts the present behaviour rather than the behaviour somebody might prefer.
    """
    db = _build_and_persist(tmp_path, {"a.py": "def f():\n    mystery_call()\n"})

    reloaded = SqliteGraphRepository(db, "svc").load_from_db()

    carried = {
        data.get("metadata", {}).get("raw") for _u, _v, data in reloaded.edges(data=True)
    } - {None}
    assert carried == set(), (
        "a ghost edge survived a reload — if that is now intended, `test_load_ignores_ghost_nodes` "
        "and this test both need revisiting, and TECH-070 gets simpler"
    )
    assert "mystery_call" in _raw_names(db), "the database must still hold what the reload drops"


def test_an_absurd_identifier_reaches_the_column_truncated(tmp_path: Path) -> None:
    """Graceful degradation: `NFR-6` — one pathological file must not abort the build.

    Python's own parser accepts an arbitrarily long identifier, so this is reachable from real
    source rather than only from a hand-built graph.
    """
    huge = "z" * 5000
    db = _build_and_persist(tmp_path, {"a.py": f"def f():\n    {huge}()\n"})

    stored = [
        m for m in (r[0] for r in sqlite3.connect(db).execute("SELECT metadata FROM graph_edges"))
    ]
    assert any(json.loads(m or "{}").get("raw", "").startswith("zzz") for m in stored)
    assert all(len((m or "").encode("utf-8")) <= METADATA_MAX_BYTES for m in stored)


def test_a_hostile_identifier_survives_the_json_column(tmp_path: Path) -> None:
    """Hostile: the metadata is JSON on the way in and on the way out.

    A non-ASCII identifier is legal Python, and it is the one that catches a cap counting characters
    where the column counts bytes.
    """
    db = _build_and_persist(tmp_path, {"a.py": "def f():\n    ünïcödé_çall()\n"})

    assert "ünïcödé_çall" in _raw_names(db)
