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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

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
#:
#: `__tablename__` and `__table_args__` are the SQLAlchemy equivalent, added by `TECH-035` on the
#: same evidence: all 13 mapped classes in `src` declare `__tablename__`, so it distinguishes none
#: of them. It mattered — `Task` was the single oversized class in the baseline at 16 attributes,
#: and has **14** real mapped columns against a limit of 15. A named list rather than "ignore every
#: dunder", so `__slots__` and friends still count.
IGNORED_ATTRIBUTES = {"model_config", "__tablename__", "__table_args__"}


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

    def unmeasurable(self) -> bool:
        """A class with methods but no cohesion graph — every one of them is stateless.

        `incohesive()` is `lcom4 > MAX_LCOM4`, so a score of 0 **passes**. That is a fair reading
        for an abstract base whose methods are all stubs, but it must not be indistinguishable
        from "measured and fine" in the output — the exact confusion `TECH-035` exists to end.
        """
        return self.lcom4 == 0 and self.method_count >= 2


def _load_sibling(module_name: str) -> ModuleType:
    """Load a same-directory script by path — `scripts/` is not an importable package."""
    import importlib.util

    path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        msg = f"cannot load {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


#: `TECH-035` freezes the known offenders in a sibling, matching R6/R7 and `check_complexity`.
#: Re-exported so this file stays the one place a reader looks for "why was my class rejected".
_ratchet = _load_sibling("_class_health_baseline")


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _rebinds_self(node: ast.AST) -> bool:
    """True when a nested scope introduces its OWN `self`, rather than closing over the outer one.

    The distinction is the whole point, and getting it wrong breaks the measurement in opposite
    directions:

    - a nested **class**'s methods take their own `self`, a different object entirely — attributing
      their attributes outward is the leak this exists to stop;
    - a nested **closure** (`def _wrapper(): ... self._results[x] = y`) has no `self` parameter and
      captures the enclosing method's, so its attributes ARE the outer method's and must count.

    Skipping both indiscriminately silently decoupled `EventBridge.start_run` from `get_result` —
    the write to `self._results` happens inside exactly such a closure.
    """
    if isinstance(node, ast.ClassDef):
        return True
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        return False
    args = node.args
    return any(a.arg == "self" for a in (*args.posonlyargs, *args.args, *args.kwonlyargs))


def _self_attributes(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Attributes reached through `self` inside one method, excluding scopes that rebind `self`.

    `ast.walk` does not stop at a scope boundary, so a nested class's `self` was attributed to the
    enclosing method. `TECH-035` found it in `MarkdownCodeStructure._find_target_block`, which
    touches no state at all but builds a local `MarkdownBodyBlock` whose `__init__` assigns four
    fields: those four made a stateless helper look like its own cohesion component **and** added
    four phantom attributes to the god-object count.
    """
    found: set[str] = set()
    stack: list[ast.AST] = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if _rebinds_self(node):
            continue
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            found.add(node.attr)
        stack.extend(ast.iter_child_nodes(node))
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


def _is_constant(name: str) -> bool:
    """True for an UPPER_CASE member — a constant by PEP 8, not instance state.

    `MCPExplorerTool.role` is `return self.NO_ROLE`, where `NO_ROLE: str = "no_role"` lives on
    `BaseTool`. That is exactly as stateless as `return "no_role"`, which is already excluded, but
    the constant is reached through `self` so it read as state and made the property its own
    component. Detected by naming rather than by declaration because the constant is usually
    inherited, and a base class is not in scope when one class body is analysed. `TECH-035`.
    """
    return name.isupper() or (name.replace("_", "").isupper() and any(c.isalpha() for c in name))


def _instance_state(touched: set[str], method_names: set[str]) -> set[str]:
    """The members a method reaches that are genuinely per-instance state.

    Sibling method names are handled as call edges, not shared state; constants are shared by
    every instance and so distinguish nothing.
    """
    return {name for name in touched - method_names if not _is_constant(name)}


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
    return not _instance_state(touched, method_names) and not (called & method_names)


def _dispatches_dynamically(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when the method looks up a sibling by name — `getattr(self, ...)`.

    That IS a call to a sibling; the analyser simply cannot say which one, so the only honest
    reading is that it may reach any of them. Without this, an intent dispatcher scores as its own
    component and the metric reports a "split" whose two halves are `run` and everything `run`
    calls -- a refactoring instruction nobody would follow. `TECH-035`.
    """
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "self"
        for node in ast.walk(func)
    )


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

    # LCOM4 over every method except the constructor (see module docstring).
    #
    # A stateless method -- a property returning a literal, an abstract stub, a staticmethod --
    # touches no attribute and so cannot couple to anything through state. Left counted, it is an
    # isolated node BY CONSTRUCTION and adds one component no matter how cohesive the class is:
    # `MarkdownCodeStructure` scored LCOM4=19 with 17 components being a single accessor apiece,
    # a number that says nothing about where to cut and so gets suppressed rather than acted on.
    #
    # `TECH-035`: it is dropped from the COUNT, not from the GRAPH. Removing it outright also
    # removed the edges that ran THROUGH it, stranding its callers as their own components --
    # `extract_endpoints` and `extract_messages` both call `_parse_proto`, so they are coupled by
    # it, and the checker reported them as two independent classes. That single defect accounted
    # for 11 of the 19 classes in the frozen baseline. Keeping the node and ignoring it only when
    # it ends up ALONE preserves the original intent and the edges both.
    graph_nodes = [m.name for m in methods if m.name != "__init__"]
    if len(graph_nodes) < 2:
        report.lcom4 = 1 if graph_nodes else 0
        report.components = [graph_nodes] if graph_nodes else []
        return report

    dynamic = {m.name for m in methods if _dispatches_dynamically(m)}

    # `b in touched[a]` catches a DISPATCH TABLE: `get_extractors` returns
    # `[self._extract_tsdoc, ...]`, which are attribute loads rather than calls, so the call rule
    # alone missed them and `TSStandardsAnalyzer` read as three unrelated classes. Handing a
    # sibling around as a value is coupling exactly as much as invoking it. `TECH-035`.
    edges: set[tuple[str, str]] = set()
    for i, a in enumerate(graph_nodes):
        for b in graph_nodes[i + 1 :]:
            shared = _instance_state(touched[a], method_names) & _instance_state(
                touched[b], method_names
            )
            if (
                shared
                or b in called[a]
                or a in called[b]
                or b in touched[a]
                or a in touched[b]
                or a in dynamic
                or b in dynamic
            ):
                edges.add((a, b))

    by_name = {m.name: m for m in methods}
    report.components = [
        component
        for component in _components(graph_nodes, edges)
        if not (
            len(component) == 1
            and _is_stateless(
                by_name[component[0]],
                touched[component[0]],
                called[component[0]],
                method_names,
            )
        )
    ]
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


