# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly real-toolchain run: `sw implement` with the real pytest, Maven, Gradle, npm, cargo.

    python scripts/toolchain.py             # run the toolchain tier now
    python scripts/toolchain.py --status    # the last night's verdict; exit 1 unless it passed

The nightly session (`scripts/_mutation_timer.py`) runs it after the live run and before the
mutation corpus. A first run downloads packages, so it needs the network; a language whose tool or
registry is missing is skipped and counted in the summary.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _nightly_run

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT = REPO_ROOT / ".tmp" / "toolchain" / "last.json"


def run(result: Path = RESULT) -> int:
    started = time.time()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "toolchain",
            "-q",
            "-rs",
            "-p",
            "no:randomly",
            "tests/e2e",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print(_nightly_run.record(proc, started, result))
    return proc.returncode


def status(path: Path = RESULT) -> tuple[bool, str]:
    """Whether the last toolchain run passed recently, and one line saying so."""
    return _nightly_run.status(path, "toolchain")


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
