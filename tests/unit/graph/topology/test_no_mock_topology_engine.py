# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No test builds a module graph on a mock engine.

Proves: TECH-088 FR-13

A `MagicMock()` engine takes every call: `freeze()` does nothing on it and a write after it raises
nothing. A test built on one would pass whether the graph froze or not, so it proves nothing about a
frozen graph. Tests give the graph a real `TopologyEngine`.

| Bucket | Case |
|---|---|
| Happy | no `TopologyGraph(...)` or `TopologyGraph.from_project(...)` under `tests/` gets a mock engine |
| Boundary | the engine is found whether passed by position or by keyword |
| Degradation | — a source walk has no dependency to fail |
| Hostile | a mock bound to a name first, then passed, is caught too |
"""

from __future__ import annotations

import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parents[3]
_MOCKS = {"MagicMock", "Mock", "NonCallableMagicMock", "NonCallableMock"}


def _is_mock_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return name in _MOCKS


def _mock_names(tree: ast.AST) -> set[str]:
    """Names assigned a mock anywhere in the file; a name reused for a real engine is rare."""
    return {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and _is_mock_call(node.value)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def _builds_a_graph(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "TopologyGraph"
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "from_project"
        and isinstance(func.value, ast.Name)
        and func.value.id == "TopologyGraph"
    )


def _engine_argument(call: ast.Call) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == "engine":
            return keyword.value
    return call.args[1] if len(call.args) > 1 else None


def mock_engines(source: str) -> list[int]:
    """Line numbers where a module graph is built on a mock engine."""
    tree = ast.parse(source)
    names = _mock_names(tree)
    found: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _builds_a_graph(node):
            engine = _engine_argument(node)
            if engine is not None and (
                _is_mock_call(engine) or (isinstance(engine, ast.Name) and engine.id in names)
            ):
                found.append(node.lineno)
    return found


def test_no_test_builds_a_module_graph_on_a_mock_engine() -> None:
    offenders = [
        f"{path.relative_to(_TESTS.parent)}:{line}"
        for path in sorted(_TESTS.rglob("*.py"))
        for line in mock_engines(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_the_guard_sees_every_spelling() -> None:
    source = (
        "TopologyGraph(nodes, MagicMock())\n"
        "TopologyGraph(nodes={}, engine=MagicMock())\n"
        "TopologyGraph.from_project(root, mock.MagicMock(), auto_infer=False)\n"
        "engine = MagicMock()\n"
        "TopologyGraph(nodes, engine)\n"
        "TopologyGraph.from_project(root, engine=engine)\n"
        "TopologyGraph(nodes, TopologyEngine())\n"
        "real = TopologyEngine()\n"
        "TopologyGraph(nodes, engine=real)\n"
    )

    assert mock_engines(source) == [1, 2, 3, 5, 6]
