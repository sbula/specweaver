#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Structural health of individual classes: god-object size and LCOM4 cohesion.

Why this is not covered by the complexity gate. Cyclomatic complexity is close to a proxy for
line count, and it is structurally BLIND to the failure it is most often credited with catching:
a god object scores 1, because field declarations contain no branches. The evidence is this repo
-- `RunContext` grew from the 23 fields `TECH-006` set out to reduce, to 32, with every gate
green the whole way, because `handlers/base.py` at 250 lines clears every size threshold too.

Two metrics, deliberately different in kind:

  ATTRIBUTE COUNT answers "is this a god object". Cheap, and it is the one that would have
  caught `RunContext`.

  LCOM4 answers "where do I cut it". Build a graph over one class -- nodes are methods, an edge
  joins two methods that touch a common attribute or that call one another -- and count connected
  components. 1 is cohesive. 3 means the class is literally three independent classes sharing a
  name, AND THE THREE COMPONENTS ARE THE SPLIT. That is a refactoring instruction, not a score,
  which matters because a finding an agent cannot act on is a finding that gets suppressed.

"LCOM" is ambiguous and the ambiguity is dangerous: LCOM1-3 (Chidamber-Kemerer) are known-flawed
and produce misleading results. This is LCOM4 (Hitz & Montazeri), the usable definition.

`__init__` is excluded from the cohesion graph on purpose. It touches every attribute by
definition, so including it fuses every component into one and reports perfect cohesion for even
the worst class.

Exit 1 if any class exceeds a threshold.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: A class holding more than this many attributes is doing more than one job.
MAX_ATTRIBUTES = 15
#: Connected components above this mean the class is really N classes.
MAX_LCOM4 = 1

#: Bases whose attribute count is meaningless — members are values, not state.
EXEMPT_BASES = {"Enum", "StrEnum", "IntEnum", "IntFlag", "Flag", "Protocol", "TypedDict"}

#: Names that are framework configuration rather than state the class carries.
#:
#: `model_config` is Pydantic's own settings block. Every Pydantic model has exactly one, so
#: counting it does not distinguish a class doing too much from one doing very little — it just
#: subtracts one from the real budget of every Pydantic class while leaving every other class
#: on the full limit. Same reasoning as excluding stateless methods from the cohesion score: a
#: term that is present by construction cannot carry information.
IGNORED_ATTRIBUTES = {"model_config"}


