# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading what `cargo test` prints on stable Rust.

Cargo offers no stable machine-readable test output: the JSON libtest format is nightly-only, behind
`-Z unstable-options`. So this parses the human-readable stream, which is stable, deterministic, and
already on stdout — and needs no external converter.

Two shapes matter and both come from real runs. Cargo reports each suite separately, so a crate with
doc-tests prints **two** `test result:` lines and the counts must be summed. And a run that never
started prints no summary at all, which must stay distinguishable from a suite that has no tests —
reporting the first as `0 passed, 0 failed` is the vacuous success the QA gate exists to prevent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from specweaver.commons.qa import TestFailure

#: `test result: ok. 1 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out; finished in 0.00s`
_SUMMARY = re.compile(
    r"^test result: \w+\. (?P<passed>\d+) passed; (?P<failed>\d+) failed; (?P<ignored>\d+) ignored",
    re.MULTILINE,
)

#: `---- t::broken stdout ----` followed by the panic, up to the next such block or the summary.
_FAILURE_BLOCK = re.compile(
    r"^---- (?P<name>\S+) stdout ----$(?P<body>.*?)(?=^---- |^test result:|\Z)",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class CargoTestOutcome:
    """What one `cargo test` invocation reported."""

    passed: int
    failed: int
    skipped: int
    failures: list[TestFailure] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped


def parse_cargo_test(stdout: str) -> CargoTestOutcome | None:
    """Counts and failures from cargo's test output, or None if cargo never reported a suite."""
    summaries = list(_SUMMARY.finditer(stdout))
    if not summaries:
        return None

    passed = sum(int(m.group("passed")) for m in summaries)
    failed = sum(int(m.group("failed")) for m in summaries)
    skipped = sum(int(m.group("ignored")) for m in summaries)
    failures = [
        TestFailure(nodeid=m.group("name"), message=m.group("body").strip())
        for m in _FAILURE_BLOCK.finditer(stdout)
    ]
    return CargoTestOutcome(passed=passed, failed=failed, skipped=skipped, failures=failures)
