# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every language this ticket covers contributes edges to a real build.

Proves: TECH-068 FR-3

The closing claim. Each language's parser has its own tests and each seam has its own; none of them
says the whole set works together, which is the shape of defect `TECH-056` and `TECH-058` both were —
two halves passing every assertion they had while the composition they exist for could not work.

A polyglot tree is built through the real orchestrator, with no doubles, and every code language must
contribute at least one dependency edge. `sql` and `markdown` have no calls to find and contribute
none, which is the correct answer rather than a gap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine
from specweaver.graph.core.engine.models import EdgeKind
from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path

_TREE = {
    "a.py": "def helper():\n    pass\n\ndef caller():\n    helper()\n",
    "b.ts": "function helper() {}\nfunction caller() { helper(); }\n",
    "c.kt": "fun helper() {}\nfun caller() { helper() }\n",
    "d.java": "class K { void helper() {} void caller() { helper(); } }",
    "e.rs": "fn helper() {}\nfn caller() { helper(); }\n",
    "f.go": "package m\nfunc helper() {}\nfunc caller() { helper() }\n",
    "g.c": "void helper(void) {}\nvoid caller(void) { helper(); }\n",
    "h.cpp": "void helper() {}\nvoid caller() { helper(); }\n",
    "i.sql": "SELECT 1;\n",
    "j.md": "# Title\n",
}


def _build(tmp_path: Path) -> InMemoryGraphEngine:
    for name, body in _TREE.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    engine = InMemoryGraphEngine()
    GraphBuilder(engine=engine, parser=extract_ast_dict).ingest_target(tmp_path)
    return engine


def _edge_kinds_by_file(engine: InMemoryGraphEngine) -> dict[str, set[str]]:
    graph = engine.export_semantic_digraph()
    by_hash = {h: d.get("file_id", "") for h, d in graph.nodes(data=True)}
    found: dict[str, set[str]] = {}
    for source, _target, data in graph.edges(data=True):
        file_id = by_hash.get(source, "")
        if file_id:
            found.setdefault(file_id.rsplit("/", 1)[-1], set()).add(str(data.get("kind")))
    return found


def test_every_code_language_contributes_a_call_edge(tmp_path: Path) -> None:
    """Happy path, and the claim about the set rather than about any one language."""
    by_file = _edge_kinds_by_file(_build(tmp_path))
    missing = [
        name
        for name in _TREE
        if not name.endswith((".sql", ".md"))
        and EdgeKind.CALLS.value not in by_file.get(name, set())
    ]
    assert missing == [], f"languages contributing no CALLS edge: {missing}"


def test_a_language_with_no_calls_contributes_none(tmp_path: Path) -> None:
    """Boundary: the correct answer, not a gap."""
    by_file = _edge_kinds_by_file(_build(tmp_path))
    for name in ("i.sql", "j.md"):
        assert EdgeKind.CALLS.value not in by_file.get(name, set())


def test_an_unreadable_file_does_not_stop_the_build(tmp_path: Path) -> None:
    """Graceful degradation: one bad file must not cost every other file's edges."""
    (tmp_path / "trap.py").mkdir()
    by_file = _edge_kinds_by_file(_build(tmp_path))
    assert EdgeKind.CALLS.value in by_file.get("a.py", set())


def test_two_builds_of_one_tree_agree(tmp_path: Path) -> None:
    """Hostile: the same tree must not produce two different graphs."""
    first = _edge_kinds_by_file(_build(tmp_path))
    second = _edge_kinds_by_file(_build(tmp_path))
    assert first == second
