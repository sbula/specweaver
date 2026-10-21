# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A nightly pytest run's verdict: written once by the run, read by `--status` and the handover.

Shared by `scripts/live.py` (real models) and `scripts/toolchain.py` (real build tools).
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess
    from pathlib import Path

MAX_AGE_HOURS = 48


def record(
    proc: subprocess.CompletedProcess[str], started: float, result: Path, note: str = ""
) -> str:
    """Write the run's verdict and full log beside `result`; return its one-line summary."""
    lines = proc.stdout.strip().splitlines()
    summary = (lines[-1] if lines else proc.stderr.strip()[-300:]) + note
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(
        json.dumps({"at": started, "passed": proc.returncode == 0, "summary": summary}),
        encoding="utf-8",
    )
    (result.parent / "last.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return summary


def status(path: Path, label: str) -> tuple[bool, str]:
    """Whether the last `label` run passed recently, and one line saying so."""
    if not path.is_file():
        return (
            False,
            f"{label} run: never ran — it runs in the nightly session "
            "(`python scripts/mutation.py --install-timer`)",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    hours = (time.time() - data["at"]) / 3600
    if hours > MAX_AGE_HOURS:
        return False, f"{label} run: last result is older than {MAX_AGE_HOURS}h ({hours:.0f}h)"
    if not data["passed"]:
        log = path.parent / "last.log"
        return False, f"{label} run: FAILED {hours:.0f}h ago — {data['summary']} ({log})"
    return True, f"{label} run: passed {hours:.0f}h ago — {data['summary']}"
