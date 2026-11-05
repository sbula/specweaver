# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check`'s summary line counts skipped rules, and a run where no rule judged exits 1.

Proves: TECH-082 FR-13

| Bucket | Case |
|---|---|
| Happy | each line adds `(N skipped)` when N > 0 |
| Boundary | with no SKIP row the lines are unchanged; no result prints `NOTHING CHECKED: 0 skipped` |
| Degradation | every row SKIP prints `NOTHING CHECKED: N skipped` and exits 1, strict or not |
| Hostile | — (results are typed values) |
"""

from __future__ import annotations

import re

import pytest
import typer

from specweaver.assurance.validation.interfaces import cli
from specweaver.assurance.validation.models import RuleResult, Status

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _results(*statuses: Status) -> list[RuleResult]:
    return [RuleResult(rule_id=f"R{i}", rule_name="r", status=s) for i, s in enumerate(statuses)]


def _summary(
    capsys: pytest.CaptureFixture[str], statuses: tuple[Status, ...], *, strict: bool = False
) -> tuple[str, int]:
    code = 0
    try:
        cli._print_summary(_results(*statuses), strict=strict)
    except typer.Exit as exc:
        code = exc.exit_code
    return _ANSI.sub("", capsys.readouterr().out).strip(), code


@pytest.mark.parametrize(
    ("statuses", "strict", "line", "code"),
    [
        (
            (Status.FAIL, Status.WARN, Status.SKIP, Status.SKIP, Status.SKIP),
            False,
            "FAILED: 1 rule(s) failed, 1 warning(s) (3 skipped)",
            1,
        ),
        ((Status.WARN, Status.SKIP), False, "PASSED with warnings: 1 warning(s) (1 skipped)", 0),
        ((Status.WARN, Status.SKIP), True, "PASSED with warnings: 1 warning(s) (1 skipped)", 1),
        ((Status.PASS, Status.SKIP, Status.SKIP), False, "ALL PASSED (2 skipped)", 0),
        ((Status.PASS, Status.FAIL), False, "FAILED: 1 rule(s) failed, 0 warning(s)", 1),
        ((Status.PASS,), False, "ALL PASSED", 0),
        ((Status.SKIP, Status.SKIP), False, "NOTHING CHECKED: 2 skipped", 1),
        ((Status.SKIP,), True, "NOTHING CHECKED: 1 skipped", 1),
        ((), False, "NOTHING CHECKED: 0 skipped", 1),
    ],
)
def test_the_summary_line_and_exit(
    capsys: pytest.CaptureFixture[str],
    statuses: tuple[Status, ...],
    strict: bool,
    line: str,
    code: int,
) -> None:
    assert _summary(capsys, statuses, strict=strict) == (line, code)
