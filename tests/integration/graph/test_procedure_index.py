# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Procedures are indexed beside types, in their own namespace, before any edge is built.

Proves: TECH-068 FR-11

`SF-03` indexed types so a supertype could resolve. A callee is a procedure, so it needs its own
entry — and its own NAMESPACE, settled with the user: a `class Foo` and a `def Foo` are different
symbols that happen to share a bare name, and one index would make each ambiguous for the other's
sake, ghosting both where neither actually collided.

The value shape differs too, which is a second reason not to share one structure. A call is written
bare — `helper()` — while the node hash is built from the qualified name, `hash_node(file,
"Impl.go")`. So a bare name maps to the `(file, qualified name)` pairs declaring it. A type needs no
such thing, because a supertype is written with the name the node carries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine

if TYPE_CHECKING:
    from pathlib import Path


def _build(tmp_path: Path, tree: dict[str, list[tuple[str, str]]]) -> GraphBuilder:
    """`tree` maps a file to the (node type, qualified name) pairs it declares."""
    absolute = {}
    for rel, decls in tree.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        absolute[str(path)] = decls

    def parse(filepath: str) -> dict[str, Any]:
        return {
            "type": "module",
            "imports": [],
            "children": [
                {"type": kind, "name": name, "supertypes": [], "calls": []}
                for kind, name in absolute.get(filepath, [])
            ],
        }

    builder = GraphBuilder(engine=InMemoryGraphEngine(), parser=parse)
    builder.ingest_target(tmp_path)
    return builder


def test_a_procedure_is_indexed_by_its_bare_name(tmp_path: Path) -> None:
    """Happy path: a call is written bare, so that is the lookup key."""
    builder = _build(tmp_path, {"a.py": [("function_definition", "helper")]})
    assert builder.procedure_index["helper"] == {(str(tmp_path / "a.py"), "helper")}


def test_a_method_is_indexed_under_its_last_segment(tmp_path: Path) -> None:
    """Boundary: `self.other()` calls `other`, and the node is `Impl.other`."""
    builder = _build(tmp_path, {"a.py": [("function_definition", "Impl.other")]})
    assert builder.procedure_index["other"] == {(str(tmp_path / "a.py"), "Impl.other")}


def test_two_procedures_of_one_bare_name_are_both_kept(tmp_path: Path) -> None:
    """Boundary: they are not one procedure, and FR-13 needs to see that."""
    builder = _build(
        tmp_path,
        {
            "a.py": [("function_definition", "A.run")],
            "b.py": [("function_definition", "B.run")],
        },
    )
    assert builder.procedure_index["run"] == {
        (str(tmp_path / "a.py"), "A.run"),
        (str(tmp_path / "b.py"), "B.run"),
    }


def test_a_type_and_a_procedure_of_one_name_do_not_collide(tmp_path: Path) -> None:
    """Graceful degradation: the whole reason for two namespaces rather than one."""
    builder = _build(
        tmp_path,
        {
            "t.py": [("class_definition", "Runner")],
            "p.py": [("function_definition", "Runner")],
        },
    )
    assert builder.symbol_index["Runner"] == {str(tmp_path / "t.py")}
    assert builder.procedure_index["Runner"] == {(str(tmp_path / "p.py"), "Runner")}


def test_a_tree_with_no_procedures_has_an_empty_index(tmp_path: Path) -> None:
    """Boundary: empty is a real state, not a missing attribute."""
    builder = _build(tmp_path, {"t.py": [("class_definition", "OnlyAType")]})
    assert builder.procedure_index == {}


def test_a_declaration_with_no_name_is_not_indexed(tmp_path: Path) -> None:
    """Hostile: an empty name would key the index on nothing and match every bare call."""
    builder = _build(tmp_path, {"a.py": [("function_definition", "")]})
    assert builder.procedure_index == {}
