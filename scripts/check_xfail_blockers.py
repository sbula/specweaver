#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A strict xfail names its blocking capability, and goes when that capability ships.

`ADR-004` clause 4: a test is written as soon as the interface it exercises is defined, not when the
implementation lands. Where the implementation is absent it is committed as
`pytest.mark.xfail(strict=True)` naming the blocker, so it fails first and proves it tests the path
at the moment it turns green. That is the whole value — a test written after the code is green on its
first run and asserts the present rather than a contract.

**Two ways it decays, and both are findings here.**

* **The blocker ships and the marker stays.** `strict=True` does make the suite complain, since an
  unexpected pass is a failure — but only once a reader interprets that as "the marker is stale"
  rather than "the test is broken", and the tempting fix is to delete the assertion. The registry
  already knows the answer: the capability is `✅` in the capability matrix.
* **The reason names no blocker.** Then nothing can ever judge the marker stale, and it becomes a
  permanent exemption. That is how every suppression list in this repo decayed, so a named blocker is
  part of the contract rather than a convention.

**Only `strict=True`.** A lenient xfail makes no claim about when it should start passing, so there
is nothing to judge. Narrow on purpose: a rule that fires on markers it cannot reason about gets
switched off, and takes the rule it protects with it.

**A blocker absent from the matrix is a finding, not a pass** — `TECH-032`'s lesson applied per row.

Zero-tolerance. Clause 4's markers do not exist yet, so there is no legacy set to carry.

Usage:
    python scripts/check_xfail_blockers.py [--root DIR] [--list]

Exit 0 when clean, 1 on any finding, 2 when the capability matrix cannot be found.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Authoritative for capability status, per `specweaver-ticket` Phase 1. The topic docs repeat these
#: glyphs and drift.
MATRIX = "capability_matrix.md"

#: `✅ D-VAL-03` inside one code span, which is how the matrix writes its cells.
_MATRIX_CELL = re.compile(r"`([^\s`]+)\s+([A-E]-[A-Z]+-\d+)`")

#: A capability id inside an xfail reason.
_CAPABILITY = re.compile(r"\b([A-E]-[A-Z]+-\d+)\b")

#: Status glyphs that mean the blocker has shipped, so the marker is stale.
DELIVERED = frozenset({"✅", "🟢"})

#: Reported for a reason that names no capability at all.
NO_BLOCKER = "(none named)"

#: Reported for a blocker the matrix does not know.
UNKNOWN = "?"


@dataclass(frozen=True)
class StaleMarker:
    """A strict xfail that can no longer be justified by the registry."""

    path: str
    line: int
    blocker: str
    status: str


def capability_status(roadmap: Path) -> dict[str, str]:
    """Map capability ID -> status glyph, read from the capability matrix.

    Raises:
        FileNotFoundError: the matrix is absent. A checker that cannot find its subject must say so
            rather than return `{}` and pass every marker by accident.
    """
    return {
        cid: glyph
        for glyph, cid in _MATRIX_CELL.findall((roadmap / MATRIX).read_text(encoding="utf-8"))
    }


def _is_strict_xfail(node: ast.expr) -> bool:
    """`@pytest.mark.xfail(strict=True, ...)`, and nothing looser."""
    if not isinstance(node, ast.Call):
        return False
    target = node.func
    if not (isinstance(target, ast.Attribute) and target.attr == "xfail"):
        return False
    return any(
        kw.arg == "strict" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in node.keywords
    )


def _reason_of(node: ast.Call) -> str:
    for kw in node.keywords:
        if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return ""


def _markers(path: Path) -> list[tuple[int, str]]:
    """`(line, reason)` for each strict xfail decorator in `path`."""
    found: list[tuple[int, str]] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            if _is_strict_xfail(decorator):
                assert isinstance(decorator, ast.Call)
                found.append((decorator.lineno, _reason_of(decorator)))
    return found


def stale_markers(roadmap: Path, tests_root: Path) -> list[StaleMarker]:
    """Every strict xfail whose blocker has shipped, is unknown, or was never named."""
    status = capability_status(roadmap)

    out: list[StaleMarker] = []
    for path in sorted(tests_root.rglob("test_*.py")):
        try:
            markers = _markers(path)
        except (SyntaxError, UnicodeDecodeError):
            continue
        for line, reason in markers:
            blockers = sorted(set(_CAPABILITY.findall(reason)))
            rel = path.as_posix()
            if not blockers:
                out.append(StaleMarker(rel, line, NO_BLOCKER, UNKNOWN))
                continue
            for blocker in blockers:
                glyph = status.get(blocker, UNKNOWN)
                if glyph in DELIVERED or glyph == UNKNOWN:
                    out.append(StaleMarker(rel, line, blocker, glyph))
    return out


def _print(found: list[StaleMarker]) -> None:
    print(f"Strict xfails the registry no longer justifies ({len(found)}):\n")
    for marker in found:
        if marker.blocker == NO_BLOCKER:
            why = "the reason names no capability, so nothing can ever judge it stale"
        elif marker.status == UNKNOWN:
            why = "blocker is not in the capability matrix"
        else:
            why = f"blocker has shipped ({marker.status})"
        print(f"  {marker.path}:{marker.line}  {marker.blocker} — {why}")
    print(
        "\nA strict xfail is a promise that a test fails only because its blocker is unbuilt "
        "(`ADR-004` clause 4).\nWhen the blocker ships the marker goes and the test stands on its "
        "own; when the reason names no\nblocker the marker is a permanent exemption wearing a "
        "deadline."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(REPO_ROOT), help="repository root to judge")
    ap.add_argument("--list", action="store_true", help="print findings without failing")
    args = ap.parse_args(argv)

    root = Path(args.root)
    roadmap = root / "docs" / "roadmap"
    if not (roadmap / MATRIX).is_file():
        print(f"could not run: capability matrix not found under {roadmap}", file=sys.stderr)
        return 2

    tests_root = root / "tests"
    if not tests_root.is_dir():
        print("Strict xfail check: no tests tree — nothing to judge.")
        return 0

    found = stale_markers(roadmap, tests_root)
    if found and not args.list:
        _print(found)
        return 1
    if found:
        _print(found)
        return 0

    print("Strict xfail check: every strict xfail names an unbuilt blocker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
