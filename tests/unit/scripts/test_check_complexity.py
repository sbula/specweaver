# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The complexity ratchet: 97 known violations may fall, never rise (`TECH-023`).

`complexipy` has failed the commit gate continuously since 2026-08-02 — 97 functions across ~68
files, spanning nearly every domain. A gate that is always red is a gate nobody reads, and nothing
stopped a 98th appearing.

Freezing the known set converts it into an enforcing gate: a **new** violation blocks the commit
that introduces it, and so does an **increase** on a function already in the baseline. This is the
mechanism `TECH-023` asks for and the pattern `check_suppressions`, R6 and R7 already use here.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]

SAMPLE = """\
──────────────────────────────── 🐙 complexipy ─────────────────────────────────
src/specweaver/assurance/graph/hasher.py
    DependencyHasher::_hash_directory 36  ❌ FAILED

src/specweaver/assurance/graph/topology.py
    TopologyGraph::_calculate_stale_seeds 17  ❌ FAILED
    standards_scan 24  ❌ FAILED
────────────────────────── 🎉 Analysis completed! 🎉 ───────────────────────────
"""


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_it_reads_complexipy_s_report_into_function_scores() -> None:
    """Each violation is keyed by file AND function — the same name recurs across modules."""
    module = _load("check_complexity")

    found = module.parse(SAMPLE)

    assert found == {
        "src/specweaver/assurance/graph/hasher.py::DependencyHasher::_hash_directory": 36,
        "src/specweaver/assurance/graph/topology.py::TopologyGraph::_calculate_stale_seeds": 17,
        "src/specweaver/assurance/graph/topology.py::standards_scan": 24,
    }


def test_banner_lines_are_not_mistaken_for_files() -> None:
    """The report is framed by decorative rules that sit at column zero, like a path does."""
    module = _load("check_complexity")

    assert module.parse("🎉 Analysis completed! 🎉\n") == {}
    assert module.parse("") == {}


def test_a_new_violation_is_a_regression() -> None:
    """The point of the ratchet: a function that was never over the line now is."""
    module = _load("check_complexity")

    worse = module.regressions({"a.py::f": 20, "b.py::g": 17}, {"a.py::f": 20})

    assert worse == [("b.py::g", None, 17)]


def test_a_function_getting_worse_is_a_regression() -> None:
    """Freezing the *set* alone would let every known offender grow without limit."""
    module = _load("check_complexity")

    worse = module.regressions({"a.py::f": 25}, {"a.py::f": 20})

    assert worse == [("a.py::f", 20, 25)]


def test_an_improvement_is_not_a_regression_but_is_reported() -> None:
    """A fall must be visible, otherwise the baseline silently drifts above reality.

    Reported rather than auto-applied: rewriting the baseline as a side effect of a passing run
    would mean nobody ever reviews the diff, which is what makes `--update-baseline` explicit.
    """
    module = _load("check_complexity")

    assert module.regressions({"a.py::f": 8}, {"a.py::f": 20}) == []
    assert module.improvements({"a.py::f": 8}, {"a.py::f": 20}) == [("a.py::f", 20, 8)]


def test_a_fixed_function_leaving_the_report_counts_as_an_improvement() -> None:
    """Dropping below the threshold removes it from complexipy's output entirely."""
    module = _load("check_complexity")

    assert module.improvements({}, {"a.py::f": 20}) == [("a.py::f", 20, 0)]


def test_the_live_baseline_matches_the_tree() -> None:
    """Anchored to reality, so the ratchet cannot pass while the artifact has drifted.

    Only checks for *regressions*: improvements are expected between a fix landing and the
    baseline being re-frozen, and failing on those would block the very commits this ticket wants.
    """
    module = _load("check_complexity")

    baseline = module.load_baseline()
    assert baseline is not None, "run `python scripts/check_complexity.py --update-baseline`"

    worse = module.regressions(module.measure(REPO_ROOT / "src"), baseline)

    assert worse == [], "complexity regressions:\n  " + "\n  ".join(
        f"{name}: {was} -> {now}" for name, was, now in worse
    )