@dataclass
class ClassReport:
    path: Path
    name: str
    lineno: int
    attributes: set[str] = field(default_factory=set)
    lcom4: int = 0
    components: list[list[str]] = field(default_factory=list)
    method_count: int = 0

    def too_many_attributes(self, limit: int = MAX_ATTRIBUTES) -> bool:
        return len(self.attributes) > limit

    def incohesive(self) -> bool:
        return self.lcom4 > MAX_LCOM4


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _self_attributes(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Attributes reached through `self` anywhere inside one method."""
    found: set[str] = set()
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            found.add(node.attr)
    return found


def _decorator_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for dec in func.decorator_list:
        if isinstance(dec, ast.Name):
            names.add(dec.id)
        elif isinstance(dec, ast.Attribute):
            names.add(dec.attr)
        elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
            names.add(dec.func.id)
    return names


def _is_abstract_stub(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """A body of `...`, `pass`, or `raise NotImplementedError` declares nothing about cohesion."""
    body = [
        s
        for s in func.body
        if not (
            isinstance(s, ast.Expr)
            and isinstance(s.value, ast.Constant)
            and isinstance(s.value.value, str)
        )
    ]
    if not body:
        return True
    if len(body) > 1:
        return False
    only = body[0]
    if isinstance(only, ast.Pass):
        return True
    if isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant):
        return only.value.value is Ellipsis
    if isinstance(only, ast.Raise):
        exc = only.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"
    return False


def _is_stateless(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    touched: set[str],
    called: set[str],
    method_names: set[str],
) -> bool:
    """True when a method cannot couple to any sibling, so it says nothing about cohesion."""
    if {"staticmethod", "classmethod"} & _decorator_names(func):
        return True
    if _is_abstract_stub(func):
        return True
    return not (touched - method_names) and not (called & method_names)


def _declared_attributes(node: ast.ClassDef) -> set[str]:
    """Class-body fields: dataclass and pydantic models declare state here, not in __init__."""
    found: set[str] = set()
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            found.add(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            found.update(t.id for t in stmt.targets if isinstance(t, ast.Name))
    return found


def _components(nodes: list[str], edges: set[tuple[str, str]]) -> list[list[str]]:
    """Connected components by union-find — no third-party graph library needed."""
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    groups: dict[str, list[str]] = {}
    for n in nodes:
        groups.setdefault(find(n), []).append(n)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g[0]))


def analyse_class(node: ast.ClassDef, path: Path) -> ClassReport:
    report = ClassReport(path=path, name=node.name, lineno=node.lineno)

    methods = [s for s in node.body if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef)]
    report.method_count = len(methods)

    touched: dict[str, set[str]] = {m.name: _self_attributes(m) for m in methods}
    called: dict[str, set[str]] = {}
    for m in methods:
        calls = {
            n.func.attr
            for n in ast.walk(m)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "self"
        }
        called[m.name] = calls

    method_names = {m.name for m in methods}
    report.attributes = (
        _declared_attributes(node)
        | (set().union(*touched.values()) - method_names if touched else set())
    ) - IGNORED_ATTRIBUTES

    # LCOM4 over every method except the constructor (see module docstring) and except methods
    # that carry no instance state at all.
    #
    # Excluding the stateless ones is not leniency, it is what makes the metric mean anything. A
    # property returning a literal, an abstract stub, or a staticmethod touches no attribute and
    # calls no sibling, so it is an isolated node BY CONSTRUCTION and adds one component no
    # matter how cohesive the class is. Left in, `MarkdownCodeStructure` scored LCOM4=19 with 17
    # of those components being a single accessor apiece -- a number that says nothing about
    # where to cut, and so gets suppressed rather than acted on.
    graph_nodes = [
        m.name
        for m in methods
        if m.name != "__init__"
        and not _is_stateless(m, touched[m.name], called[m.name], method_names)
    ]
    if len(graph_nodes) < 2:
        report.lcom4 = 1 if graph_nodes else 0
        report.components = [graph_nodes] if graph_nodes else []
        return report

    edges: set[tuple[str, str]] = set()
    for i, a in enumerate(graph_nodes):
        for b in graph_nodes[i + 1 :]:
            shared = (touched[a] - method_names) & (touched[b] - method_names)
            if shared or b in called[a] or a in called[b]:
                edges.add((a, b))

    report.components = _components(graph_nodes, edges)
    report.lcom4 = len(report.components)
    return report


def analyse_file(path: Path) -> list[ClassReport]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    reports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if _base_names(node) & EXEMPT_BASES:
                continue
            reports.append(analyse_class(node, path))
    return reports


def iter_python_files(paths: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(p for p in path.rglob("*.py") if "__pycache__" not in p.parts)
        elif path.suffix == ".py" and path.is_file():
            found.add(path)
    return sorted(found)


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="files or directories (default: src)")
    ap.add_argument("--max-attributes", type=int, default=MAX_ATTRIBUTES)
    args = ap.parse_args(argv)

    limit: int = args.max_attributes

    raw = [Path(p) for p in args.paths] if args.paths else [REPO_ROOT / "src"]
    missing = [p for p in raw if not p.exists()]
    if missing:
        for path in missing:
            print(f"FAIL  path not found: {path}")
        return 1

    files = iter_python_files(raw)
    reports = [r for f in files for r in analyse_file(f)]
    fat = [r for r in reports if r.too_many_attributes(limit)]
    split = [r for r in reports if r.incohesive()]
    failures = {id(r): r for r in [*fat, *split]}

    if not failures:
        print(f"Class health: {len(reports)} class(es) in {len(files)} file(s), all within limits")
        return 0

    if fat:
        print(f"God objects (> {limit} attributes):\n")
        for r in sorted(fat, key=lambda r: -len(r.attributes)):
            print(f"  {_rel(r.path)}:{r.lineno}  {r.name}  {len(r.attributes)} attributes")

    if split:
        print(f"\nIncohesive classes (LCOM4 > {MAX_LCOM4} — the components ARE the split):\n")
        for r in sorted(split, key=lambda r: -r.lcom4):
            print(f"  {_rel(r.path)}:{r.lineno}  {r.name}  LCOM4={r.lcom4}")
            for i, comp in enumerate(r.components, 1):
                shown = ", ".join(comp[:6]) + (" ..." if len(comp) > 6 else "")
                print(f"      component {i}: {shown}")

    print(
        f"\nBLOCKED: {len(failures)} class(es) failed — {len(fat)} oversized, "
        f"{len(split)} incohesive, out of {len(reports)} analysed."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
