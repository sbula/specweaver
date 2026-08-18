# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading JVM test reports, including the part that says what went wrong.

Both JVM runners harvested counts and returned `failures=[]`. The detail was already on disk — a
surefire report carries the assertion message, the exception type and the stack — and nothing read
it. An agent handed `failed=1` and nothing else has to re-run the suite by hand to learn anything,
which is the one thing a sandboxed QA run exists to avoid.

Shared rather than duplicated per language: the two JVM runners consume the same format, and the
counting drifted between them once already — Java counted `errors` toward failures and Kotlin counted
them too but ignored `skipped` when deriving `passed`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.commons.qa import TestFailure

if TYPE_CHECKING:
    from collections.abc import Iterable

    import junitparser as _junitparser

logger = logging.getLogger(__name__)

#: A stack trace is worth reading; a whole build log is not.
_MAX_STACK = 4000


@dataclass(frozen=True)
class JUnitHarvest:
    """What one report directory said, counts and detail together."""

    passed: int
    failed: int
    skipped: int
    failures: list[TestFailure] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped


#: The sandbox writes a JVM build's output here, because the workspace it ran in was an overlay
#: that is discarded. Same convention `QARunnerAtom` builds its container mounts from.
_SANDBOX_SCRATCH = (".specweaver", ".sandbox", "scratch")


def report_search_paths(cwd: Path, relative: str) -> list[Path]:
    """Both places a build's reports can be: inside the project, or mounted out to scratch.

    The runner is the same object either way and nothing tells it whether the build ran on the host
    or in a container, so it looks in both. A directory that does not exist harvests as nothing.
    """
    return [cwd.joinpath(relative), cwd.joinpath(*_SANDBOX_SCRATCH, relative)]


def harvest_junit(search_path: Path | Iterable[Path]) -> JUnitHarvest:
    """Every JUnit XML report under `search_path`, summed, with failure detail preserved.

    A report that cannot be parsed is skipped rather than failing the run: a partially-written file
    from a killed build is not a test failure, and reporting it as one would blame the project for
    the build being interrupted.
    """
    import junitparser

    roots = [search_path] if isinstance(search_path, Path) else list(search_path)
    xml_files = sorted(f for root in roots if root.exists() for f in root.rglob("*.xml"))
    if not xml_files:
        return JUnitHarvest(0, 0, 0)

    passed = failed = skipped = 0
    failures: list[TestFailure] = []
    for xml_file in xml_files:
        try:
            xml = junitparser.JUnitXml.fromfile(str(xml_file))
        except Exception:
            logger.debug("harvest_junit: unreadable report skipped: %s", xml_file)
            continue
        passed += xml.tests - xml.failures - xml.skipped - xml.errors
        failed += xml.failures + xml.errors
        skipped += xml.skipped
        failures.extend(_failures_in(xml))
    return JUnitHarvest(passed=passed, failed=failed, skipped=skipped, failures=failures)


def _failures_in(xml: _junitparser.JUnitXml) -> list[TestFailure]:
    """One `TestFailure` per failed or errored case, named so a reader can find it."""
    import junitparser

    found: list[TestFailure] = []
    for suite in xml:
        for case in suite:
            for outcome in case.result:
                if not isinstance(outcome, junitparser.Failure | junitparser.Error):
                    continue
                stack = (outcome.text or "").strip()
                found.append(
                    TestFailure(
                        nodeid=f"{case.classname}.{case.name}",
                        message=(outcome.message or stack.splitlines()[0] if stack else "").strip(),
                        stacktrace=stack[:_MAX_STACK],
                    )
                )
    return found
