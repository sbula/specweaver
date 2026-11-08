# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No test builds a `GraphContext` with `model_copy(update=…)`.

Proves: TECH-088 FR-1

`model_copy(update=…)` skips validation, so a test double could put a shape in the run that no run
setup makes, and the reader it feeds would pass against it. That is how the topology slot held four
meanings with every test green. Tests go through `tests/fixtures/run_context.with_graph`, which
validates.
"""

from __future__ import annotations

import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parents[1]


def _is_a_graph(node: ast.expr, graph_names: set[str]) -> bool:
    """`<x>.graph`, a `GraphContext(...)` call, or a name bound to one of those."""
    if isinstance(node, ast.Attribute) and node.attr == "graph":
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id == "GraphContext"
    return isinstance(node, ast.Name) and node.id in graph_names


def _copies_a_graph(call: ast.Call, graph_names: set[str] = frozenset()) -> bool:
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr == "model_copy"):
        return False
    if not any(keyword.arg == "update" for keyword in call.keywords):
        return False
    return _is_a_graph(func.value, graph_names)


def _graph_names(tree: ast.AST) -> set[str]:
    """Names assigned a graph anywhere in the file; a name reused for something else is rare."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_a_graph(node.value, set()):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(_TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = _graph_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _copies_a_graph(node, names):
                found.append(f"{path.relative_to(_TESTS.parent)}:{node.lineno}")
    return found


def test_no_test_copies_a_graph_context_unvalidated() -> None:
    assert _offenders() == []


def test_the_guard_sees_every_spelling() -> None:
    code = (
        "ctx.graph = ctx.graph.model_copy(update={'x': 1})\n"
        "GraphContext().model_copy(update={'x': 1})\n"
        "original = GraphContext()\n"
        "original.model_copy(update={'x': 1})\n"
        "ctx.model = ctx.model.model_copy(update={'x': 1})\n"
        "ctx.graph.model_copy()\n"
    )
    tree = ast.parse(code)
    names = _graph_names(tree)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]

    assert sum(_copies_a_graph(call, names) for call in calls) == 3
