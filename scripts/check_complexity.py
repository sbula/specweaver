#!/usr/bin/env python
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Cognitive-complexity ratchet — the known set may fall, never rise (`TECH-023`).

`complexipy` has failed the commit gate continuously since 2026-08-02: **97 functions across ~68
files**, spanning nearly every domain. That is not a defect one commit introduced and not one a
commit can incidentally fix, so the gate had settled into permanent red — and a gate that is always
red is one nobody reads. Worse, nothing stopped a 98th appearing.

Freezing the known set turns it back into an enforcing gate. A **new** violation blocks the commit
that introduces it, and so does an **increase** on a function already in the baseline. Neither was
true before.

This is deliberately the same shape as `check_suppressions.py`, R6 and R7: a frozen baseline, a
regression check, and an explicit `--update-baseline` whose diff is meant to be reviewed. What it
is *not* is an allowlist of permanent exemptions — every entry is debt with a number attached, and
the number can only go down.

Usage:
    python scripts/check_complexity.py [path ...]     # default: src
    python scripts/check_complexity.py --update-baseline
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "scripts" / "baselines" / "complexity.json"

#: Must match `MAX_COGNITIVE_COMPLEXITY` in `quality.py`, which is what the gate advertises.
MAX_COMPLEXITY = 15

#: An indented `Name 36  ❌ FAILED` row. The name may be `Class::method` or a bare function.
_ROW = re.compile(r"^\s+(?P<name>\S+)\s+(?P<score>\d+)\s+.*FAILED")

#: A file path at column zero. Anchored on the `.py` suffix rather than "no leading space", because
#: complexipy frames its report with full-width rules that also start at column zero.
_FILE = re.compile(r"^(?P<path>\S+\.py)\s*$")


def parse(output: str) -> dict[str, int]:
    """Turn complexipy's `--failed` report into `{file::function: score}`.

    Keyed by file *and* function because the same function name recurs across modules — three
    different `execute` methods are three different debts.
    """
    found: dict[str, int] = {}
    current: str | None = None
    for line in output.splitlines():
        file_match = _FILE.match(line)
        if file_match:
            current = file_match.group("path").replace("\\", "/")
            continue
        row = _ROW.match(line)
        if row and current:
            found[f"{current}::{row.group('name')}"] = int(row.group("score"))
    return found


def measure(*paths: Path) -> dict[str, int]:
    """Run complexipy over `paths` and parse what failed."""
    exe = REPO_ROOT / ".venv" / "bin" / "complexipy"
    head = [str(exe)] if exe.exists() else [sys.executable, "-m", "complexipy"]
    result = subprocess.run(
        [
            *head,
            *(str(p) for p in paths),
            "--failed",
            "--color",
            "no",
            "--max-complexity-allowed",
            str(MAX_COMPLEXITY),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    return parse(result.stdout)


def load_baseline() -> dict[str, int] | None:
    """The frozen scores, or None when the baseline has never been written."""
    if not BASELINE_PATH.is_file():
        return None
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data.get("functions", {}).items()}


def write_baseline(scores: dict[str, int]) -> None:
    """Freeze the current scores. The diff is meant to be reviewed."""
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps({"functions": dict(sorted(scores.items()))}, indent=2) + "\n", encoding="utf-8"
    )


def regressions(
    current: dict[str, int], baseline: dict[str, int]
) -> list[tuple[str, int | None, int]]:
    """Violations that are new, or worse than they were. `None` for "was not a violation"."""
    worse: list[tuple[str, int | None, int]] = []
    for name, score in sorted(current.items()):
        was = baseline.get(name)
        if was is None or score > was:
            worse.append((name, was, score))
    return worse


def improvements(current: dict[str, int], baseline: dict[str, int]) -> list[tuple[str, int, int]]:
    """Violations that fell, including to zero — i.e. off the report entirely."""
    better: list[tuple[str, int, int]] = []
    for name, was in sorted(baseline.items()):
        now = current.get(name, 0)
        if now < was:
            better.append((name, was, now))
    return better


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="files or directories (default: src)")
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="rewrite the baseline from the current tree; the diff is meant to be reviewed",
    )
    args = ap.parse_args(argv)
    paths = [Path(p) for p in args.paths] or [REPO_ROOT / "src"]

    current = measure(*paths)

    if args.update_baseline:
        write_baseline(current)
        print(f"Complexity baseline written: {len(current)} function(s) over {MAX_COMPLEXITY}")
        return 0

    baseline = load_baseline()
    if baseline is None:
        print(
            f"FAIL  no baseline at {BASELINE_PATH.relative_to(REPO_ROOT).as_posix()} — "
            "run `python scripts/check_complexity.py --update-baseline`"
        )
        return 1

    print(f"Complexity ratchet: {len(current)} function(s) over {MAX_COMPLEXITY}")

    better = improvements(current, baseline)
    if better:
        print(f"\n  {len(better)} improved — re-freeze with --update-baseline:")
        for name, was, now in better[:10]:
            print(f"    {name}: {was} -> {now or 'resolved'}")

    worse = regressions(current, baseline)
    if not worse:
        print("  no function is new or worse than its frozen score")
        return 0

    print(f"\n{len(worse)} complexity regression(s):\n")
    for name, before, after in worse:
        print(f"  {name}: {before if before is not None else 'under threshold'} -> {after}")
    print(
        "\nBLOCKED: extract the sub-steps into named collaborators. The frozen set may fall, "
        "never rise — and nothing new may join it."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
