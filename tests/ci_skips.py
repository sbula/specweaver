# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""On CI a test that skips for anything but the platform fails the run.

A skip because a tool is missing reads as a pass. CI installs the tools the suite looks for, so on
CI (`CI` set, as GitHub sets it) such a skip means the run tested less than it claims. Only a skip
whose reason names Windows is allowed there. Locally a skip stays a skip. The hooks are registered
by `tests/conftest.py`; under xdist the controller sees every report and judges once.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

#: (node id, reason) of every skip this session saw.
_SKIPS: list[tuple[str, str]] = []
_ALLOWED = "Windows"


def _reason(report: Any) -> str:
    longrepr = report.longrepr
    text = longrepr[2] if isinstance(longrepr, tuple) else str(longrepr)
    return str(text).removeprefix("Skipped: ")


def _record(report: Any) -> None:
    if report.skipped and not hasattr(report, "wasxfail"):
        _SKIPS.append((report.nodeid, _reason(report)))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    _record(report)


def pytest_collectreport(report: pytest.CollectReport) -> None:
    _record(report)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    if hasattr(session.config, "workerinput") or not os.environ.get("CI"):
        return
    refused = [(nodeid, reason) for nodeid, reason in _SKIPS if _ALLOWED not in reason]
    if refused:
        print("\nOn CI only Windows-only skips are allowed; these tests did not run:")
        for nodeid, reason in refused:
            print(f"  {nodeid}: {reason}")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
