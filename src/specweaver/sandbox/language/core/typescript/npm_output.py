# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading what `npm test` and ESLint print: Jest's or Vitest's summary line, ESLint's JSON."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_JEST = re.compile(r"^\s*Tests:\s+(?P<body>.*\btotal)\s*$", re.MULTILINE)
_VITEST = re.compile(r"^\s*Tests\s+(?P<body>.*\(\d+\))\s*$", re.MULTILINE)
_COUNT = re.compile(r"(\d+)\s+(passed|failed|skipped|todo)")


@dataclass(frozen=True)
class TestCounts:
    __test__ = False

    passed: int
    failed: int
    skipped: int
    total: int


def summary_counts(stdout: str) -> TestCounts | None:
    """The counts in Jest's `Tests: … total` or Vitest's `Tests … (n)` line; None when neither."""
    text = _ANSI.sub("", stdout)
    found = _JEST.search(text) or _VITEST.search(text)
    if found is None:
        return None
    counts = {kind: int(number) for number, kind in _COUNT.findall(found.group("body"))}
    passed, failed = counts.get("passed", 0), counts.get("failed", 0)
    skipped = counts.get("skipped", 0) + counts.get("todo", 0)
    return TestCounts(passed, failed, skipped, passed + failed + skipped)


@dataclass(frozen=True)
class EslintFinding:
    file: str
    line: int
    code: str
    message: str


def eslint_findings(stdout: str) -> tuple[list[EslintFinding], int] | None:
    """ESLint's `--format json` read into findings and the fixable count; None when it is not that."""
    try:
        results = json.loads(stdout)
    except ValueError:  # expected: ESLint printed no JSON — the caller reports it did not run
        return None
    if not isinstance(results, list):
        return None
    findings = [
        EslintFinding(
            file=str(result.get("filePath", "")),
            line=int(message.get("line", 0)),
            code=str(message.get("ruleId") or "eslint"),
            message=str(message.get("message", "")),
        )
        for result in results
        for message in result.get("messages", [])
        if message.get("severity") == 2
    ]
    fixable = sum(int(result.get("fixableErrorCount", 0)) for result in results)
    return findings, fixable
