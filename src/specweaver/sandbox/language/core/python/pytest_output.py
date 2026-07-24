# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pytest output parsing for the Python QA runner.

Extracted from ``runner.py`` (INT-US-24 SF-03) alongside the inherited
defect #7 fix: pytest orders mixed summaries failed-FIRST
("2 failed, 1 passed in 0.03s"); the old passed-first regex silently parsed
that as passed=1/failed=0 — failing runs reported SUCCESS. Parsing is now
order-independent: find the summary line via its duration token, then extract
every "<count> <bucket>" pair on it.
"""

from __future__ import annotations

import re
from typing import TypedDict

from specweaver.sandbox.qa_runner.core.interface import TestFailure

_SUMMARY_DURATION_RE = re.compile(r"\bin\s+([\d.]+)s\b")
_COUNT_TOKEN_RE = re.compile(r"(\d+)\s+(passed|failed|errors?|skipped)\b")

# Matches "FAILED tests/test_foo.py::test_bar" with an OPTIONAL " - <message>"
# suffix (-q short summaries may omit it).
_FAILURE_RE = re.compile(r"FAILED\s+(\S+)(?:\s*-\s*(.*))?")

# Matches "TOTAL  100  15  85%"
_COVERAGE_RE = re.compile(r"TOTAL\s+\d+\s+\d+\s+(\d+)%")


class _ParsedOutput(TypedDict):
    passed: int
    failed: int
    errors: int
    skipped: int
    total: int
    duration: float
    failures: list[TestFailure]
    coverage_pct: float | None


def _parse_pytest_output(stdout: str) -> _ParsedOutput:
    """Parse pytest --tb=short -q output into structured data."""
    result: _ParsedOutput = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "total": 0,
        "duration": 0.0,
        "failures": [],
        "coverage_pct": None,
    }

    # Parse the summary line (the LAST line carrying a duration + count tokens),
    # order-independently — pytest emits buckets in varying orders.
    for line in stdout.splitlines():
        duration_match = _SUMMARY_DURATION_RE.search(line)
        if not duration_match:
            continue
        tokens = _COUNT_TOKEN_RE.findall(line)
        if not tokens:
            continue
        counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        for count, bucket in tokens:
            key = "errors" if bucket.startswith("error") else bucket
            counts[key] = int(count)
        result["passed"] = counts["passed"]
        result["failed"] = counts["failed"]
        result["errors"] = counts["errors"]
        result["skipped"] = counts["skipped"]
        result["duration"] = float(duration_match.group(1))

    result["total"] = result["passed"] + result["failed"] + result["errors"] + result["skipped"]

    # Parse failure lines (the " - <message>" suffix is optional under -q)
    for match in _FAILURE_RE.finditer(stdout):
        result["failures"].append(
            TestFailure(nodeid=match.group(1), message=(match.group(2) or "").strip()),
        )

    # Parse coverage
    cov_match = _COVERAGE_RE.search(stdout)
    if cov_match:
        result["coverage_pct"] = float(cov_match.group(1))

    return result
