#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Import-graph coupling: dependency cycles, fan-in/fan-out, and instability.

This does NOT replace `tach`. `tach` answers "is this import ALLOWED" against declared layer
boundaries. It cannot answer "how much does this module depend on, how much depends on it, and is
it stable enough to carry that weight" -- and it cannot see an UNDECLARED cycle, because a cycle
between two modules inside the same declared layer breaks no declared rule.

Two modes, because the two questions have different shapes:

  --cycles-only  Strongly connected components via Tarjan. A cycle CANNOT be seen in a diff --
                 the whole point is that module A reaches back round to itself through modules
                 nobody touched -- so this is global from the first commit point and never
                 narrows. Any cycle fails.

  (default)      Adds the metrics. Fan-in likewise needs every importer in the repo, so the
                 ANALYSIS is always global; the paths given narrow only which modules are JUDGED,
                 never what is computed.

Instability I = Ce / (Ca + Ce): 0 is maximally stable (everyone depends on it, it depends on
nobody), 1 is maximally unstable. High fan-in plus high instability is the "zone of pain" -- a
module many things rely on that itself keeps moving.

Stdlib only, on purpose: Tarjan is twenty lines and a gate that cannot run when a dependency is
missing is a gate that gets skipped.

Exit 1 on any cycle, or any module past a threshold.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
ROOT_PACKAGE = "specweaver"

#: Modules importing more than this many internal modules are doing too much coordinating.
MAX_FAN_OUT = 20
#: Widely-depended-on modules that are themselves unstable: the zone of pain.
HIGH_FAN_IN = 10
UNSTABLE = 0.7


def module_name(path: Path) -> str:
    """src/specweaver/core/flow/runner.py -> specweaver.core.flow.runner"""
    rel = path.relative_to(SRC_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(current: str, node: ast.ImportFrom, is_package: bool) -> str:
    """Resolve `from ..x import y` against the importing module's own dotted path."""
    parts = current.split(".")
    # Inside a package's __init__, level 1 means the package itself; elsewhere its parent.
    base = parts if is_package else parts[:-1]
    climb = node.level - 1
    if climb:
        base = base[:-climb] if climb <= len(base) else []
    return ".".join([*base, node.module] if node.module else base)


def _is_type_checking_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def iter_runtime_imports(tree: ast.AST) -> list[ast.Import | ast.ImportFrom]:
    """Every import that actually executes.

    Imports under `if TYPE_CHECKING:` are excluded deliberately. They create no runtime edge, and
    they are the standard, CORRECT way to break an import cycle -- `sandbox.execution.executor`
    and `platform_limiter` are joined only by one, and reporting that pair as a cycle would tell
    the reader to fix something already fixed. A check that flags correct code is a check that
    gets suppressed.
    """
    found: list[ast.Import | ast.ImportFrom] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.If) and _is_type_checking_guard(node):
            # `else:` executes at runtime, so its imports are real edges. Visit those statements
            # themselves — descending into their children instead silently drops them.
            for alt in node.orelse:
                visit(alt)
            return
        if isinstance(node, ast.Import | ast.ImportFrom):
            found.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return found


