# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Getting a JVM test failure out of the report and into the caller's hands.

Both JVM runners harvested **counts only** and hard-coded `failures=[]`. Measured 2026-08-18 against
real Maven: a failing Java test yielded `TestRunResult(passed=0, failed=1, failures=[])` while the
surefire XML beside it held `java.lang.AssertionError: expected:<42> but was:<41>` and the full stack.

An agent handed `failed=1` and nothing else cannot act. It cannot name the test, the assertion, the
expected value or the line — so the next step is to re-run the suite by hand, which is the one thing
the sandbox exists to avoid. The detail was already on disk; nothing read it.

The sample below is a real surefire report, trimmed of its 40-line `<properties>` block.

Proves: TECH-031 FR-15
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.language.core.junit_reports import harvest_junit

if TYPE_CHECKING:
    from pathlib import Path

_REPORT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="ProbeTest" time="0.003" tests="3" errors="0" skipped="1" failures="1">
  <testcase name="broken" classname="ProbeTest" time="0.003">
    <failure message="expected:&lt;42&gt; but was:&lt;41&gt;" type="java.lang.AssertionError"><![CDATA[java.lang.AssertionError: expected:<42> but was:<41>
\tat org.junit.Assert.fail(Assert.java:89)
\tat org.junit.Assert.assertEquals(Assert.java:633)
\tat ProbeTest.broken(ProbeTest.java:6)]]></failure>
  </testcase>
  <testcase name="works" classname="ProbeTest" time="0"/>
  <testcase name="skipped" classname="ProbeTest" time="0">
    <skipped/>
  </testcase>
</testsuite>
"""


class TestHarvestJunit:
    """Counts, and the detail that makes a count actionable."""

    def test_the_counts_are_unchanged(self, tmp_path: Path) -> None:
        (tmp_path / "TEST-ProbeTest.xml").write_text(_REPORT, encoding="utf-8")

        harvest = harvest_junit(tmp_path)

        assert (harvest.passed, harvest.failed, harvest.skipped) == (1, 1, 1)

    def test_the_failing_test_is_named(self, tmp_path: Path) -> None:
        (tmp_path / "TEST-ProbeTest.xml").write_text(_REPORT, encoding="utf-8")

        harvest = harvest_junit(tmp_path)

        assert len(harvest.failures) == 1
        assert harvest.failures[0].nodeid == "ProbeTest.broken", harvest.failures[0].nodeid

    def test_the_assertion_and_the_stack_both_survive(self, tmp_path: Path) -> None:
        """The message says what went wrong; the stack says where. An agent needs both."""
        (tmp_path / "TEST-ProbeTest.xml").write_text(_REPORT, encoding="utf-8")

        failure = harvest_junit(tmp_path).failures[0]

        assert "expected:<42> but was:<41>" in failure.message, failure.message
        assert "ProbeTest.broken(ProbeTest.java:6)" in failure.stacktrace, failure.stacktrace

    def test_a_passing_report_yields_no_failures(self, tmp_path: Path) -> None:
        """The control: a green suite must not manufacture detail."""
        (tmp_path / "TEST-Ok.xml").write_text(
            '<testsuite name="Ok" tests="1" errors="0" skipped="0" failures="0">'
            '<testcase name="works" classname="Ok" time="0"/></testsuite>',
            encoding="utf-8",
        )

        harvest = harvest_junit(tmp_path)

        assert (harvest.passed, harvest.failed) == (1, 0)
        assert harvest.failures == []

    def test_an_error_counts_as_a_failure_and_keeps_its_detail(self, tmp_path: Path) -> None:
        """An `<error>` is a test that blew up rather than asserted. Both are red, both need detail."""
        (tmp_path / "TEST-Err.xml").write_text(
            '<testsuite name="Err" tests="1" errors="1" skipped="0" failures="0">'
            '<testcase name="explodes" classname="Err" time="0">'
            '<error message="boom" type="java.lang.IllegalStateException">'
            "<![CDATA[java.lang.IllegalStateException: boom]]></error></testcase></testsuite>",
            encoding="utf-8",
        )

        harvest = harvest_junit(tmp_path)

        assert harvest.failed == 1
        assert harvest.failures[0].nodeid == "Err.explodes"
        assert "boom" in harvest.failures[0].message

    def test_an_unreadable_report_is_skipped_not_fatal(self, tmp_path: Path) -> None:
        """A build killed mid-write leaves a truncated file; that is not a test failure."""
        (tmp_path / "TEST-Broken.xml").write_text("<testsuite", encoding="utf-8")
        (tmp_path / "TEST-Ok.xml").write_text(
            '<testsuite name="Ok" tests="1" errors="0" skipped="0" failures="0">'
            '<testcase name="works" classname="Ok" time="0"/></testsuite>',
            encoding="utf-8",
        )

        harvest = harvest_junit(tmp_path)

        assert harvest.passed == 1
        assert harvest.failed == 0

    def test_a_missing_directory_is_empty_rather_than_an_error(self, tmp_path: Path) -> None:
        harvest = harvest_junit(tmp_path / "never-written")

        assert (harvest.passed, harvest.failed, harvest.skipped) == (0, 0, 0)
        assert harvest.failures == []
