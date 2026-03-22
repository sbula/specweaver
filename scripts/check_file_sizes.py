#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Check Python file sizes to catch over-large modules.

Thresholds (src/ files):
  - up to 450 lines:  GREEN  (ok)
  - 451 to 600 lines: YELLOW (warning)
  - above 600 lines:  RED    (error, blocks pre-commit)

Test files (tests/) use src thresholds x 1.5:
  - up to 675 lines:  GREEN  (ok)
  - 676 to 900 lines: YELLOW (warning)
  - above 900 lines:  RED    (error, blocks pre-commit)

Exit code 1 if any file exceeds the RED threshold.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Thresholds
SRC_WARN = 450
SRC_ERROR = 600
TEST_SCALE = 1.5
TEST_WARN = int(SRC_WARN * TEST_SCALE)   # 675
TEST_ERROR = int(SRC_ERROR * TEST_SCALE)  # 900


def _check_dir(
    root: Path, search_dir: str, warn: int, error: int,
) -> tuple[int, int]:
    """Check all .py files in a directory. Returns (errors, warnings)."""
    errs = warns = 0
    path = root / search_dir
    if not path.exists():
        return 0, 0

    for py_file in sorted(path.rglob("*.py")):
        lines = len(py_file.read_text(encoding="utf-8").splitlines())
        rel = py_file.relative_to(root)

        if lines > error:
            print(f"  RED:    {rel} ({lines} lines > {error})")
            errs += 1
        elif lines > warn:
            print(f"  YELLOW: {rel} ({lines} lines > {warn})")
            warns += 1

    return errs, warns


def main() -> int:
    root = Path(".")
    errors = warnings = 0

    for search_dir, warn, error in [
        ("src", SRC_WARN, SRC_ERROR),
        ("tests", TEST_WARN, TEST_ERROR),
    ]:
        e, w = _check_dir(root, search_dir, warn, error)
        errors += e
        warnings += w

    if errors > 0 or warnings > 0:
        print(f"\nFile size check: {errors} error(s), {warnings} warning(s)")
    else:
        print("File size check: all files within limits")

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
