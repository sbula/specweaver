# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A supertype becomes an edge to the type it names, or to a ghost when it names none of ours.

Proves: TECH-068 FR-9, FR-10

The edge runs type to type, not file to file — `IMPORTS` answers "which files does this depend on",
and inheritance answers "which type is this one built from". Resolution goes through the symbol index
`CB-2` builds before any edge, so a supertype declared in a file the build reaches later still
resolves, and resolves the same way on every run.

Unresolved and ambiguous both become a `GHOST`, as `ADR-006` requires of a truth store: two classes
named `Config` are not one class, and a blast-radius reader following an invented parent is worse
served than one seeing a visible unknown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.hashing import SemanticHasher
from specweaver.graph.core.engine.models import EdgeKind

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _parser_for(types: dict[str, dict[str, list[dict[str, str]]]]) -> Any:
    def parse(filepath: str) -> dict[str, Any]:
        return {
            "type": "module",
            "imports": [],
            "children": [
                {"type": "class_definition", "name": name, "supertypes": supers, "calls": []}
                for name, supers in types.get(filepath, {}).items()
            ],
        }

    return parse


def _build(
    tmp_path: Path, tree: dict[str, dict[str, list[dict[str, str]]]]
) -> tuple[InMemoryGraphEngine, Callable[[str, str], str]]:
    absolute = {}
    for rel, decls in tree.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        absolute[str(path)] = decls
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine=engine, parser=_parser_for(absolute))
    builder.ingest_target(tmp_path)
    hasher = SemanticHasher()
    return engine, lambda rel, name: hasher.hash_node(str(tmp_path / rel), name)


def _edges(engine: InMemoryGraphEngine, kind: EdgeKind) -> set[tuple[str, str]]:
    graph = engine.export_semantic_digraph()
    return {(u, v) for u, v, d in graph.edges(data=True) if d.get("kind") == kind.value}


def test_extension_and_implementation_land_as_different_edges(tmp_path: Path) -> None:
    """Happy path: what the grammar separated stays separate all the way to the graph."""
    engine, node = _build(
        tmp_path,
        {
            "Impl.java": {
                "Impl": [
                    {"name": "Base", "kind": "extends"},
                    {"name": "Runner", "kind": "implements"},
                ]
            },
            "Base.java": {"Base": []},
            "Runner.java": {"Runner": []},
        },
    )
    assert (node("Impl.java", "Impl"), node("Base.java", "Base")) in _edges(
        engine, EdgeKind.EXTENDS
    )
    assert (node("Impl.java", "Impl"), node("Runner.java", "Runner")) in _edges(
        engine, EdgeKind.IMPLEMENTS
    )


def test_a_supertype_in_the_same_file_resolves(tmp_path: Path) -> None:
    """Boundary: the index is not only for cross-file lookups."""
    engine, node = _build(
        tmp_path, {"m.py": {"Base": [], "Impl": [{"name": "Base", "kind": "extends"}]}}
    )
    assert (node("m.py", "Impl"), node("m.py", "Base")) in _edges(engine, EdgeKind.EXTENDS)


def test_a_type_with_no_supertypes_yields_no_edges(tmp_path: Path) -> None:
    """Boundary: nothing declared means nothing emitted, not an edge to nowhere."""
    engine, _ = _build(tmp_path, {"m.py": {"Plain": []}})
    assert _edges(engine, EdgeKind.EXTENDS) == set()
    assert _edges(engine, EdgeKind.IMPLEMENTS) == set()


def test_a_cycle_is_recorded_rather_than_followed(tmp_path: Path) -> None:
    """Boundary: mutual inheritance is invalid code, and must not hang the build."""
    engine, _node = _build(
        tmp_path,
        {
            "a.py": {"A": [{"name": "B", "kind": "extends"}]},
            "b.py": {"B": [{"name": "A", "kind": "extends"}]},
        },
    )
    assert len(_edges(engine, EdgeKind.EXTENDS)) == 2


def test_a_supertype_outside_the_parsed_set_becomes_a_ghost(tmp_path: Path) -> None:
    """Graceful degradation: a framework base class is not ours, and the reader can see that."""
    engine, node = _build(
        tmp_path, {"m.py": {"Impl": [{"name": "SomeFrameworkBase", "kind": "extends"}]}}
    )
    edges = _edges(engine, EdgeKind.EXTENDS)
    assert len(edges) == 1
    source, target = next(iter(edges))
    assert source == node("m.py", "Impl")
    assert target != node("m.py", "SomeFrameworkBase")


def test_a_supertype_declared_twice_becomes_one_ghost(tmp_path: Path) -> None:
    """Hostile: two classes named `Config` are not one class, so neither is the answer."""
    engine, node = _build(
        tmp_path,
        {
            "m.py": {"Impl": [{"name": "Config", "kind": "extends"}]},
            "one.py": {"Config": []},
            "two.py": {"Config": []},
        },
    )
    edges = _edges(engine, EdgeKind.EXTENDS)
    assert len(edges) == 1
    _, target = next(iter(edges))
    assert target not in {node("one.py", "Config"), node("two.py", "Config")}


def test_an_unresolved_type_and_an_unresolved_module_are_different_ghosts(tmp_path: Path) -> None:
    """A module named `Foo` and a type named `Foo` are not the same thing.

    Found by a surviving mutant: the ghost hash reused the module prefix, so an import of `Foo` we
    do not have and a base class `Foo` we do not have collapsed into one node. A traversal would
    then read a file's missing dependency and a type's missing parent as the same unknown.
    """
    engine = InMemoryGraphEngine()
    path = tmp_path / "m.py"
    path.write_text("", encoding="utf-8")

    def parse(_filepath: str) -> dict[str, Any]:
        return {
            "type": "module",
            "imports": ["Foo"],
            "children": [
                {
                    "type": "class_definition",
                    "name": "Impl",
                    "supertypes": [{"name": "Foo", "kind": "extends"}],
                    "calls": [],
                }
            ],
        }

    GraphBuilder(engine=engine, parser=parse).ingest_target(tmp_path)
    ghost_module = next(iter(_edges(engine, EdgeKind.IMPORTS)))[1]
    ghost_type = next(iter(_edges(engine, EdgeKind.EXTENDS)))[1]
    assert ghost_module != ghost_type
