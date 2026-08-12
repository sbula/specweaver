# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The cohesion ratchet: known incohesive classes may improve, never worsen (`TECH-035`).

`check_class_health` failed on a clean tree for the whole session — 23 classes when filed, 20 after
`TECH-034` — and **nobody saw it**, because its commit-gate scope is `changed`: it is skipped
entirely whenever a commit touches none of them. It reported `nothing in scope` while 20 classes
were failing.

That makes it simultaneously ignored *and* blocking: the moment a commit does touch one, the whole
gate goes red on debt that commit did not create. `TECH-034` hit exactly that.

Freezing the known set fixes both halves. A **new** incohesive class blocks the commit that
introduces it; an existing one getting **worse** blocks too; and everything else stops being
collateral. Same mechanism as `check_suppressions`, R6, R7 and `check_complexity` — the last of
which caught three real regressions within an hour of shipping, including one of mine.

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


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_a_newly_incohesive_class_is_a_regression() -> None:
    """The point: a class that was fine and now is not blocks the commit that did it."""
    module = _load("_class_health_baseline")

    worse = module.regressions({"a.py::A": 3, "b.py::B": 2}, {"a.py::A": 3})

    assert worse == [("b.py::B", None, 2)]


def test_an_existing_class_getting_worse_is_a_regression() -> None:
    """Freezing the *set* alone would let every known offender drift upward without limit."""
    module = _load("_class_health_baseline")

    assert module.regressions({"a.py::A": 5}, {"a.py::A": 3}) == [("a.py::A", 3, 5)]


def test_an_improvement_is_reported_but_never_a_regression() -> None:
    """A fall must be visible, or the baseline silently drifts above reality.

    Reported rather than auto-applied: rewriting the baseline as a side effect of a passing run
    means nobody reviews the diff, which is what makes `--update-baseline` explicit.
    """
    module = _load("_class_health_baseline")

    assert module.regressions({"a.py::A": 2}, {"a.py::A": 5}) == []
    assert module.improvements({"a.py::A": 2}, {"a.py::A": 5}) == [("a.py::A", 5, 2)]


def test_a_class_becoming_cohesive_counts_as_an_improvement() -> None:
    """Dropping to LCOM4<=1 removes it from the report entirely, which must read as progress."""
    module = _load("_class_health_baseline")

    assert module.improvements({}, {"a.py::A": 4}) == [("a.py::A", 4, 0)]


def test_the_live_baseline_has_no_regressions() -> None:
    """Anchored to the tree, so the ratchet cannot pass while the artifact has drifted.

    Only regressions: improvements are expected between a fix landing and the baseline being
    re-frozen, and failing on those would block the very commits this ticket wants.
    """
    module = _load("_class_health_baseline")

    baseline = module.load_baseline()
    assert baseline is not None, "run `python scripts/check_class_health.py --update-baseline`"

    worse = module.regressions(module.measure(REPO_ROOT / "src"), baseline)

    assert worse == [], "cohesion regressions:\n  " + "\n  ".join(
        f"{name}: {was} -> {now}" for name, was, now in worse
    )


def test_the_census_finds_the_known_offenders() -> None:
    """Guards the measurement against collapsing to nothing and reading as success.

    If `measure` returned `{}` — a moved script, a changed API — every assertion above would still
    hold while proving nothing. That is the failure this ticket is about, so it gets its own test.
    """
    module = _load("_class_health_baseline")

    current = module.measure(REPO_ROOT / "src")

    assert len(current) >= 15, f"expected the known offenders, found {len(current)}"
    assert any("BaseTreeSitterParser" in name for name in current), (
        "the most incohesive class in the repo is missing from the census"
    )
