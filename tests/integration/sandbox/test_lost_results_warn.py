# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A tool report the sandbox cannot read is a warning, and a runner that crashed says why.

Proves: D-FLOW-04 FR-8
Proves: TECH-087 FR-10

Real report files on disk; the runners' executor is a double that raises.

| Bucket | Case |
|---|---|
| Happy | a good JUnit report beside an unreadable one is still counted |
| Boundary | not applicable — the same fallback as before; only its trace is new |
| Degradation | unreadable JUnit XML, SARIF, ruff and import reports; cargo that cannot start |
| Hostile | a folder named like a JUnit report |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _warned(caplog: pytest.LogCaptureFixture, *words: str) -> bool:
    return any(
        record.levelno == logging.WARNING and all(w in record.getMessage() for w in words)
        for record in caplog.records
    )


class _Broken:
    """An executor whose command cannot start."""

    def execute(self, *_a: Any, **_k: Any) -> Any:
        raise OSError("cargo: not found")


def test_cargo_test_that_cannot_start_says_why(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.language.core.rust.runner import RustRunner

    result = RustRunner(tmp_path, executor=_Broken()).run_tests("src")

    assert (result.passed, result.errors) == (0, 1)
    assert any("cargo: not found" in failure.message for failure in result.failures)
    assert _warned(caplog, "cargo test")


def test_cargo_clippy_that_cannot_start_says_why(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.language.core.rust.runner import RustRunner

    result = RustRunner(tmp_path, executor=_Broken()).run_linter("src")

    assert result.error_count >= 1
    assert any("cargo: not found" in error.message for error in result.errors)
    assert _warned(caplog, "cargo clippy")


def test_cargo_run_that_cannot_start_says_why(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.language.core.rust.runner import RustRunner

    result = RustRunner(tmp_path, executor=_Broken()).run_debugger("src", "main")

    assert result.exit_code == 1
    assert any("cargo: not found" in event.output for event in result.events)
    assert _warned(caplog, "cargo run")


_GOOD_REPORT = (
    '<testsuite name="s" tests="2" failures="1" errors="0" skipped="0">'
    '<testcase name="ok"/><testcase name="bad"><failure message="boom"/></testcase>'
    "</testsuite>"
)


def test_an_unreadable_junit_report_is_not_counted_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.language.core.junit_reports import harvest_junit

    (tmp_path / "TEST-x.xml").write_text("<testsuite", encoding="utf-8")

    harvest = harvest_junit(tmp_path)

    assert (harvest.passed, harvest.failed, harvest.skipped) == (0, 0, 0)
    assert _warned(caplog, "TEST-x.xml", "not counted")


def test_a_good_report_beside_an_unreadable_one_is_still_counted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.language.core.junit_reports import harvest_junit

    (tmp_path / "TEST-good.xml").write_text(_GOOD_REPORT, encoding="utf-8")
    (tmp_path / "TEST-x.xml").write_text("<testsuite", encoding="utf-8")

    harvest = harvest_junit(tmp_path)

    assert (harvest.passed, harvest.failed) == (1, 1)
    assert _warned(caplog, "TEST-x.xml", "not counted")
    assert not _warned(caplog, "TEST-good.xml")


def test_a_folder_named_like_a_report_warns_and_is_not_counted(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.language.core.junit_reports import harvest_junit

    (tmp_path / "TEST-dir.xml").mkdir()

    harvest = harvest_junit(tmp_path)

    assert (harvest.passed, harvest.failed, harvest.skipped) == (0, 0, 0)
    assert _warned(caplog, "TEST-dir.xml", "not counted")


def test_a_malformed_sarif_report_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    from specweaver.sandbox.language.core.sarif import read_sarif_report

    report = tmp_path / "report.sarif"
    report.write_text("{not json", encoding="utf-8")

    assert read_sarif_report(report) is None
    assert _warned(caplog, "report.sarif", "cannot be read")


def test_a_ruff_report_that_is_not_json_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.sandbox.language.core.python.runner import PythonQARunner

    assert PythonQARunner(tmp_path)._parse_ruff_json("not json") is None
    assert _warned(caplog, "ruff", "not valid JSON")


def test_an_import_report_that_is_not_json_warns(caplog: pytest.LogCaptureFixture) -> None:
    from specweaver.sandbox.language.core.typescript.runner import _restricted_import_violations

    assert _restricted_import_violations("not json") == []
    assert _warned(caplog, "import report", "lost")
