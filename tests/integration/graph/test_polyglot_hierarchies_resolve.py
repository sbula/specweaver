# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A type hierarchy is traversable in Go and Rust, not only in the curly-brace languages.

Proves: TECH-068 FR-9, FR-10

The parsers report supertypes now, and that alone changes nothing a reader can use: the mapper
resolves a supertype against `symbol_index`, which `_index_types` fills from children the adapter
marked `class_definition` — and the adapter decided that from `extract_framework_markers`, which
returns `{}` for Go. So every Go type was classified as a PROCEDURE, never indexed, and a Go
supertype edge could only ever point at a ghost even with both types in the same build.

The fix reads the classification from `extract_supertypes` instead: a name that method reports IS a
type, by its own contract. That is a truer source than an `extends` key that only appears when a
type happens to have a supertype.

**Rust stops one step short, deliberately.** `list_symbols` does not report a trait at all, so
`Runner` is not a node this build can point at and the `IMPLEMENTS` edge ghosts. The edge exists
with the right kind, and `FR-12` now makes the ghost say `Runner` — so a reader learns the trait's
name even though it has no node. Making traits symbols means changing `list_symbols`, whose callers
reach well past this ticket. Recorded rather than widened.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import EDGE_KIND_ATTR
from specweaver.graph.core.engine.ontology import EdgeKind
from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _build(tmp_path: Path, files: dict[str, str]) -> InMemoryGraphEngine:
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    engine = InMemoryGraphEngine()
    GraphBuilder(engine=engine, parser=extract_ast_dict).ingest_target(tmp_path)
    return engine


def _edges_of(engine: InMemoryGraphEngine, kind: EdgeKind) -> list[tuple[str, str, str]]:
    """`(source name, target file_id, raw name)` for every edge of one kind.

    An empty `file_id` on the target is what a ghost looks like from here.
    """
    graph = engine.export_semantic_digraph()
    named = {h: d.get("name", "") for h, d in graph.nodes(data=True)}
    files = {h: d.get("file_id", "") for h, d in graph.nodes(data=True)}
    return [
        (named.get(u, ""), files.get(v, ""), data.get("metadata", {}).get("raw", ""))
        for u, v, data in graph.edges(data=True)
        if data.get(EDGE_KIND_ATTR) == kind.value
    ]


_GO = {
    "base.go": "package m\ntype Base struct {\n\tX int\n}\n",
    "impl.go": "package m\ntype Impl struct {\n\tBase\n\tY int\n}\n",
}
_RUST = {
    "t.rs": "pub trait Runner {\n    fn go(&self);\n}\n",
    "i.rs": "struct Impl;\nimpl Runner for Impl {\n    fn go(&self) {}\n}\n",
}


def test_a_go_embed_resolves_to_the_embedded_type(tmp_path: Path) -> None:
    """Happy path: both types are in the build, so the edge must reach a real node."""
    edges = _edges_of(_build(tmp_path, _GO), EdgeKind.EXTENDS)

    assert edges, "no EXTENDS edge was produced at all"
    assert any(src == "Impl" and target.endswith("base.go") for src, target, _raw in edges), (
        f"the Go embed did not resolve to the collected file: {edges}"
    )


def test_a_go_type_is_a_type_and_not_a_procedure(tmp_path: Path) -> None:
    """Boundary: the classification is what makes resolution possible at all.

    `extract_framework_markers` returns `{}` for Go, so every Go type used to be classified as a
    procedure — and `_index_types` only indexes types, so nothing Go declared could ever be the
    target of anybody's supertype edge.
    """
    graph = _build(tmp_path, _GO).export_semantic_digraph()

    kinds = {d.get("name"): d.get("kind") for _h, d in graph.nodes(data=True) if d.get("name")}
    assert kinds.get("Base") == "DATA_STRUCTURE", f"Go types are still not types: {kinds}"
    assert kinds.get("Impl") == "DATA_STRUCTURE", f"Go types are still not types: {kinds}"


def test_a_go_embed_of_something_absent_still_ghosts_by_name(tmp_path: Path) -> None:
    """Boundary: resolution must not start inventing targets to satisfy the test above."""
    edges = _edges_of(
        _build(tmp_path, {"impl.go": "package m\ntype Impl struct {\n\tNowhere\n}\n"}),
        EdgeKind.EXTENDS,
    )

    assert [(src, target, raw) for src, target, raw in edges if src == "Impl"] == [
        ("Impl", "", "Nowhere")
    ]


def test_a_rust_impl_emits_an_implements_edge(tmp_path: Path) -> None:
    """Happy path for `FR-10`: the KIND is the claim, and it is not `EXTENDS`."""
    edges = _edges_of(_build(tmp_path, _RUST), EdgeKind.IMPLEMENTS)

    assert any(src == "Impl" for src, _t, _raw in edges), f"no IMPLEMENTS edge for Impl: {edges}"


def test_a_rust_trait_is_named_even_though_it_has_no_node(tmp_path: Path) -> None:
    """Graceful degradation, and the recorded limit.

    `list_symbols` does not report a trait, so `Runner` has no node and the edge ghosts. `FR-12` is
    what keeps that useful: the ghost says which trait it was. This test is the record — if traits
    ever become symbols it turns red and says so.
    """
    edges = _edges_of(_build(tmp_path, _RUST), EdgeKind.IMPLEMENTS)

    impl_edges = [(target, raw) for src, target, raw in edges if src == "Impl"]
    assert impl_edges == [("", "Runner")], (
        f"expected one ghost edge naming Runner, got {impl_edges} — if traits are now symbols, "
        f"this limit is lifted and the docstring above needs rewriting"
    )


def test_go_and_rust_do_not_disturb_python(tmp_path: Path) -> None:
    """Hostile: the classification change touches every language, not only the two it was for.

    A name reported by `extract_supertypes` is now treated as a type. If any language reported a
    FUNCTION there, that function would silently become a `DATA_STRUCTURE` node.
    """
    graph = _build(
        tmp_path,
        {
            "a.py": "class Thing(Base):\n    pass\n\n\ndef helper():\n    pass\n",
            **_GO,
        },
    ).export_semantic_digraph()

    kinds = {d.get("name"): d.get("kind") for _h, d in graph.nodes(data=True) if d.get("name")}
    assert kinds.get("Thing") == "DATA_STRUCTURE"
    assert kinds.get("helper") == "PROCEDURE", f"a function was reclassified as a type: {kinds}"
