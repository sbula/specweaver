# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Telling "the tool reported nothing" apart from "the tool never ran".

Extracted from ``runner.py`` (TECH-031) because all three QA paths needed the same answer and
none of them had it. A toolchain that is not installed read as a *clean run*: ``python -m pytest``
with no pytest leaves stdout empty and exits 1, which parses to ``passed=0 failed=0 errors=0`` —
indistinguishable from a project with no tests, and from a caller's view, from success. Ruff's
empty stdout parses identically to its own ``[]``, and an empty tach stdout reads as no
violations.

**The QA gate could certify runs that never happened** — a vacuous proof inside the mechanism
whose whole job is to prevent them, and why the container prepare-phase defects around it went
unnoticed for so long.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.sandbox.execution.models import SubprocessResult

logger = logging.getLogger(__name__)

#: Truncation for the reported reason — a stderr line can be an entire traceback.
_MAX_REASON = 200


def did_not_run(result: SubprocessResult, tool: str) -> str | None:
    """Why `tool` never executed, or None if it ran and reached a verdict.

    The discriminator is **empty stdout, not the exit code**. Keying on the exit code was tried
    and broke `sw implement` against a fresh project: pytest exits **4** for a `tests/` directory
    that does not exist yet, having run correctly and printed `no tests ran in 0.00s`. Exit 4 and
    exit 5 both mean the tool reached a verdict; only a tool that never started says nothing.
    """
    if result.exit_code == 0 or result.stdout.strip():
        return None

    detail = (result.stderr or "").strip().splitlines()
    reason = detail[-1][:_MAX_REASON] if detail else f"{tool} exited {result.exit_code}"
    logger.error("PythonQARunner: %s produced no output — %s", tool, reason)
    return f"{tool} did not run: {reason}"
