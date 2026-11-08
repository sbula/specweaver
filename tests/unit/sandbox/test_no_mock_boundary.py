# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No test stands a mock in for a run's boundary where the MCP tool reads its servers.

Proves: TECH-088 FR-15

A `MagicMock` boundary answers any attribute: a test built on one passes whatever shape the reader
expects, so it says nothing about the real boundary, which is frozen and holds tuples. Tests give the
MCP tool, its facade and the dispatcher a real `TopologyNode`.

| Bucket | Case |
|---|---|
| Happy | no `MCPExplorerTool(...)`, `create_mcp_interface(...)` or `ToolDispatcher.create_standard_set(...)` under `tests/` gets a mock `topology` |
| Boundary | the boundary is found by position or by keyword; `None` and a real node pass |
| Degradation | — a source walk has no dependency to fail |
| Hostile | a mock bound to a name first, returned by a fixture or helper, then passed, is caught too |
"""

from __future__ import annotations

import ast
from pathlib import Path

_TESTS = Path(__file__).resolve().parents[2]
_MOCKS = {"MagicMock", "Mock", "NonCallableMagicMock", "NonCallableMock"}
#: Each builder, and where its `topology` sits when passed by position.
_BUILDERS = {"MCPExplorerTool": 0, "create_mcp_interface": 1, "create_standard_set": 4}


def _name_of(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else ""


def _is_mock_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _name_of(node.func) in _MOCKS


def _mock_names(tree: ast.AST) -> set[str]:
    """Names bound to a mock in the file, and functions (fixtures, helpers) that return one."""
    names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and _is_mock_call(node.value)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for ret in ast.walk(node):
                if (
                    isinstance(ret, ast.Return)
                    and ret.value is not None
                    and _is_mock(ret.value, names)
                ):
                    names.add(node.name)
    return names


def _is_mock(node: ast.expr, names: set[str]) -> bool:
    if _is_mock_call(node):
        return True
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Call):
        return _name_of(node.func) in names
    if isinstance(node, ast.Tuple):
        return any(_is_mock(item, names) for item in node.elts)
    return False


def _boundary_argument(call: ast.Call) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == "topology":
            return keyword.value
    position = _BUILDERS[_name_of(call.func)]
    return call.args[position] if len(call.args) > position else None


def mock_boundaries(source: str) -> list[int]:
    """Line numbers where a builder is handed a mock boundary."""
    tree = ast.parse(source)
    names = _mock_names(tree)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _name_of(node.func) in _BUILDERS
        and (boundary := _boundary_argument(node)) is not None
        and _is_mock(boundary, names)
    ]


def test_no_test_hands_the_mcp_tool_a_mock_boundary() -> None:
    offenders = [
        f"{path.relative_to(_TESTS.parent)}:{line}"
        for path in sorted(_TESTS.rglob("*.py"))
        if path != Path(__file__).resolve()
        for line in mock_boundaries(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_the_guard_sees_every_spelling() -> None:
    source = (
        "MCPExplorerTool(MagicMock())\n"
        "MCPExplorerTool(topology=mock.MagicMock())\n"
        "create_mcp_interface('architect', MagicMock())\n"
        "ToolDispatcher.create_standard_set(b, 'architect', [], None, MagicMock())\n"
        "ToolDispatcher.create_standard_set(b, 'architect', [], topology=MagicMock())\n"
        "topo = MagicMock()\n"
        "MCPExplorerTool(topology=topo)\n"
        "def mock_topology():\n"
        "    t = MagicMock()\n"
        "    return t\n"
        "def test_a(mock_topology):\n"
        "    MCPExplorerTool(topology=mock_topology)\n"
        "    MCPExplorerTool(topology=mock_topology())\n"
        "MCPExplorerTool(topology=None)\n"
        "MCPExplorerTool(topology=TopologyNode('n', 'module', 'p', 'adapter'))\n"
        "create_mcp_interface('architect')\n"
    )

    assert mock_boundaries(source) == [1, 2, 3, 4, 5, 7, 12, 13]
