# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""On CI a test that skips for anything but the platform fails the run.

Proves: TECH-094 FR-5

A skip because a tool is missing reads as a pass in the summary. On CI the tools are installed on
purpose, so such a skip means the run did not test what it claims. Locally a skip stays a skip.

| Bucket | Case |
|---|---|
| Happy | on CI a skip for a missing tool fails the session, naming the test and the reason |
| Boundary | a Windows-only skip passes on CI; an expected failure (`xfail`) is not a skip |
| Degradation | without `CI` every skip passes; a skip reported by a worker is judged once, by the controller |
| Hostile | a module-level skip at collection is judged too; an empty `CI` value is not CI |
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests import ci_skips


def _skip(reason: str, nodeid: str = "tests/a_test.py::test_x") -> pytest.TestReport:
    return pytest.TestReport(
        nodeid,
        ("tests/a_test.py", 1, "test_x"),
        {},
        "skipped",
        ("f.py", 3, f"Skipped: {reason}"),
        "setup",
    )


@pytest.fixture()
def fresh(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(ci_skips, "_SKIPS", seen)
    return seen


def _finish(monkeypatch: pytest.MonkeyPatch, ci: str | None, worker: bool = False) -> int:
    if ci is None:
        monkeypatch.delenv("CI", raising=False)
    else:
        monkeypatch.setenv("CI", ci)
    config = SimpleNamespace(workerinput={}) if worker else SimpleNamespace()
    session = SimpleNamespace(config=config, exitstatus=pytest.ExitCode.OK)
    ci_skips.pytest_sessionfinish(session, pytest.ExitCode.OK)
    return session.exitstatus


def test_a_tool_skip_fails_the_run_on_ci(
    fresh: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ci_skips.pytest_runtest_logreport(_skip("ripgrep (rg) not on PATH"))

    assert _finish(monkeypatch, "true") == pytest.ExitCode.TESTS_FAILED
    out = capsys.readouterr().out
    assert "tests/a_test.py::test_x" in out
    assert "ripgrep (rg) not on PATH" in out


def test_a_windows_only_skip_passes_on_ci(
    fresh: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    ci_skips.pytest_runtest_logreport(_skip("Windows-only test"))
    ci_skips.pytest_runtest_logreport(_skip("SIGBREAK only exists on Windows"))

    assert _finish(monkeypatch, "true") == pytest.ExitCode.OK


def test_an_expected_failure_is_not_a_skip(
    fresh: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _skip("blocked on X")
    report.wasxfail = "blocked on X"
    ci_skips.pytest_runtest_logreport(report)

    assert fresh == []
    assert _finish(monkeypatch, "true") == pytest.ExitCode.OK


@pytest.mark.parametrize("ci", [None, ""])
def test_without_ci_a_skip_stays_a_skip(
    fresh: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch, ci: str | None
) -> None:
    ci_skips.pytest_runtest_logreport(_skip("rg not on PATH"))

    assert _finish(monkeypatch, ci) == pytest.ExitCode.OK


def test_a_worker_leaves_the_judgement_to_the_controller(
    fresh: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    ci_skips.pytest_runtest_logreport(_skip("rg not on PATH"))

    assert _finish(monkeypatch, "true", worker=True) == pytest.ExitCode.OK


def test_a_skip_at_collection_is_judged(
    fresh: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    report = pytest.CollectReport(
        "tests/b_test.py", "skipped", ("b.py", 1, "Skipped: kotlinc not installed"), []
    )
    ci_skips.pytest_collectreport(report)

    assert fresh == [("tests/b_test.py", "kotlinc not installed")]
    assert _finish(monkeypatch, "true") == pytest.ExitCode.TESTS_FAILED
