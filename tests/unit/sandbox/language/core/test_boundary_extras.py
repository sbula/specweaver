# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A stricter boundary tool the project configured runs in addition, and says when it did not run.

Proves: TECH-082 FR-20

With no `tach.toml` tach is not configured, so nothing runs and nothing fails `[agreed 2026-11-05]`.
A configured tool that cannot run is reported as not run, never as clean `[agreed 2026-11-05]`.

| Bucket | Case |
|---|---|
| Happy | tach configured and clean; tach's violations are reported with the tool's name |
| Boundary | no config file → not listed; a Go file → tach is not asked |
| Degradation | not installed, timed out, unreadable output → not run, with the reason |
| Hostile | output that is valid JSON but not a list → not run |
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.language.core import boundary_extras
from specweaver.sandbox.language.core.boundary_extras import run_extras

if TYPE_CHECKING:
    from pathlib import Path

UNDECLARED = (
    '[{"Located": {"file_path": "a/b.py", "details": {"Code": {"UndeclaredDependency": '
    '{"dependency": "c.d", "usage_module": "a", "definition_module": "c"}}}}}]'
)


class _Executor:
    def __init__(self, stdout: str = "[]", *, exit_code: int = 0, timed_out: bool = False) -> None:
        self.calls: list[list[str]] = []
        self._result = SimpleNamespace(
            exit_code=exit_code, stdout=stdout, stderr="", timed_out=timed_out
        )

    def execute(self, cmd: list[str], *, timeout_seconds: int | None = None) -> SimpleNamespace:
        self.calls.append(cmd)
        return self._result


@pytest.fixture
def configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "tach.toml").write_text("exact = true\n", encoding="utf-8")
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: f"/bin/{name}")
    return tmp_path


def test_a_clean_tach_run_ran_and_found_nothing(configured: Path) -> None:
    executor = _Executor("[]")

    [run] = run_extras(configured, "python", executor)

    assert (run.tool, run.ran, run.reason, run.violations) == ("tach", True, "", [])
    assert executor.calls == [["python", "-m", "tach", "check", "--output", "json"]]


def test_tachs_violations_carry_the_tools_name(configured: Path) -> None:
    [run] = run_extras(configured, "python", _Executor(UNDECLARED, exit_code=1))

    assert run.ran
    assert [(v.file, v.code) for v in run.violations] == [("a/b.py", "tach:UndeclaredDependency")]
    assert "cannot import 'c.d'" in run.violations[0].message


def test_without_tach_toml_tach_is_not_configured(tmp_path: Path) -> None:
    executor = _Executor()

    assert run_extras(tmp_path, "python", executor) == []
    assert executor.calls == []


def test_a_go_file_does_not_ask_tach(configured: Path) -> None:
    assert run_extras(configured, "go", _Executor()) == []


def test_tach_not_installed_is_not_run(configured: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: None)

    [run] = run_extras(configured, "python", _Executor())

    assert (run.ran, run.violations) == (False, [])
    assert "not installed" in run.reason


@pytest.mark.parametrize(
    ("executor", "says"),
    [
        (_Executor("", timed_out=True), "timed out"),
        (_Executor("not json", exit_code=2), "could not read"),
        (_Executor('{"a": 1}', exit_code=1), "could not read"),
        (_Executor("[1]", exit_code=1), "could not read"),
        (_Executor("", exit_code=1), "did not run"),
    ],
)
def test_a_tach_run_with_no_verdict_is_not_run(
    configured: Path, executor: _Executor, says: str
) -> None:
    [run] = run_extras(configured, "python", executor)

    assert run.ran is False
    assert says in run.reason


def test_container_mode_does_not_ask_the_host_path(
    configured: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In a container the host PATH says nothing: tach is looked for inside the image."""
    from unittest.mock import MagicMock

    from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

    monkeypatch.setattr(boundary_extras.shutil, "which", lambda name: None)
    executor = MagicMock(spec=ContainerSubprocessExecutor)
    executor.execute.return_value = SimpleNamespace(
        exit_code=0, stdout="[]", stderr="", timed_out=False
    )

    [run] = run_extras(configured, "python", executor)

    assert run.ran
    executor.execute.assert_called_once()


def test_tach_missing_inside_the_container_is_not_run(configured: Path) -> None:
    from unittest.mock import MagicMock

    from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

    executor = MagicMock(spec=ContainerSubprocessExecutor)
    executor.execute.return_value = SimpleNamespace(
        exit_code=1, stdout="", stderr="/usr/bin/python3: No module named tach", timed_out=False
    )

    [run] = run_extras(configured, "python", executor)

    assert run.ran is False
    assert "tach" in run.reason


def test_an_unavailable_container_engine_is_not_run(configured: Path) -> None:
    from unittest.mock import MagicMock

    from specweaver.sandbox.execution.container_executor import (
        ContainerEngineUnavailableError,
        ContainerSubprocessExecutor,
    )

    executor = MagicMock(spec=ContainerSubprocessExecutor)
    executor.execute.side_effect = ContainerEngineUnavailableError("no podman")

    [run] = run_extras(configured, "python", executor)

    assert (run.ran, run.reason) == (False, "no podman")
