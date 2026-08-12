# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Resolving the project virtualenv's interpreter and console scripts.

Split out of `scripts/quality.py` (2026-08-12, `TECH-026`), which had an identical copy in
`scripts/tests.py` — two places to keep in step for a thing with one correct answer. The extraction
was forced by `quality.py` sitting at 595/600 against the RED threshold while a fifth whole-repo
check needed adding: the project's own rule is that headroom comes from structure, not from
condensing prose, and a duplicated helper is the honest thing to remove first.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> str:
    """Prefer the project venv over whatever `python` happens to be on PATH.

    Measured on this repo: system Python has ruff/mypy/tach but NOT complexipy, while `.venv` has
    all four. Resolving this per-invocation avoids a gate that passes or fails depending on which
    shell it was launched from.
    """
    for rel in ("Scripts/python.exe", "bin/python"):
        candidate = REPO_ROOT / ".venv" / rel
        if candidate.exists():
            return str(candidate)
    return sys.executable


def venv_tool(name: str) -> str | None:
    """Locate a console-script entry point (some tools have no importable __main__)."""
    for rel in (f"Scripts/{name}.exe", f"bin/{name}"):
        candidate = REPO_ROOT / ".venv" / rel
        if candidate.exists():
            return str(candidate)
    return None
