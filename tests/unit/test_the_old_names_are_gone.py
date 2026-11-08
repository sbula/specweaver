# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Names say what the code does: three old names are gone from source and tests.

Proves: TECH-088 FR-11

| Bucket | Case |
|---|---|
| Happy | `graph/topology/topology.py` defines `contexts_for`; `graph/lineage/protocol.py` defines `LineageRepositoryProtocol` |
| Boundary | `graph.lineage.store.lineage_repository`, a different module, is not an old name |
| Degradation | — a name has no dependency to fail |
| Hostile | no file under `src/` or `tests/` names `format_context_summary`, `specweaver.graph.lineage.repository` or `specweaver.graph.topology.changes`, as an import, an attribute, a definition or a string; the guard sees each spelling |
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src" / "specweaver"
_OLD_NAME = "format_context_summary"
_OLD_MODULES = ("specweaver.graph.lineage.repository", "specweaver.graph.topology.changes")


def _is_old_module(text: str) -> bool:
    return any(text == old or text.startswith(f"{old}.") for old in _OLD_MODULES)


def _old_names(tree: ast.AST) -> list[str]:
    """Each use of an old name: imports (`from a import b` read as `a.b`), attributes, defs, strings."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for name in (node.module, *(f"{node.module}.{a.name}" for a in node.names)):
                if _is_old_module(name):
                    found.append(name)
            found += [a.name for a in node.names if a.name == _OLD_NAME]
        elif isinstance(node, ast.Import):
            found += [a.name for a in node.names if _is_old_module(a.name)]
        elif isinstance(node, ast.Attribute) and node.attr == _OLD_NAME:
            found.append(node.attr)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == _OLD_NAME:
            found.append(node.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _OLD_NAME in node.value or _is_old_module(node.value):
                found.append(node.value)
    return found


def _defines(path: Path, name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name == name
        for node in ast.walk(tree)
    )


def test_the_new_names_exist() -> None:
    assert _defines(_SRC / "graph" / "topology" / "topology.py", "contexts_for")
    assert _defines(_SRC / "graph" / "lineage" / "protocol.py", "LineageRepositoryProtocol")
    assert not (_SRC / "graph" / "lineage" / "repository.py").exists()
    assert not (_SRC / "graph" / "topology" / "changes.py").exists()


def test_no_file_names_an_old_name() -> None:
    offenders: list[str] = []
    for path in sorted([*(_ROOT / "src").rglob("*.py"), *(_ROOT / "tests").rglob("*.py")]):
        if path == Path(__file__).resolve():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders += [f"{path.relative_to(_ROOT)}: {n}" for n in _old_names(tree)]

    assert offenders == []


def test_the_guard_sees_each_spelling() -> None:
    source = (
        "import specweaver.graph.topology.changes\n"
        "from specweaver.graph.lineage import repository\n"
        "from specweaver.graph.lineage.repository import LineageRepositoryProtocol\n"
        "graph.format_context_summary('a', set())\n"
        "def format_context_summary(): ...\n"
        "patch('specweaver.graph.lineage.repository.LineageRepositoryProtocol')\n"
        "'TopologyGraph.format_context_summary()'\n"
    )

    assert len(_old_names(ast.parse(source))) == 8


def test_the_lineage_store_is_not_an_old_name() -> None:
    source = "from specweaver.graph.lineage.store.lineage_repository import LineageRepository\n"

    assert _old_names(ast.parse(source)) == []
