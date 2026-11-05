# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One summary of a check's results, for `sw check` and `POST /check` alike.

Proves: TECH-082 FR-13, FR-14

| Bucket | Case |
|---|---|
| Happy | a FAIL fails; a WARN passes with warnings; PASS rows pass; SKIP rows are counted |
| Boundary | no result, or only SKIP rows, is NOTHING_CHECKED; strict turns a WARN into a failure |
| Degradation | NOTHING_CHECKED wins over strict |
| Hostile | — (results are typed `RuleResult` values; nothing reaches here from outside) |
"""

from __future__ import annotations

import pytest

from specweaver.assurance.validation.models import RuleResult, Status
from specweaver.assurance.validation.summary import Verdict, summarize


def _results(*statuses: Status) -> list[RuleResult]:
    return [RuleResult(rule_id=f"R{i}", rule_name="r", status=s) for i, s in enumerate(statuses)]


def test_each_status_is_counted() -> None:
    summary = summarize(
        _results(Status.PASS, Status.PASS, Status.FAIL, Status.WARN, Status.SKIP, Status.SKIP)
    )

    assert (summary.passed, summary.failed, summary.warned, summary.skipped, summary.total) == (
        2,
        1,
        1,
        2,
        6,
    )


@pytest.mark.parametrize(
    ("statuses", "strict", "verdict"),
    [
        ((Status.PASS, Status.FAIL, Status.SKIP), False, Verdict.FAILED),
        ((Status.PASS, Status.WARN, Status.SKIP), False, Verdict.PASSED_WITH_WARNINGS),
        ((Status.PASS, Status.WARN), True, Verdict.FAILED),
        ((Status.PASS, Status.SKIP), False, Verdict.ALL_PASSED),
        ((Status.PASS,), True, Verdict.ALL_PASSED),
        ((Status.SKIP, Status.SKIP), False, Verdict.NOTHING_CHECKED),
        ((), False, Verdict.NOTHING_CHECKED),
    ],
)
def test_the_verdict(statuses: tuple[Status, ...], strict: bool, verdict: Verdict) -> None:
    assert summarize(_results(*statuses), strict=strict).verdict is verdict


def test_nothing_checked_wins_over_strict() -> None:
    assert summarize(_results(Status.SKIP), strict=True).verdict is Verdict.NOTHING_CHECKED


@pytest.mark.parametrize(
    ("verdict", "fails"),
    [
        (Verdict.FAILED, True),
        (Verdict.NOTHING_CHECKED, True),
        (Verdict.PASSED_WITH_WARNINGS, False),
        (Verdict.ALL_PASSED, False),
    ],
)
def test_which_verdicts_fail(verdict: Verdict, fails: bool) -> None:
    assert verdict.fails is fails