def _unfrozen(split: list[ClassReport]) -> list[ClassReport]:
    """The incohesive classes that are new, or worse than their frozen score."""
    baseline = _ratchet.load_baseline()
    if baseline is None:
        print(
            "FAIL  no cohesion baseline — run "
            "`python scripts/check_class_health.py --update-baseline`"
        )
        return split

    scored = {f"{_ratchet._repo_relative(r.path)}::{r.name}": r for r in split}
    worse = dict(
        (name, was)
        for name, was, _ in _ratchet.regressions({k: v.lcom4 for k, v in scored.items()}, baseline)
    )
    better = _ratchet.improvements({k: v.lcom4 for k, v in scored.items()}, baseline)
    if better:
        print(f"{len(better)} class(es) improved — re-freeze with --update-baseline:")
        for name, was, now in better[:8]:
            print(f"    {name}: {was} -> {now or 'cohesive'}")
        print()
    return [report for name, report in scored.items() if name in worse]


def _unfrozen_attributes(fat: list[ClassReport]) -> list[ClassReport]:
    """The oversized classes that are new, or larger than their frozen count."""
    baseline = _ratchet.load_attribute_baseline()
    if baseline is None:
        return fat
    scored = {f"{_ratchet._repo_relative(r.path)}::{r.name}": r for r in fat}
    worse = {
        name
        for name, _was, _now in _ratchet.regressions(
            {k: len(v.attributes) for k, v in scored.items()}, baseline
        )
    }
    return [report for name, report in scored.items() if name in worse]


def _report_unmeasurable(reports: list[ClassReport]) -> None:
    """Say so, on EVERY run, when a class could not be measured rather than measured and passed.

    `TECH-035`: a check that silently does not run is indistinguishable from one that passes, and
    a score of 0 passes. Reported rather than blocked — an abstract base whose methods are all
    stubs is legitimately in this state, and 28 classes in `src` are.
    """
    unmeasurable = [r for r in reports if r.unmeasurable()]
    if unmeasurable:
        print(
            f"  {len(unmeasurable)} class(es) hold no instance state — cohesion is not "
            f"measurable for them, so they are reported rather than scored"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="files or directories (default: src)")
    ap.add_argument("--max-attributes", type=int, default=MAX_ATTRIBUTES)
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="rewrite the cohesion baseline from the current tree; the diff is meant to be reviewed",
    )
    args = ap.parse_args(argv)

    limit: int = args.max_attributes

    raw = [Path(p) for p in args.paths] if args.paths else [REPO_ROOT / "src"]
    missing = [p for p in raw if not p.exists()]
    if missing:
        for path in missing:
            print(f"FAIL  path not found: {path}")
        return 1

    if args.update_baseline:
        scores = _ratchet.measure(*raw)
        attributes = _ratchet.measure_attributes(*raw)
        _ratchet.write_baseline(scores, attributes)
        print(
            f"Class-health baseline written: {len(scores)} incohesive, {len(attributes)} oversized"
        )
        return 0

    files = iter_python_files(raw)
    reports = [r for f in files for r in analyse_file(f)]
    fat = [r for r in reports if r.too_many_attributes(limit)]
    split = [r for r in reports if r.incohesive()]

    # `TECH-035`: the known incohesive set is frozen, so an untouched offender is not this commit's
    # problem. Only a NEW class, or an existing one getting WORSE, blocks. Without this the gate is
    # simultaneously ignored (its `cb` scope is `changed`, so it usually skips) and blocking (the
    # moment a commit touches one, everything goes red on debt it did not create).
    split = _unfrozen(split)
    fat = _unfrozen_attributes(fat)
    failures = {id(r): r for r in [*fat, *split]}

    _report_unmeasurable(reports)

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
