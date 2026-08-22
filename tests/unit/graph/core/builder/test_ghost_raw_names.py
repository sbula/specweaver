# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An edge to a GHOST says what it could not resolve.

Proves: TECH-068 FR-12, NFR-5

`FR-12` reads: *emit an edge to a `GHOST` node carrying the unresolved raw name in edge metadata*.
Only the first half was built. The name survives inside the target hash and a hash is one-way, so
`os.getcwd` and `mystery_call` become two indistinguishable ghosts: a reader can see THAT something
is unresolved and never WHAT. Found by the retrospective pre-commit gate on 2026-08-22.

The raw name goes on the EDGE, not the node. `graph_edges` already has a metadata column, and the
store materialises a ghost node from an unknown target hash — at which point the name is already
gone. The edge is the only place that still knows it.

Truncated rather than refused above the RT-25 cap. `GraphNode` raises there, which is right for a
node the caller built; here the string comes from source nobody controls and the raise would happen
inside the mapper where nothing catches it, aborting a whole build over one absurd identifier
(`NFR-6`).
"""

from __future__ import annotations

from specweaver.graph.core.builder.mapper import OntologyMapper
from specweaver.graph.core.engine.models import METADATA_MAX_BYTES
from specweaver.graph.core.engine.ontology import EdgeKind


def _edges(ast: dict, **kw) -> list:
    return OntologyMapper().map_ast_to_nodes("a.py", ast, **kw)[1]


def _of_kind(ast: dict, kind: EdgeKind, **kw) -> list:
    return [e for e in _edges(ast, **kw) if e.kind is kind]


def _module(**extra) -> dict:
    return {"type": "module", "imports": [], "calls": [], "children": [], **extra}


class TestTheNameIsOnTheEdge:
    def test_an_unresolved_call_carries_the_name_it_could_not_find(self) -> None:
        """Happy path: the whole point of the requirement."""
        edges = _of_kind(_module(calls=["mystery_call"]), EdgeKind.CALLS)

        assert [e.metadata.get("raw") for e in edges] == ["mystery_call"]

    def test_an_unresolved_import_carries_its_module_path(self) -> None:
        """Happy path: the same answer for the second ghost namespace."""
        edges = _of_kind(_module(imports=["os.path"]), EdgeKind.IMPORTS)

        assert [e.metadata.get("raw") for e in edges] == ["os.path"]

    def test_an_unresolved_supertype_carries_its_type_name(self) -> None:
        """Happy path: and the third. All three namespaces must answer the same way."""
        ast = _module(
            children=[
                {
                    "type": "class_definition",
                    "name": "Impl",
                    "supertypes": [{"name": "Base", "kind": "extends"}],
                    "calls": [],
                }
            ]
        )

        edges = _of_kind(ast, EdgeKind.EXTENDS)

        assert [e.metadata.get("raw") for e in edges] == ["Base"]

    def test_a_resolved_edge_carries_no_raw_name(self) -> None:
        """Boundary: the marker means something only when it is absent for a resolved target.

        If every edge carried a raw name, a reader could not tell a ghost from a real dependency by
        looking at the edge, and the field would be decoration.
        """
        edges = _of_kind(
            _module(calls=["helper"]),
            EdgeKind.CALLS,
            procedure_index={"helper": {("b.py", "helper")}},
        )

        assert [e.metadata.get("raw") for e in edges] == [None]

    def test_an_ambiguous_name_is_reported_as_the_name_it_was(self) -> None:
        """Boundary: ambiguity ghosts too, and the reader needs the name to resolve it by hand.

        Two declarations of one name are not one thing (`ADR-006`), so this is a ghost — but it is
        the ghost a human is most able to act on, and only if it says which name collided.
        """
        edges = _of_kind(
            _module(calls=["helper"]),
            EdgeKind.CALLS,
            procedure_index={"helper": {("b.py", "helper"), ("c.py", "helper")}},
        )

        assert [e.metadata.get("raw") for e in edges] == ["helper"]


class TestTheCapCannotStopABuild:
    def test_an_absurd_identifier_is_truncated_rather_than_refused(self) -> None:
        """Graceful degradation: `NFR-6` — one pathological file must not abort the build."""
        edges = _of_kind(_module(calls=["x" * 5000]), EdgeKind.CALLS)

        raw = edges[0].metadata["raw"]
        assert len(raw) < 5000
        assert raw.startswith("xxx")

    def test_a_truncated_name_says_it_was_truncated(self) -> None:
        """Graceful degradation: a silently shortened name reads as a real, wrong name."""
        edges = _of_kind(_module(calls=["y" * 5000]), EdgeKind.CALLS)

        assert edges[0].metadata["raw"] != "y" * 5000
        assert "…" in edges[0].metadata["raw"] or "..." in edges[0].metadata["raw"]

    def test_the_edge_stays_inside_the_agreed_cap(self) -> None:
        """Boundary: RT-25's 2 KB is the number, reused rather than a new one invented."""
        import json

        edges = _of_kind(_module(calls=["z" * 9000]), EdgeKind.CALLS)

        assert len(json.dumps(edges[0].metadata)) <= METADATA_MAX_BYTES

    def test_a_name_exactly_at_the_cap_is_not_mangled(self) -> None:
        """Boundary: the off-by-one. A name that fits must arrive whole."""
        name = "q" * 64
        edges = _of_kind(_module(calls=[name]), EdgeKind.CALLS)

        assert edges[0].metadata["raw"] == name


