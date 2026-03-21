#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Check Python file sizes to catch over-large modules.

Thresholds:
  - src/ files:   500 lines = error
  - tests/ files: 800 lines = warning (test files tend to be longer)

Exit code 1 if any src/ file exceeds the error threshold.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(".")
    errors = 0
    warnings = 0

    src_threshold = 500
    test_threshold = 800

    for search_dir, threshold, label in [
        ("src", src_threshold, "ERROR"),
        ("tests", test_threshold, "WARNING"),
    ]:
        search_path = root / search_dir
        if not search_path.exists():
            continue

        for py_file in sorted(search_path.rglob("*.py")):
            lines = len(py_file.read_text(encoding="utf-8").splitlines())
            if lines > threshold:
                rel = py_file.relative_to(root)
                print(f"  {label}: {rel} ({lines} lines > {threshold})")
                if label == "ERROR":
                    errors += 1
                else:
                    warnings += 1

    if errors > 0 or warnings > 0:
        print(f"\nFile size check: {errors} error(s), {warnings} warning(s)")
    else:
        print("File size check: all files within limits")

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
