# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw graph build` writes real, typed dependency edges to the database.

Proves: TECH-068 FR-3, FR-14, FR-16

This ticket is about edges, and until now nothing anywhere asserted one had reached disk. The two
halves were each proven and the pair was not:

* `test_every_language_reaches_the_graph.py` drives real parsers into the mapper and the engine, and
  stops there — the graph it inspects is in memory and is never persisted.
* `test_edge_kind_survives_persist.py` drives the engine into the store, from hand-built nodes. A
  test that builds the edge itself cannot see a mapper that stopped producing one.
* `test_real_extraction_to_graph.py` is the only test that runs the real `build_target`, and every
  assertion in it counts `graph_nodes`. Not one touches `graph_edges`.

So `_clear_edges_of` is scoped to `set(hash_to_id.values())` — a set only a real write fills — and
nothing had ever filled it from real parser output.

The tier is e2e: this is the shipped command, run as a user runs it, against a tree on disk. Nothing
is mocked and nothing is hand-built.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.graph.core.engine.models import EdgeKind
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

runner = CliRunner()

# Two languages, one of them not Python, with every edge kind this ticket ships present in the
# source: a call, an import, a class hierarchy, and the containment that comes free.
_TREE = {
    "src/orders.py": (
        "from .models import Order\n\n\n"
        "class OrderService(Order):\n"
        "    def submit(self):\n"
        "        validate()\n\n\n"
        "def validate():\n"
        "    pass\n"
    ),
    "src/models.py": "class Order:\n    pass\n",
    "src/Runner.java": (
        "public class Runner extends Base {\n    public void go() { helper(); }\n}\n"
    ),
}


def _project(root: Path, files: dict[str, str]) -> Path:
    (root / ".specweaver").mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _build(project: Path, target: str = "src") -> None:
    result = runner.invoke(
        app, ["graph", "build", str(project / target), "--project-path", str(project)]
    )
    # The exit code is checked for the message it carries on failure, never as the claim: the
    # assertions that matter are the persisted rows below.
    assert result.exit_code == 0, result.output


def _edge_rows(project: Path) -> list[tuple[str, str, str]]:
    """`(source file, target file, kind)` for every persisted edge ROW, ghosts included.

    A list, not a set. `graph_edges`' primary key is `(source_id, target_id, type)`, so an edge
    whose kind changed inserts a SECOND row rather than replacing the first — and a set comparison
    collapses exactly the duplication `_clear_edges_of` exists to prevent. Callers that want
    identity use this; callers that want membership take `set(...)` of it explicitly.
    """
    with sqlite3.connect(project / ".specweaver" / "graph.db") as conn:
        return [
            (a or "", b or "", kind)
            for a, b, kind in conn.execute(
                "SELECT n1.file_id, n2.file_id, e.type FROM graph_edges e "
                "JOIN graph_nodes n1 ON n1.id = e.source_id "
                "JOIN graph_nodes n2 ON n2.id = e.target_id"
            )
        ]


def _edges(project: Path) -> set[tuple[str, str, str]]:
    """The distinct edges on disk. Use `_edge_rows` when duplication is part of the claim."""
    return set(_edge_rows(project))


def test_a_real_build_persists_typed_edges(tmp_path: Path) -> None:
    """Happy path, and the ticket's central claim: edges exist on disk, carrying their own kinds."""
    project = _project(tmp_path, _TREE)

    _build(project)

    kinds = {kind for _s, _t, kind in _edges(project)}
    assert EdgeKind.CALLS.value in kinds, f"no CALLS edge reached the database: {kinds}"
    assert EdgeKind.IMPORTS.value in kinds, f"no IMPORTS edge reached the database: {kinds}"
    assert EdgeKind.EXTENDS.value in kinds, f"no EXTENDS edge reached the database: {kinds}"
    assert EdgeKind.CONTAINS.value in kinds, f"no CONTAINS edge reached the database: {kinds}"


def test_the_persisted_kinds_are_not_all_one_kind(tmp_path: Path) -> None:
    """Boundary: the defect this replaces stored 108 edges, every one of them typed `CALLS`.

    An assertion that some kind is present passes perfectly against a store that stamps every row
    with it. The claim is that the kinds are DISTINGUISHED, so the count is what says so.
    """
    project = _project(tmp_path, _TREE)

    _build(project)

    kinds = {kind for _s, _t, kind in _edges(project)}
    assert len(kinds) >= 4, f"the kinds collapsed to {kinds}"


