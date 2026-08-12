# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How each quality tool is invoked — one argv builder per check.

Split out of `scripts/quality.py` (2026-08-12, `TECH-026`). That file sat at 595/600 against the
RED threshold while a fifth whole-repo check needed adding, and the project's rule is that headroom
comes from structure rather than from condensing prose. This is the part that grows every time a
check is added, so it is the part that had to move.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from _venv import venv_python

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = venv_python()
MAX_COGNITIVE_COMPLEXITY = 15


def _script(name: str) -> list[str]:
    return [PY, str(REPO_ROOT / "scripts" / name)]


def _ruff(paths: list[Path]) -> list[str]:
    return [PY, "-m", "ruff", "check", *(str(p) for p in paths)]


def _format(paths: list[Path]) -> list[str]:
    # --check never writes; `ruff format` is the fix and the failure message says so.
    return [PY, "-m", "ruff", "format", "--check", *(str(p) for p in paths)]


def _mypy(paths: list[Path]) -> list[str]:
    return [PY, "-m", "mypy", *(str(p) for p in paths)]


def _tach(_paths: list[Path]) -> list[str]:
    return [PY, "-m", "tach", "check"]


def _complexipy(paths: list[Path]) -> list[str]:
    """`TECH-023`: the ratchet, not raw complexipy.

    Running the tool directly meant the gate was red on all 97 known violations forever, so it was
    read as background noise and nothing blocked a 98th. `check_complexity.py` runs the same tool
    with the same threshold and compares against a frozen per-function baseline: the known set may
    fall, never rise, and nothing new may join it.
    """
    return [*_script("check_complexity.py"), *(str(p) for p in paths)]


def _file_sizes(paths: list[Path]) -> list[str]:
    return [*_script("check_file_sizes.py"), *(str(p) for p in paths)]


def _test_basenames(paths: list[Path]) -> list[str]:
    return [*_script("check_test_basenames.py"), *(str(p) for p in paths)]


def _useless_asserts(paths: list[Path]) -> list[str]:
    return [*_script("check_useless_asserts.py"), *(str(p) for p in paths)]


def _suppressions(paths: list[Path]) -> list[str]:
    return [*_script("check_suppressions.py"), *(str(p) for p in paths)]


def _class_health(paths: list[Path]) -> list[str]:
    return [*_script("check_class_health.py"), *(str(p) for p in paths)]


def _coupling(paths: list[Path]) -> list[str]:
    return [*_script("check_coupling.py"), *(str(p) for p in paths)]


def _cycles(paths: list[Path]) -> list[str]:
    return [*_script("check_coupling.py"), "--cycles-only", *(str(p) for p in paths)]


def _conventions(paths: list[Path]) -> list[str]:
    return [*_script("check_conventions.py"), *(str(p) for p in paths)]


def _whole_repo(script: str) -> Callable[[list[Path]], list[str]]:
    """Whole-repo check; ignores the changed-path list. Collapsed from identical wrappers."""
    return lambda _paths: _script(script)
