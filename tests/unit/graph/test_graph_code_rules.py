# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The graph package keeps the shape TECH-004 gave it, read from its source.

Proves: TECH-004 FR-5
Proves: TECH-004 FR-9
Proves: TECH-004 FR-11

| Bucket | Case |
|---|---|
| Happy | the repository's public methods are typed without `Any` |
| Boundary | the DB-keyed internal graph may be called `db_digraph` |
| Degradation | not applicable — the source is read, nothing runs |
| Hostile | a parameter typed `nx.DiGraph` under any other name; an import inside a function |
"""

from __future__ import annotations

import ast
from pathlib import Path

GRAPH = Path(__file__).resolve().parents[3] / "src" / "specweaver" / "graph"
REPOSITORY = GRAPH / "core" / "store" / "repository.py"
#: AD-6: a graph keyed by semantic hash, or the repository's own DB-keyed one.
_GRAPH_NAMES = {"semantic_digraph", "db_digraph"}


def _trees() -> dict[Path, ast.Module]:
    return {p: ast.parse(p.read_text(encoding="utf-8")) for p in sorted(GRAPH.rglob("*.py"))}


def _functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def test_there_is_no_abstract_graph_repository() -> None:
    names = {
        n.name for tree in _trees().values() for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
    }
    assert "AbstractGraphRepository" not in names


def test_the_repository_public_methods_carry_no_any() -> None:
    tree = ast.parse(REPOSITORY.read_text(encoding="utf-8"))
    (repo,) = [
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SqliteGraphRepository"
    ]
    loose = [
        f.name
        for f in repo.body
        if isinstance(f, ast.FunctionDef)
        and not f.name.startswith("_")
        and "Any" in ast.unparse(f.args) + ast.unparse(f.returns or ast.Constant(None))
    ]
    assert loose == []


def test_the_repository_imports_only_at_module_level() -> None:
    tree = ast.parse(REPOSITORY.read_text(encoding="utf-8"))
    inner = [
        (f.name, ast.unparse(n))
        for f in _functions(tree)
        for n in ast.walk(f)
        if isinstance(n, ast.Import | ast.ImportFrom)
        and any(a.name.split(".")[0] in ("json", "networkx") for a in n.names)
    ]
    assert inner == []


def test_every_graph_parameter_is_named_by_ad_6() -> None:
    wrong = [
        f"{path.relative_to(GRAPH)}:{f.lineno} {f.name}({arg.arg})"
        for path, tree in _trees().items()
        for f in _functions(tree)
        for arg in [*f.args.posonlyargs, *f.args.args, *f.args.kwonlyargs]
        if arg.annotation is not None
        and ast.unparse(arg.annotation).split("[")[0].endswith("DiGraph")
        and arg.arg not in _GRAPH_NAMES
    ]
    assert wrong == []
