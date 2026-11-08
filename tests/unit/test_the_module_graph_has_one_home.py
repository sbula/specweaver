# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The module graph has one home, `graph/topology/`; `assurance/graph/` keeps only the boundary rule.

Proves: TECH-088 FR-5

| Bucket | Case |
|---|---|
| Happy | `graph/topology/` holds the graph, its loader, selectors, hasher and changed files |
| Boundary | `assurance/graph/` holds `boundary_rule.py` and `context.yaml` and nothing else |
| Degradation | — a layout has no dependency to fail |
| Hostile | no source or test imports or patches an old path; tach declares the new module and leaves `specweaver.graph`'s edges as they were |
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src" / "specweaver"
_OLD = tuple(
    f"specweaver.assurance.graph.{name}"
    for name in ("topology", "loader", "selectors", "hasher", "changes")
)
_MOVED = ("topology.py", "loader.py", "selectors.py", "hasher.py", "changed_files.py")


def _python_files() -> list[Path]:
    return sorted([*(_ROOT / "src").rglob("*.py"), *(_ROOT / "tests").rglob("*.py")])


def _names_an_old_path(text: str) -> bool:
    return any(old == text or text.startswith(f"{old}.") for old in _OLD)


def _imports(tree: ast.AST) -> list[str]:
    """Every imported module, `from a.b import c` counted as `a.b.c` too."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
            found.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
    return found


def _strings(tree: ast.AST) -> list[str]:
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _tach_modules() -> dict[str, list[str]]:
    data = tomllib.loads((_ROOT / "tach.toml").read_text(encoding="utf-8"))
    return {m["path"]: m.get("depends_on", []) for m in data["modules"]}


def test_the_graph_lives_in_graph_topology() -> None:
    present = {p.name for p in (_SRC / "graph" / "topology").iterdir()}

    assert set(_MOVED) <= present


def test_assurance_graph_keeps_only_the_boundary_rule() -> None:
    present = {p.name for p in (_SRC / "assurance" / "graph").iterdir() if p.name != "__pycache__"}

    assert present == {"boundary_rule.py", "context.yaml"}


def test_no_file_imports_or_patches_an_old_path() -> None:
    offenders: list[str] = []
    for path in _python_files():
        if path == Path(__file__).resolve():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        named = [*_imports(tree), *(s for s in _strings(tree) if _names_an_old_path(s))]
        offenders += [f"{path.relative_to(_ROOT)}: {n}" for n in named if _names_an_old_path(n)]

    assert offenders == []


def test_tach_declares_the_module_and_keeps_the_code_graph_s_edges() -> None:
    modules = _tach_modules()

    assert sorted(modules["specweaver.graph.topology"]) == [
        "specweaver.workspace.analyzers",
        "specweaver.workspace.context",
    ]
    assert sorted(modules["specweaver.graph"]) == [
        "specweaver.infrastructure.database",
        "specweaver.workspace.ast.adapters",
    ]


def test_the_guard_sees_a_moved_module_imported_from_its_package() -> None:
    tree = ast.parse("from specweaver.assurance.graph import selectors, boundary_rule\n")

    assert [n for n in _imports(tree) if _names_an_old_path(n)] == [
        "specweaver.assurance.graph.selectors"
    ]
