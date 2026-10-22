#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The numbers the README's Testing section states, measured now.

    .venv/bin/python scripts/readme_counts.py

Tests per tier come from `pytest --collect-only`, with every marker included (`-m ''`) except where
a tier is a marker. Mutants are those of campaigns that are not retired. Recount before calling a
feature ready, and copy the numbers by hand: the README is prose, not a template.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES = REPO_ROOT / "docs" / "roadmap" / "features"
PY = sys.executable

#: name -> (path, marker expression; None keeps pyproject's default deselection)
TIERS: dict[str, tuple[str, str | None]] = {
    "unit": ("tests/unit", ""),
    "integration": ("tests/integration", ""),
    "e2e": ("tests/e2e", ""),
    "manual": ("tests/manual", ""),
    "all": (".", ""),
    "live": (".", "live"),
    "default": (".", None),
}

_COLLECTED = re.compile(r"(?:(\d+)(?:/\d+)?|no) tests? collected(.*)$")


def collected(output: str) -> int:
    """The selected count from pytest's last collect line; refuse output that has none."""
    for line in reversed(output.strip().splitlines()):
        match = _COLLECTED.search(line.strip(" ="))
        if match:
            if "error" in match.group(2):
                raise ValueError(f"collection had errors: {line.strip()}")
            return int(match.group(1) or 0)
    raise ValueError("no collect line in pytest output")


def test_counts(
    run: Callable[[list[str]], subprocess.CompletedProcess[str]],
) -> dict[str, int]:
    counts = {}
    for name, (path, marker) in TIERS.items():
        cmd = [PY, "-m", "pytest", path, "--collect-only", "-q", "-p", "no:randomly"]
        if marker is not None:
            cmd += ["-m", marker]
        counts[name] = collected(run(cmd).stdout)
    return counts


def mutant_counts(corpora: Iterable[Path]) -> tuple[int, int]:
    """(corpus files, mutants in campaigns that are not retired)."""
    files = mutants = 0
    for path in corpora:
        files += 1
        for campaign in json.loads(path.read_text(encoding="utf-8"))["campaigns"]:
            if not campaign.get("retired"):
                mutants += len(campaign["mutants"])
    return files, mutants


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)


def main() -> int:
    try:
        tiers = test_counts(_run)
    except ValueError as exc:  # expected: a broken collection must not print a number
        print(f"could not count: {exc}", file=sys.stderr)
        return 1
    print(" ".join(f"{name}={count}" for name, count in tiers.items()))
    files, mutants = mutant_counts(sorted(FEATURES.glob("*/*/*_mutants.json")))
    print(f"corpora={files} mutants={mutants}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
