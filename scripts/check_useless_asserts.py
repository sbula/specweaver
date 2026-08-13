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
  6. vacuous outcome     a test whose ONLY assertions are outcome codes, at least one of them
                         permissive: assert r.exit_code in (0, 1). Such a test cannot fail on the
                         thing its name claims — `TECH-017`: six stood over the US-25 seam and all
                         stayed green with the capability disabled outright.

                         Function-level, and narrow on purpose. A permissive check STANDING BESIDE
                         real assertions is a weak guard, not a vacuous test; scoring per-assertion
                         instead flags 24 of those and is the noise this module refuses. Scoped to
                         exit/status attributes for the same reason — `x in (0, 1)` on an ordinary
                         value is an ordinary assertion.

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

#: Attribute names whose value encodes success-vs-failure. Pattern 6 applies only to these.
OUTCOME_ATTRS = {"exit_code", "returncode", "status_code"}

#: What counts as success for each. Everything else in the collection is a failure.
_SUCCESS = {"exit_code": {0}, "returncode": {0}, "status_code": {200, 201, 202, 204}}


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


def _is_outcome_compare(test: ast.expr) -> tuple[bool, bool]:
    """Return ``(touches_outcome_code, is_permissive)`` for one assertion."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False, False
    attr = getattr(test.left, "attr", None)
    if attr not in OUTCOME_ATTRS:
        return False, False
    if not isinstance(test.ops[0], ast.In):
        return True, False
    right = test.comparators[0]
    if not isinstance(right, ast.Tuple | ast.List | ast.Set):
        return True, False
    values = [e.value for e in right.elts if isinstance(e, ast.Constant)]
    if len(values) != len(right.elts) or len(values) < 2:
        return True, False
    success = _SUCCESS[attr]
    return True, any(v in success for v in values) and any(v not in success for v in values)


def vacuous_outcome_tests(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Pattern 6: test functions proven by nothing but a permissive outcome code.

    Mock assertions and ``pytest.raises`` count as real proof, so a function using either is left
    alone even if its only bare ``assert`` is an exit code.
    """
    hits: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        body = ast.unparse(node)
        if "assert_called" in body or "assert_awaited" in body or "pytest.raises" in body:
            continue
        asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
        if not asserts:
            continue
        verdicts = [_is_outcome_compare(a.test) for a in asserts]
        if all(touches for touches, _ in verdicts) and any(loose for _, loose in verdicts):
            offender = next(a for a, (_, loose) in zip(asserts, verdicts, strict=True) if loose)
            hits.append((offender.lineno, "permissive-exit-code", ast.unparse(offender.test)))
    return hits


def scan_source(source: str) -> list[tuple[int, str, str]]:
    """Findings for one file's source text. Unparseable input yields nothing."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    visitor = UselessAssertVisitor()
    visitor.visit(tree)
    return sorted(visitor.hits + vacuous_outcome_tests(tree))


def iter_test_files(paths: list[Path]) -> list[Path]:
    """Expand a mixed list of files and directories.

    A directory is globbed for `test_*.py`; a file named explicitly is scanned as given, since a
    caller passing one diff-scoped path means that file regardless of how it is named.
    """
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(p for p in path.rglob("test_*.py") if "__pycache__" not in p.parts)
        elif path.is_file() and path.suffix == ".py":
            found.add(path)
    return sorted(found)


def scan_files(files: list[Path]) -> list[tuple[Path, int, str, str]]:
    out: list[tuple[Path, int, str, str]] = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out.extend((path, line, kind, src) for line, kind, src in scan_source(source))
    return out


def scan_tree(tests_root: Path) -> list[tuple[Path, int, str, str]]:
    return scan_files(iter_test_files([tests_root]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="test files or directories (default: the tests/ tree)")
    args = ap.parse_args(argv)

    raw = [Path(p) for p in args.paths] if args.paths else [REPO_ROOT / "tests"]
    missing = [p for p in raw if not p.exists()]
    if missing:
        for path in missing:
            print(f"FAIL  tests root not found: {path}")
        return 1

    findings = scan_files(iter_test_files(raw))
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
