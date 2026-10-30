# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw drift check-rot --staged` reads the git index through `SubprocessExecutor`.

Proves: TECH-087 FR-17

| Bucket | Case |
|---|---|
| Happy | the staged paths come back, blank lines dropped |
| Boundary | nothing staged gives an empty list, not an error |
| Degradation | git missing (exit -1) or timed out: one line, exit 1, no traceback |
| Hostile | git's own error text is shown as git wrote it, not raised |
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer

from specweaver.assurance.validation.interfaces import cli_drift
from specweaver.sandbox.execution.models import SubprocessResult


def _git_answers(monkeypatch: pytest.MonkeyPatch, **result: object) -> MagicMock:
    fields: dict[str, object] = {
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "duration_seconds": 0.0,
    }
    fields.update(result)
    executor = MagicMock()
    executor.execute.return_value = SubprocessResult(**fields)  # type: ignore[arg-type]
    monkeypatch.setattr(cli_drift, "SubprocessExecutor", MagicMock(return_value=executor))
    return executor


def _printed(capsys: pytest.CaptureFixture[str]) -> str:
    return " ".join(capsys.readouterr().out.split())


def test_the_staged_paths_come_back(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = _git_answers(monkeypatch, stdout="src/a.py\n\n  src/b.py \n")

    assert cli_drift._staged_files() == ["src/a.py", "src/b.py"]
    cmd = executor.execute.call_args.args[0]
    assert cmd == ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"]


def test_nothing_staged_is_an_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _git_answers(monkeypatch, stdout="")

    assert cli_drift._staged_files() == []


def test_git_missing_is_one_line_and_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _git_answers(monkeypatch, exit_code=-1, stderr="[Errno 2] No such file or directory: 'git'")

    with pytest.raises(typer.Exit) as exited:
        cli_drift._staged_files()

    assert exited.value.exit_code == 1
    assert "Failed to query git index: [Errno 2] No such file or directory: 'git'" in _printed(
        capsys
    )


def test_a_timeout_is_one_line_and_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _git_answers(monkeypatch, exit_code=-1, timed_out=True)

    with pytest.raises(typer.Exit) as exited:
        cli_drift._staged_files()

    assert exited.value.exit_code == 1
    assert "Failed to query git index: timed out" in _printed(capsys)


def test_git_s_own_error_is_shown_not_raised(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _git_answers(monkeypatch, exit_code=128, stderr="fatal: not a git repository")

    with pytest.raises(typer.Exit) as exited:
        cli_drift._staged_files()

    assert exited.value.exit_code == 1
    assert "Failed to query git index: fatal: not a git repository" in _printed(capsys)


def test_a_hook_s_git_variables_reach_git_and_nothing_else_is_added(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_INDEX_FILE", "/repo/.git/next-index")
    monkeypatch.setenv("GIT_WORK_TREE", "/repo")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-pass")
    executor = _git_answers(monkeypatch)

    cli_drift._staged_files()

    assert executor.execute.call_args.kwargs["extra_env"] == {
        "GIT_INDEX_FILE": "/repo/.git/next-index",
        "GIT_WORK_TREE": "/repo",
    }


def test_outside_a_hook_no_variable_is_added(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_INDEX_FILE", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    executor = _git_answers(monkeypatch)

    cli_drift._staged_files()

    assert executor.execute.call_args.kwargs["extra_env"] == {}
