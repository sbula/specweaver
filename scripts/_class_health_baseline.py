#!/usr/bin/env python
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Cohesion ratchet — the known incohesive classes may improve, never worsen (`TECH-035`).

`check_class_health` failed on a clean tree for an entire working session and **nobody saw it**,
because its commit-gate scope is `changed`: it is skipped whenever a commit touches none of the
offenders, and it reported `nothing in scope` while 20 classes were failing.

That left it in the worst of both states — **ignored, and blocking**. The moment a commit does
touch one of them, the whole gate goes red on debt that commit did not create. `TECH-034` hit
exactly that and had to be landed with the gate failing.

Freezing the known set fixes both halves at once: a *new* incohesive class blocks the commit that
introduces it, an existing one getting *worse* blocks too, and nothing else is collateral damage.

Same shape as `check_suppressions`, R6, R7 and `check_complexity`: frozen baseline, regression
check, explicit `--update-baseline` whose diff is reviewed. It is **not** an allowlist — every
entry carries its `LCOM4`, and that number can only go down.

Lives in a sibling of `check_class_health.py` and is re-exported from it, so a reader still has one
place to look for "why did class health reject my commit".
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "scripts" / "baselines" / "class_health.json"


def _checker() -> ModuleType:
    """Load `check_class_health` by path — `scripts/` is not an importable package."""
    if "check_class_health" in sys.modules:
        return sys.modules["check_class_health"]
    path = REPO_ROOT / "scripts" / "check_class_health.py"
    spec = importlib.util.spec_from_file_location("check_class_health", path)
    if spec is None or spec.loader is None:
        msg = f"cannot load {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_class_health"] = module
    spec.loader.exec_module(module)
    return module


def _repo_relative(path: Path) -> str:
    """A stable repo-relative key, whether the caller passed an absolute or relative path.

    The checker echoes back whatever it was given, so a baseline frozen from `src` and one frozen
    from an absolute path would otherwise key differently and every entry would read as new.

    A path **outside** the repo — which is what a test scanning a `tmp_path` produces — keys by its
    absolute path instead. It can then never match a baseline entry, so it is correctly treated as
    new. An earlier version raised `ValueError` here and silently took the whole check down to
    "nothing to report", which is the failure this ticket is about.
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def measure(*paths: Path) -> dict[str, int]:
    """Every incohesive class under `paths`, as `{file::Class: lcom4}`.

    Keyed by file *and* class name: `Task` and `GitAtom` are unremarkable names that could recur,
    and two classes sharing one entry would let a regression hide behind an improvement.

    Cohesion only. Attribute counts are frozen separately by `measure_attributes` — they are a
    different measure with a different fix, and folding both into one number would make neither
    readable.
    """
    checker = _checker()
    found: dict[str, int] = {}
    for path in checker.iter_python_files(list(paths)):
        for report in checker.analyse_file(path):
            if report.incohesive():
                found[f"{_repo_relative(report.path)}::{report.name}"] = report.lcom4
    return found


def measure_attributes(*paths: Path) -> dict[str, int]:
    """Every oversized class under `paths`, as `{file::Class: attribute_count}`.

    Frozen for the same reason as cohesion: `Task` is one attribute over the limit, and leaving the
    gate red over it would keep the whole check ignored — which is the condition this ticket
    exists to end. A ratchet says "this may not grow" without pretending it is fixed.
    """
    checker = _checker()
    limit = checker.MAX_ATTRIBUTES
    found: dict[str, int] = {}
    for path in checker.iter_python_files(list(paths)):
        for report in checker.analyse_file(path):
            if report.too_many_attributes(limit):
                found[f"{_repo_relative(report.path)}::{report.name}"] = len(report.attributes)
    return found


def _load(section: str) -> dict[str, int] | None:
    if not BASELINE_PATH.is_file():
        return None
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data.get(section, {}).items()}


def load_baseline() -> dict[str, int] | None:
    """The frozen cohesion scores, or None when the baseline has never been written."""
    return _load("classes")


def load_attribute_baseline() -> dict[str, int] | None:
    """The frozen attribute counts, or None when the baseline has never been written."""
    return _load("attributes")


def write_baseline(scores: dict[str, int], attributes: dict[str, int] | None = None) -> None:
    """Freeze the current scores. The diff is meant to be reviewed."""
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "classes": dict(sorted(scores.items())),
                "attributes": dict(sorted((attributes or {}).items())),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def regressions(
    current: dict[str, int], baseline: dict[str, int]
) -> list[tuple[str, int | None, int]]:
    """Classes that are newly incohesive, or less cohesive than they were.

    `None` in the middle position means "was not in the baseline at all".
    """
    worse: list[tuple[str, int | None, int]] = []
    for name, score in sorted(current.items()):
        was = baseline.get(name)
        if was is None or score > was:
            worse.append((name, was, score))
    return worse


def improvements(current: dict[str, int], baseline: dict[str, int]) -> list[tuple[str, int, int]]:
    """Classes whose LCOM4 fell, including to zero — i.e. off the report entirely."""
    better: list[tuple[str, int, int]] = []
    for name, was in sorted(baseline.items()):
        now = current.get(name, 0)
        if now < was:
            better.append((name, was, now))
    return better
