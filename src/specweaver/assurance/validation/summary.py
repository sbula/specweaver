# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One summary of a check's results: the counts and the verdict `sw check` and `/check` report.

A run where no rule judged (every result SKIP, or none) is never a pass.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import Status

if TYPE_CHECKING:
    from collections.abc import Sequence

    from specweaver.assurance.validation.models import RuleResult


class Verdict(enum.Enum):
    """What a check's results add up to."""

    FAILED = "failed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    ALL_PASSED = "all_passed"
    NOTHING_CHECKED = "nothing_checked"

    @property
    def fails(self) -> bool:
        """True when the check must not be read as passed."""
        return self in (Verdict.FAILED, Verdict.NOTHING_CHECKED)


@dataclass(frozen=True)
class Summary:
    """The counts per status and the verdict."""

    passed: int
    failed: int
    warned: int
    skipped: int
    verdict: Verdict

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.warned + self.skipped


def summarize(results: Sequence[RuleResult], *, strict: bool = False) -> Summary:
    """Count `results` and judge them; `strict` makes a warning a failure."""
    count = {status: sum(1 for r in results if r.status == status) for status in Status}
    passed, failed, warned = count[Status.PASS], count[Status.FAIL], count[Status.WARN]
    if passed + failed + warned == 0:
        verdict = Verdict.NOTHING_CHECKED
    elif failed or (strict and warned):
        verdict = Verdict.FAILED
    elif warned:
        verdict = Verdict.PASSED_WITH_WARNINGS
    else:
        verdict = Verdict.ALL_PASSED
    return Summary(passed, failed, warned, count[Status.SKIP], verdict)
