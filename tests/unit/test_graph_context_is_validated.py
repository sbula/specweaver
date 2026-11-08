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


def _copies_a_graph(call: ast.Call) -> bool:
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr == "model_copy"):
        return False
    if not any(keyword.arg == "update" for keyword in call.keywords):
        return False
    receiver = func.value
    if isinstance(receiver, ast.Attribute) and receiver.attr == "graph":
        return True
    return (
        isinstance(receiver, ast.Call)
        and isinstance(receiver.func, ast.Name)
        and receiver.func.id == "GraphContext"
    )


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(_TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _copies_a_graph(node):
                found.append(f"{path.relative_to(_TESTS.parent)}:{node.lineno}")
    return found


def test_no_test_copies_a_graph_context_unvalidated() -> None:
    assert _offenders() == []


def test_the_guard_sees_both_spellings() -> None:
    code = (
        "ctx.graph = ctx.graph.model_copy(update={'x': 1})\n"
        "GraphContext().model_copy(update={'x': 1})\n"
        "ctx.model = ctx.model.model_copy(update={'x': 1})\n"
        "ctx.graph.model_copy()\n"
    )
    calls = [n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Call)]

    assert sum(_copies_a_graph(call) for call in calls) == 2