class TestHostileNames:
    def test_a_name_with_json_punctuation_survives(self) -> None:
        """Hostile: the metadata is JSON-encoded on the way to SQLite."""
        name = 'weird"name\\with{braces}'
        edges = _of_kind(_module(calls=[name]), EdgeKind.CALLS)

        assert edges[0].metadata["raw"] == name

    def test_a_name_with_newlines_survives(self) -> None:
        """Hostile: a grammar can hand back text spanning lines."""
        edges = _of_kind(_module(calls=["two\nlines"]), EdgeKind.CALLS)

        assert edges[0].metadata["raw"] == "two\nlines"

    def test_a_non_ascii_name_survives(self) -> None:
        """Hostile: identifiers are not ASCII in every language.

        Also the one that catches a byte-length cap applied to a character count: `é` is two bytes
        in UTF-8, so a 2,000-character name of them is 4 KB on disk.
        """
        import json

        edges = _of_kind(_module(calls=["héllo_wörld"]), EdgeKind.CALLS)
        assert edges[0].metadata["raw"] == "héllo_wörld"

        long_edges = _of_kind(_module(calls=["é" * 4000]), EdgeKind.CALLS)
        assert len(json.dumps(long_edges[0].metadata).encode("utf-8")) <= METADATA_MAX_BYTES


class TestEveryGhostNamespaceAgrees:
    """The agreement question: three call sites build a ghost, and they must answer alike.

    Each namespace has its own helper, so each could drift on its own and its own tests would still
    pass. That is the `TECH-058` shape — an asymmetry plainly visible in every file and asserted in
    none of them.
    """

    def test_all_three_ghost_kinds_carry_a_raw_name(self) -> None:
        ast = _module(
            imports=["unresolved.module"],
            calls=["unresolved_call"],
            children=[
                {
                    "type": "class_definition",
                    "name": "Impl",
                    "supertypes": [{"name": "UnresolvedBase", "kind": "extends"}],
                    "calls": [],
                }
            ],
        )

        by_kind = {e.kind: e.metadata.get("raw") for e in _edges(ast) if e.metadata.get("raw")}

        assert by_kind == {
            EdgeKind.IMPORTS: "unresolved.module",
            EdgeKind.CALLS: "unresolved_call",
            EdgeKind.EXTENDS: "UnresolvedBase",
        }
