#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly real-model run: every `live` test, against real providers.

    python scripts/live.py                  # run the live tests now
    python scripts/live.py --status         # the last night's verdict; exit 1 unless it passed

The nightly session (`scripts/_mutation_timer.py`) runs it before the mutation corpus. The live
tests read their keys from `~/.specweaver/keys.env`, as SpecWeaver does; no value is printed.
Each live test sets its own spend limit; together they stay under USD 0.10 a night.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT = REPO_ROOT / ".tmp" / "live" / "last.json"
#: A result older than this means a night was missed.
MAX_AGE_HOURS = 48


def run() -> int:
    started = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "live", "-q", "-p", "no:randomly", "tests/e2e"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = proc.stdout.strip().splitlines()
    summary = lines[-1] if lines else proc.stderr.strip()[-300:]
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps({"at": started, "passed": proc.returncode == 0, "summary": summary}),
        encoding="utf-8",
    )
    (RESULT.parent / "last.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    print(summary)
    return proc.returncode


def status(path: Path = RESULT) -> tuple[bool, str]:
    """Whether the last live run passed recently, and one line saying so."""
    if not path.is_file():
        return (
            False,
            "live run: never ran — it runs in the nightly session (`python scripts/mutation.py --install-timer`)",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    hours = (time.time() - data["at"]) / 3600
    if hours > MAX_AGE_HOURS:
        return False, f"live run: last result is older than {MAX_AGE_HOURS}h ({hours:.0f}h)"
    if not data["passed"]:
        return False, f"live run: FAILED {hours:.0f}h ago — {data['summary']} (.tmp/live/last.log)"
    return True, f"live run: passed {hours:.0f}h ago — {data['summary']}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--status", action="store_true", help="the last verdict; exit 1 unless passed")
    args = ap.parse_args(argv)
    if args.status:
        ok, line = status()
        print(line)
        return 0 if ok else 1
    return run()


if __name__ == "__main__":
    sys.exit(main())
