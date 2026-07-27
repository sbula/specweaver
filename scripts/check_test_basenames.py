#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every test file must have a repo-unique basename.

This is not style. On 2026-07-26 a refactor renamed a private helper, and the grep for stale
references was truncated with ``head -5``. All five hits came from one ``test_cli_pipelines.py``;
the identically-named file two directories away went unnoticed. Result: ``ImportError`` at
collection and **5806 tests never ran** — a green targeted run had reported success minutes
earlier.

Duplicate basenames cause two distinct failures:

* **Search truncation hides a twin.** Any "find every reference" sweep that caps its output can
  silently miss the duplicate, and the two look identical in the results.
* **Failure output is ambiguous.** ``test_cli_pipelines.py::test_resolve`` does not say which file,
  so a CI failure cannot be located without searching.

24 basenames covered 90 files before this check existed.

Usage:
    python scripts/check_test_basenames.py [tests_root]

Exit code 1 on any duplicate. Name the file for its subject — the language, the module, the
capability — not for the structural directory it happens to sit in (`interfaces` and `core` are
scaffolding, not subjects).
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def duplicate_basenames(tests_root: Path) -> dict[str, list[Path]]:
    """Map each repeated test basename to every path carrying it."""
    by_name: dict[str, list[Path]] = collections.defaultdict(list)
    for path in sorted(tests_root.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        by_name[path.name].append(path)
    return {name: paths for name, paths in by_name.items() if len(paths) > 1}


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

    total = sum(1 for p in root.rglob("test_*.py") if "__pycache__" not in p.parts)
    if not total:
        print(f"FAIL  no test files found under {root} — the check would pass vacuously")
        return 1

    dupes = duplicate_basenames(root)
    if not dupes:
        print(f"Test basename check: {total} file(s), all unique")
        return 0

    affected = sum(len(v) for v in dupes.values())
    print(f"Test basename check: {total} file(s), {len(dupes)} duplicated name(s)\n")
    for name, paths in sorted(dupes.items()):
        print(f"  {name}")
        for p in paths:
            print(f"      {p.as_posix()}")
    print(
        f"\nBLOCKED: {affected} file(s) share {len(dupes)} basename(s). Rename each for its "
        "subject (language, module, capability), not for the structural directory it sits in."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
