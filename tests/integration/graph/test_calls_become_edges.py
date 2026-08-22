# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A call becomes an edge to the procedure it names, or to a ghost when it names none of ours.

Proves: TECH-068 FR-11, FR-13

The last edge kind this ticket owns. Resolution goes through the procedure index `CB-2` builds
before any edge, keyed on the bare name a call is written with and valued by the qualified name the
node hash is built from.

Ambiguity ghosts, as `FR-13` requires. Measured over this repository: 87% of distinct bare names are
declared exactly once and resolve, while the collisions are `__init__` (131), `name`, `check`,
`execute`, `run`. **Every constructor call therefore ghosts** — that is the rule working, not a gap
in it: resolving `__init__` means guessing which class was constructed, which is the guess `ADR-006`
forbids of a truth store.
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


def _build(
    tmp_path: Path, tree: dict[str, dict[str, Any]]
) -> tuple[InMemoryGraphEngine, Callable[[str, str], str], Callable[[str], str]]:
    """`tree` maps a file to `{"defs": [names], "calls": {caller: [callees]}, "file_calls": [...]}`."""
    absolute = {}
    for rel, spec in tree.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        absolute[str(path)] = spec

    def parse(filepath: str) -> dict[str, Any]:
        spec = absolute.get(filepath, {})
        return {
            "type": "module",
            "imports": [],
            "calls": spec.get("file_calls", []),
            "children": [
                {
                    "type": "function_definition",
                    "name": name,
                    "supertypes": [],
                    "calls": spec.get("calls", {}).get(name, []),
                }
                for name in spec.get("defs", [])
            ],
        }

    engine = InMemoryGraphEngine()
    GraphBuilder(engine=engine, parser=parse).ingest_target(tmp_path)
    hasher = SemanticHasher()
    return (
        engine,
        lambda rel, name: hasher.hash_node(str(tmp_path / rel), name),
        lambda rel: hasher.hash_file(str(tmp_path / rel)),
    )


def _calls(engine: InMemoryGraphEngine) -> set[tuple[str, str]]:
    graph = engine.export_semantic_digraph()
    return {(u, v) for u, v, d in graph.edges(data=True) if d.get("kind") == EdgeKind.CALLS.value}


def test_a_call_to_a_unique_procedure_becomes_an_edge(tmp_path: Path) -> None:
    """Happy path: caller to callee, the question every reader of this graph asks."""
    engine, node, _ = _build(
        tmp_path,
        {
            "a.py": {"defs": ["caller"], "calls": {"caller": ["helper"]}},
            "b.py": {"defs": ["helper"]},
        },
    )
    assert (node("a.py", "caller"), node("b.py", "helper")) in _calls(engine)


def test_a_method_call_resolves_through_its_bare_name(tmp_path: Path) -> None:
    """Boundary: written `other()`, declared `Impl.other` — the index bridges the two."""
    engine, node, _ = _build(
        tmp_path,
        {
            "a.py": {"defs": ["A.go"], "calls": {"A.go": ["other"]}},
            "b.py": {"defs": ["Impl.other"]},
        },
    )
    assert (node("a.py", "A.go"), node("b.py", "Impl.other")) in _calls(engine)


def test_a_recursive_call_is_a_self_edge(tmp_path: Path) -> None:
    """Boundary: a function calling itself is a real dependency, not noise to filter."""
    engine, node, _ = _build(tmp_path, {"a.py": {"defs": ["a"], "calls": {"a": ["a"]}}})
    assert (node("a.py", "a"), node("a.py", "a")) in _calls(engine)


def test_a_module_level_call_runs_from_the_file(tmp_path: Path) -> None:
    """Boundary: no symbol owns it, so the file does."""
    engine, node, file_node = _build(
        tmp_path,
        {"a.py": {"file_calls": ["build"]}, "b.py": {"defs": ["build"]}},
    )
    assert (file_node("a.py"), node("b.py", "build")) in _calls(engine)


def test_a_symbol_that_calls_nothing_yields_no_edge(tmp_path: Path) -> None:
    """Boundary: nothing declared means nothing emitted."""
    engine, _, _ = _build(tmp_path, {"a.py": {"defs": ["quiet"]}})
    assert _calls(engine) == set()


def test_a_callee_outside_the_parsed_set_becomes_a_ghost(tmp_path: Path) -> None:
    """Graceful degradation: the stdlib is not ours, and the reader can see that."""
    engine, node, _ = _build(
        tmp_path, {"a.py": {"defs": ["caller"], "calls": {"caller": ["getcwd"]}}}
    )
    edges = _calls(engine)
    assert len(edges) == 1
    source, target = next(iter(edges))
    assert source == node("a.py", "caller")
    assert target != node("a.py", "getcwd")


def test_a_callee_declared_twice_becomes_one_ghost(tmp_path: Path) -> None:
    """Hostile: FR-13. Two procedures named `run` are not one procedure."""
    engine, node, _ = _build(
        tmp_path,
        {
            "a.py": {"defs": ["caller"], "calls": {"caller": ["run"]}},
            "one.py": {"defs": ["A.run"]},
            "two.py": {"defs": ["B.run"]},
        },
    )
    edges = _calls(engine)
    assert len(edges) == 1
    _, target = next(iter(edges))
    assert target not in {node("one.py", "A.run"), node("two.py", "B.run")}


def test_an_unresolved_call_type_and_module_are_three_different_ghosts(tmp_path: Path) -> None:
    """Hostile: a missing function, a missing base class and a missing module are three unknowns.

    `SF-03` separated modules from types after a mutant showed one prefix serving both. A procedure
    is the third kind, and collapsing any two would report one absence as another.
    """
    engine = InMemoryGraphEngine()
    path = tmp_path / "m.py"
    path.write_text("", encoding="utf-8")

    def parse(_f: str) -> dict[str, Any]:
        return {
            "type": "module",
            "imports": ["Foo"],
            "calls": [],
            "children": [
                {
                    "type": "class_definition",
                    "name": "Impl",
                    "supertypes": [{"name": "Foo", "kind": "extends"}],
                    "calls": ["Foo"],
                }
            ],
        }

    GraphBuilder(engine=engine, parser=parse).ingest_target(tmp_path)
    graph = engine.export_semantic_digraph()
    targets = {d["kind"]: v for _u, v, d in graph.edges(data=True) if d.get("kind") != "CONTAINS"}
    assert len(set(targets.values())) == 3, targets
