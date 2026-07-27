#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Find assertions that cannot fail.

A test that cannot fail is worse than no test: it reports green and suppresses the gap from every
later analysis. On 2026-07-26 a single ``assert len(edges) >= 0`` — always true for a length — sat
in ``test_builder_ingest_ast_edge_delta``, whose stated purpose is *"Re-ingesting an updated AST
cleanly performs edge deletion (Story 4)"*. Pulling that thread showed the fixture also fed a
``"calls"`` key that **nothing in the graph module reads**, so the edge it meant to delete was never
created. One weak assertion kept a whole story unverified for the test's entire life.

Only mechanically-decidable patterns are reported. That restraint is deliberate: a first attempt at
a broader hollow-test detector returned 630 candidates, most of them noise, which is unusable — a
detector you cannot trust is as bad as a test you cannot trust.

  1. literal             assert True / assert 1 / assert "text"
  2. self-comparison     assert x == x
  3. always-true bound   assert len(x) >= 0  /  assert len(x) > -1
  4. vacuous isinstance  assert isinstance(x, object)
  5. mock truthiness     assert m / assert m.attr  where m = MagicMock()
                         — every MagicMock attribute is truthy, so it always passes

Usage:
    python scripts/check_useless_asserts.py [tests_root]

Exit code 1 on any finding. This detector has its own tests, including a synthetic file containing
one of each pattern plus a legitimate assertion — see tests/unit/scripts/.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MOCK_FACTORIES = {"Mock", "MagicMock", "AsyncMock", "NonCallableMock"}


class UselessAssertVisitor(ast.NodeVisitor):
    """Collects ``(lineno, pattern, source)`` for assertions that cannot fail."""

    def __init__(self) -> None:
        self.mock_names: set[str] = set()
        self.hits: list[tuple[int, str, str]] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            func = node.value.func
            name = getattr(func, "id", getattr(func, "attr", None))
            if name in MOCK_FACTORIES:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.mock_names.add(target.id)
        self.generic_visit(node)

    @staticmethod
    def _root_name(node: ast.expr) -> str | None:
        while isinstance(node, ast.Attribute):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    def visit_Assert(self, node: ast.Assert) -> None:
        test = node.test
        if isinstance(test, ast.Constant) and bool(test.value):
            self.hits.append((node.lineno, "literal", ast.unparse(test)))
        elif isinstance(test, ast.Compare) and len(test.ops) == 1:
            self._check_compare(node, test)
        elif isinstance(test, ast.Call) and getattr(test.func, "id", "") == "isinstance":
            if len(test.args) == 2 and getattr(test.args[1], "id", "") == "object":
                self.hits.append((node.lineno, "vacuous-isinstance", ast.unparse(test)))
        elif isinstance(test, ast.Name | ast.Attribute):
            root = self._root_name(test)
            if root and root in self.mock_names:
                self.hits.append((node.lineno, "mock-truthiness", ast.unparse(test)))
        self.generic_visit(node)

    def _check_compare(self, node: ast.Assert, test: ast.Compare) -> None:
        left, op, right = test.left, test.ops[0], test.comparators[0]
        if isinstance(op, ast.Eq) and ast.unparse(left) == ast.unparse(right):
            self.hits.append((node.lineno, "self-comparison", ast.unparse(test)))
            return
        is_len = isinstance(left, ast.Call) and getattr(left.func, "id", "") == "len"
        if is_len and isinstance(right, ast.Constant):
            always = (isinstance(op, ast.GtE) and right.value == 0) or (
                isinstance(op, ast.Gt) and right.value == -1
            )
            if always:
                self.hits.append((node.lineno, "always-true-bound", ast.unparse(test)))


def scan_source(source: str) -> list[tuple[int, str, str]]:
    """Findings for one file's source text. Unparseable input yields nothing."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = UselessAssertVisitor()
    visitor.visit(tree)
    return visitor.hits


def scan_tree(tests_root: Path) -> list[tuple[Path, int, str, str]]:
    out: list[tuple[Path, int, str, str]] = []
    for path in sorted(tests_root.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out.extend((path, line, kind, src) for line, kind, src in scan_source(source))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("tests_root", nargs="?", default=str(REPO_ROOT / "tests"))
    args = ap.parse_args(argv)

    root = Path(args.tests_root)
    if not root.is_dir():
        print(f"FAIL  tests root not found: {root}")
        return 1

    findings = scan_tree(root)
    if not findings:
        print("Useless-assert check: no assertion that cannot fail")
        return 0

    for path, line, kind, src in findings:
        print(f"  {path.as_posix()}:{line}  [{kind}]  assert {src}")
    print(
        f"\nBLOCKED: {len(findings)} assertion(s) cannot fail. Assert the relationship the test "
        "name claims, then break the behaviour on purpose and confirm it goes red."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