def test_the_import_edge_points_at_the_file_it_names(tmp_path: Path) -> None:
    """Boundary: a resolved import must reach the collected file, not a ghost.

    `orders.py` imports `.models`, which the same build collected. A ghost target here would mean
    resolution silently failed while the edge count stayed identical.
    """
    project = _project(tmp_path, _TREE)

    _build(project)

    imports = {(s, t) for s, t, kind in _edges(project) if kind == EdgeKind.IMPORTS.value}
    assert any(s.endswith("orders.py") and t.endswith("models.py") for s, t in imports), (
        f"the relative import did not resolve to the collected file: {imports}"
    )


def test_the_extends_edge_points_at_the_class_it_names(tmp_path: Path) -> None:
    """Boundary: a resolved supertype must reach the collected file too.

    `OrderService(Order)` and `class Order` are in the same build, so this edge resolves. Asserting
    only that some `EXTENDS` row exists is weaker than what the code does: a ghost-targeted
    `EXTENDS` -- which `Runner extends Base` also produces here, since `Base` is nowhere --
    satisfies that identically.
    """
    project = _project(tmp_path, _TREE)

    _build(project)

    extends = {(s, t) for s, t, kind in _edges(project) if kind == EdgeKind.EXTENDS.value}
    assert any(s.endswith("orders.py") and t.endswith("models.py") for s, t in extends), (
        f"the supertype did not resolve to the collected file: {extends}"
    )


def test_a_second_build_leaves_the_edge_set_identical(tmp_path: Path) -> None:
    """Graceful degradation: rebuilding an unchanged tree must neither grow nor lose the graph.

    This is the pair `_clear_edges_of` and the insert that follows it form. A clear that is too wide
    loses edges; an insert with no clear grows them forever. Both halves have their own tests, and
    only a real second build says the pair agrees.
    """
    project = _project(tmp_path, _TREE)

    _build(project)
    first = sorted(_edge_rows(project))
    _build(project)
    second = sorted(_edge_rows(project))

    # Rows, sorted -- not sets, which would collapse duplicate rows and hide row growth. Measured
    # honestly: neutralising `_clear_edges_of` still kills only the deletion test below, because an
    # UNCHANGED rebuild re-inserts identical primary keys and duplicates nothing. Row identity is a
    # free invariant to assert here; the claim it was meant to protect is proven where the state
    # can actually be built -- `test_stale_edges_are_removed.py`.
    assert second == first, f"a rebuild changed the graph: {set(first) ^ set(second)}"
    assert len(second) == len(first), f"a rebuild duplicated rows: {len(first)} -> {len(second)}"


def test_a_call_deleted_from_the_source_stops_being_a_dependency(tmp_path: Path) -> None:
    """Graceful degradation, through the real command: FR-16 end to end.

    The store's own test proves the delete. This proves a real edit to a real file reaches it —
    the mapper must stop producing the edge AND the store must stop holding it, and each half
    passes its own tests while the pair does nothing.
    """
    project = _project(tmp_path, _TREE)
    _build(project)
    assert any(kind == EdgeKind.CALLS.value for _s, _t, kind in _edges(project))

    (project / "src" / "orders.py").write_text(
        "from .models import Order\n\n\nclass OrderService(Order):\n    def submit(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    _build(project)

    calls = {(s, t) for s, t, kind in _edges(project) if kind == EdgeKind.CALLS.value}
    assert not any(s.endswith("orders.py") for s, _t in calls), (
        f"the deleted call survived: {calls}"
    )


def test_an_unresolved_dependency_says_what_it_could_not_find(tmp_path: Path) -> None:
    """Happy path for FR-12, through the shipped command.

    `Runner extends Base` and `Base` is nowhere in this tree, so the edge points at a ghost. Before
    this, the ghost was a hash and nothing else — a reader could see that something was unresolved
    and had no way to learn what. The name is on the EDGE because the store materialises the ghost
    node from an unknown hash, at which point the name is already gone.
    """
    project = _project(tmp_path, _TREE)

    _build(project)

    with sqlite3.connect(project / ".specweaver" / "graph.db") as conn:
        named = {
            json.loads(m or "{}").get("raw")
            for m in (r[0] for r in conn.execute("SELECT metadata FROM graph_edges"))
        } - {None}

    assert "Base" in named, f"the unresolved supertype was not named: {sorted(named)}"


def test_an_unreadable_file_does_not_cost_the_other_files_their_edges(tmp_path: Path) -> None:
    """Hostile: a directory wearing a source file's name must not take the build down.

    The command catches and exits 1 on any exception, so a raise here would be reported as a clean
    failure rather than as the partial build it should be.
    """
    project = _project(tmp_path, _TREE)
    (project / "src" / "trap.py").mkdir()

    _build(project)

    kinds = {kind for _s, _t, kind in _edges(project)}
    assert EdgeKind.CALLS.value in kinds, f"one unreadable file cost every edge: {kinds}"