def build_graph(files: list[Path]) -> dict[str, set[str]]:
    """Map every internal module to the internal modules it imports."""
    known = {module_name(f) for f in files}
    graph: dict[str, set[str]] = {name: set() for name in known}

    def register(source: str, target: str) -> None:
        if not target or not target.startswith(ROOT_PACKAGE):
            return
        # Attribute imports resolve to their owning module; walk up to the nearest real one.
        candidate = target
        while candidate and candidate not in known:
            candidate, _, _ = candidate.rpartition(".")
        if candidate and candidate != source:
            graph[source].add(candidate)

    for path in files:
        name = module_name(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        is_package = path.name == "__init__.py"
        for node in iter_runtime_imports(tree):
            for target in _import_targets(node, name, is_package):
                register(name, target)
    return graph


def _import_targets(node: ast.Import | ast.ImportFrom, current: str, is_package: bool) -> list[str]:
    """Every dotted name one import statement could be referring to."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    base = _resolve_relative(current, node, is_package) if node.level else (node.module or "")
    # `from x import y` may name a module OR an attribute of x; register both and let the
    # caller resolve to whichever is a real module.
    return [base, *[f"{base}.{alias.name}" if base else alias.name for alias in node.names]]


def tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components, iteratively (the graph is deeper than the stack limit)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: list[list[str]] = []
    counter = 0

    for root in sorted(graph):
        if root in index:
            continue
        work: list[tuple[str, list[str]]] = [(root, sorted(graph[root]))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)

        while work:
            node, pending = work[-1]
            if pending:
                child = pending.pop()
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, sorted(graph.get(child, set()))))
                elif child in on_stack:
                    low[node] = min(low[node], index[child])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    component = _pop_component(stack, on_stack, node)
                    if len(component) > 1:
                        result.append(component)
    return result


def _pop_component(stack: list[str], on_stack: set[str], root: str) -> list[str]:
    """Unwind one strongly connected component off the Tarjan stack."""
    component = []
    while True:
        popped = stack.pop()
        on_stack.discard(popped)
        component.append(popped)
        if popped == root:
            return sorted(component)


def metrics(graph: dict[str, set[str]]) -> dict[str, tuple[int, int, float]]:
    """module -> (fan_in, fan_out, instability)"""
    fan_in: dict[str, int] = defaultdict(int)
    for deps in graph.values():
        for dep in deps:
            fan_in[dep] += 1

    out: dict[str, tuple[int, int, float]] = {}
    for name, deps in graph.items():
        ce, ca = len(deps), fan_in[name]
        instability = ce / (ca + ce) if (ca + ce) else 0.0
        out[name] = (ca, ce, instability)
    return out


def iter_python_files(paths: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(p for p in path.rglob("*.py") if "__pycache__" not in p.parts)
        elif path.suffix == ".py" and path.is_file():
            found.add(path)
    return sorted(found)


def _judged_prefixes(paths: list[Path]) -> list[str] | None:
    """Which modules the caller asked to be judged; None means all of them."""
    prefixes = []
    for path in paths:
        resolved = path if path.is_absolute() else REPO_ROOT / path
        try:
            rel = resolved.resolve().relative_to(SRC_ROOT.resolve())
        except ValueError:
            continue
        if not rel.parts:
            return None
        prefixes.append(".".join(rel.with_suffix("").parts))
    return prefixes or None


def _print_cycles(cycles: list[list[str]], module_count: int) -> bool:
    if not cycles:
        print(f"Dependency cycles: none across {module_count} modules")
        return False
    print(f"Dependency cycles ({len(cycles)} found):\n")
    for cycle in cycles:
        print(f"  cycle of {len(cycle)}:")
        for name in cycle:
            print(f"      {name}")
    return True


def _print_metrics(title: str, rows: list[tuple[str, tuple[int, int, float]]]) -> bool:
    if not rows:
        return False
    print(f"\n{title}:\n")
    for name, (ca, ce, inst) in rows:
        print(f"  {name}\n      fan-in {ca}, fan-out {ce}, instability {inst:.2f}")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="modules to JUDGE (analysis is always repo-wide)")
    ap.add_argument("--cycles-only", action="store_true", help="report cycles, skip metrics")
    args = ap.parse_args(argv)

    if not SRC_ROOT.is_dir():
        print(f"FAIL  source root not found: {SRC_ROOT}")
        return 1

    # Always global: fan-in and cycles are invisible in a subset.
    all_files = iter_python_files([SRC_ROOT])
    if not all_files:
        print("FAIL  no Python files under src/ -- the check would pass vacuously")
        return 1

    graph = build_graph(all_files)
    cycles = tarjan_scc(graph)

    if args.cycles_only:
        failed = _print_cycles(cycles, len(graph))
        if failed:
            print(
                "\nBLOCKED: an import cycle means these modules cannot be understood, tested or "
                "extracted independently. Break it by moving the shared contract down, not by "
                "deferring an import inside a function."
            )
        return 1 if failed else 0

    # Cycles are owned by the `cycles` check, which runs from `cb` upward. Reporting them here
    # too would fail two checks for one defect and make the fix look twice as large as it is.
    if cycles:
        print(f"({len(cycles)} import cycle(s) present — reported by the `cycles` check)\n")
    failed = False

    prefixes = _judged_prefixes([Path(p) for p in args.paths]) if args.paths else None
    stats = metrics(graph)

    def judged(name: str) -> bool:
        return prefixes is None or any(name == p or name.startswith(f"{p}.") for p in prefixes)

    wide = sorted(
        ((n, s) for n, s in stats.items() if judged(n) and s[1] > MAX_FAN_OUT),
        key=lambda kv: -kv[1][1],
    )
    pain = sorted(
        (
            (n, s)
            for n, s in stats.items()
            if judged(n) and s[0] >= HIGH_FAN_IN and s[2] >= UNSTABLE
        ),
        key=lambda kv: -kv[1][0],
    )

    failed |= _print_metrics(f"Excessive fan-out (> {MAX_FAN_OUT} internal imports)", wide)
    failed |= _print_metrics(
        f"Zone of pain (fan-in >= {HIGH_FAN_IN} and instability >= {UNSTABLE})", pain
    )

    scope_note = "all modules" if prefixes is None else ", ".join(prefixes)
    if not failed:
        print(
            f"\nCoupling: {len(graph)} modules analysed, judging {scope_note} -- all within limits"
        )
        return 0

    print(f"\nBLOCKED: coupling thresholds exceeded (judging {scope_note}).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
