#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Check Python file sizes to catch over-large modules.

Thresholds (src/ and scripts/ files):
  - up to 450 lines:  GREEN  (ok)
  - 451 to 600 lines: YELLOW (warning)
  - above 600 lines:  RED    (error, blocks pre-commit)

Test files (tests/) carry a higher allowance than src, set explicitly rather than derived:
  - up to 800 lines:  GREEN  (ok)
  - 801 to 900 lines: YELLOW (warning)
  - above 900 lines:  RED    (error, blocks pre-commit)

800 is a deliberate project decision (user, 2026-07-26), not a scaled guess. A thorough test file
legitimately runs long: the four adversarial buckets, a table of hostile inputs, and a docstring
explaining what each seam proves all cost lines, and splitting a file that covers ONE contract
across several just to satisfy a threshold makes the coverage harder to audit, not easier.

Accepts explicit paths (files or directories) so `scripts/quality.py` can run it diff-scoped; with
no arguments it sweeps the default trees. Thresholds are chosen per FILE, not per invocation, so a
mixed list of src and test paths is scored correctly.

Exit code 1 if any file exceeds the RED threshold.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Thresholds
SRC_WARN = 450
SRC_ERROR = 600
#: Set explicitly, not scaled from SRC_WARN — see the module docstring.
TEST_WARN = 800
TEST_ERROR = 900

DEFAULT_TREES = ("src", "tests", "scripts")


def thresholds_for(path: Path) -> tuple[int, int]:
    """Test files get the higher allowance; everything else gets the src limits."""
    return (TEST_WARN, TEST_ERROR) if "tests" in path.parts else (SRC_WARN, SRC_ERROR)


def iter_python_files(paths: list[Path]) -> list[Path]:
    """Expand a mixed list of files and directories to the .py files it covers."""
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(p for p in path.rglob("*.py") if "__pycache__" not in p.parts)
        elif path.suffix == ".py" and path.is_file():
            found.add(path)
    return sorted(found)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="files or directories (default: src, tests, scripts)")
    args = ap.parse_args(argv)

    explicit = bool(args.paths)
    raw = [Path(p) for p in args.paths] if explicit else [Path(t) for t in DEFAULT_TREES]

    missing = [p for p in raw if not p.exists()]
    if missing:
        for path in missing:
            print(f"  FAIL:   path not found: {path}")
        return 1

    files = iter_python_files(raw)
    if not files and not explicit:
        # A default sweep that finds nothing is a broken checkout, not a clean bill of health.
        print("File size check: FAIL — no Python files found in the default trees")
        return 1

    errors = warnings = 0
    for py_file in files:
        warn, error = thresholds_for(py_file)
        lines = len(py_file.read_text(encoding="utf-8").splitlines())
        try:
            rel = py_file.relative_to(REPO_ROOT)
        except ValueError:
            rel = py_file

        if lines > error:
            print(f"  RED:    {rel} ({lines} lines > {error})")
            errors += 1
        elif lines > warn:
            print(f"  YELLOW: {rel} ({lines} lines > {warn})")
            warnings += 1

    if errors or warnings:
        print(
            f"\nFile size check: {errors} error(s), {warnings} warning(s) over {len(files)} file(s)"
        )
    else:
        print(f"File size check: all {len(files)} file(s) within limits")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
