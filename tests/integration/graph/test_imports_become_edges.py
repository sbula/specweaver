# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An import becomes an edge to the file it names, or to a GHOST when it names none of ours.

Proves: TECH-068 FR-8, FR-12

The mapper receives one file at a time and has no view of what else was collected, so it cannot turn
a module string into a file node alone. `collect_files` already produces that set and
`SemanticHasher.hash_file` is a pure function of the normalised path, so resolution needs no
filesystem access — `NFR-4` holds.

Resolution is one language-agnostic rule, settled with the user: split on `.`, `::` or `/` and
suffix-match the trailing segments against the collected paths, trying both `a/b.<ext>` and
`a/b/__init__.<ext>`, case-insensitively because `normalize_path` lowercases before hashing (RT-21).
No unique match becomes a GHOST — including an AMBIGUOUS one, because `ADR-006` makes the graph the
truth store and a blast-radius reader following an invented dependency is worse than one seeing a
visible unknown.
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


def _parser_reporting(imports: dict[str, list[str]]) -> Any:
    def parse(filepath: str) -> dict[str, Any]:
        return {"type": "module", "imports": imports.get(filepath, []), "children": []}

    return parse


def _import_edges(engine: InMemoryGraphEngine) -> set[tuple[str, str]]:
    graph = engine.export_semantic_digraph()
    return {
        (u, v)
        for u, v, data in graph.edges(data=True)
        if data.get("kind") == EdgeKind.IMPORTS.value
    }


def _build(
    tmp_path: Path, files: dict[str, list[str]]
) -> tuple[InMemoryGraphEngine, Callable[[str], str]]:
    """Write the fixture tree, then ingest it through the real entry point."""
    absolute = {}
    for rel, imports in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        absolute[str(path)] = imports

    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine=engine, parser=_parser_reporting(absolute))
    builder.known_files = set(absolute)
    for path in absolute:
        builder.ingest_file(path)

    hasher = SemanticHasher()
    return engine, lambda rel: hasher.hash_file(str(tmp_path / rel))


def test_an_import_of_a_collected_file_becomes_an_edge_between_them(tmp_path: Path) -> None:
    """Happy path: `a` imports `b`, and the graph says so."""
    engine, hasher = _build(tmp_path, {"pkg/a.py": ["pkg.b"], "pkg/b.py": []})
    assert (hasher("pkg/a.py"), hasher("pkg/b.py")) in _import_edges(engine)


def test_a_package_resolves_through_its_init(tmp_path: Path) -> None:
    """Boundary: `pkg.sub` is a directory whose module is `__init__.py`."""
    engine, hasher = _build(tmp_path, {"pkg/a.py": ["pkg.sub"], "pkg/sub/__init__.py": []})
    assert (
        hasher("pkg/a.py"),
        hasher("pkg/sub/__init__.py"),
    ) in _import_edges(engine)


def test_a_rust_style_separator_resolves(tmp_path: Path) -> None:
    """Boundary: the rule is language-agnostic, so `::` behaves like `.`."""
    engine, hasher = _build(tmp_path, {"src/a.rs": ["crate::alpha::beta"], "src/alpha/beta.rs": []})
    assert (hasher("src/a.rs"), hasher("src/alpha/beta.rs")) in _import_edges(engine)


def test_an_import_of_something_we_never_collected_becomes_a_ghost(tmp_path: Path) -> None:
    """Happy path for FR-12: the stdlib is not ours, and the reader can see that."""
    engine, hasher = _build(tmp_path, {"pkg/a.py": ["os"], "pkg/b.py": []})
    edges = _import_edges(engine)
    assert len(edges) == 1
    source, target = next(iter(edges))
    assert source == hasher("pkg/a.py")
    assert target not in {hasher(p) for p in ("pkg/a.py", "pkg/b.py")}


def test_an_ambiguous_import_becomes_one_ghost_not_a_guess(tmp_path: Path) -> None:
    """Hostile: two collected files both end `a/b.py`, so neither is the answer."""
    engine, hasher = _build(tmp_path, {"m.py": ["a.b"], "src/a/b.py": [], "vendor/a/b.py": []})
    edges = _import_edges(engine)
    assert len(edges) == 1
    _, target = next(iter(edges))
    assert target not in {hasher("src/a/b.py"), hasher("vendor/a/b.py")}


def test_with_no_collected_set_every_import_ghosts(tmp_path: Path) -> None:
    """Graceful degradation: `ingest_file` outside `ingest_target` knows of no other file."""
    lone = tmp_path / "pkg" / "a.py"
    lone.parent.mkdir(parents=True)
    lone.write_text("", encoding="utf-8")
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine=engine, parser=_parser_reporting({str(lone): ["pkg.b"]}))
    builder.ingest_file(str(lone))
    edges = _import_edges(engine)
    assert len(edges) == 1
    assert next(iter(edges))[1] != SemanticHasher().hash_file(str(tmp_path / "pkg/b.py"))


def test_an_empty_import_string_produces_no_edge(tmp_path: Path) -> None:
    """Hostile: an empty module name names nothing, not even a ghost."""
    engine, _ = _build(tmp_path, {"pkg/a.py": [""], "pkg/b.py": []})
    assert _import_edges(engine) == set()
