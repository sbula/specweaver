# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The QA tools never run a tool on a path outside the project.

Proves: TECH-075 FR-5
Proves: TECH-075 NFR-3

Built the way an agent would get them (`create_qa_runner_interface`): a real `QARunnerTool` over a
real `QARunnerAtom` and a real Python runner, over a tmp project. Only the process start is
watched, so the proof is that no process starts for an outside path.

| Bucket | Case |
|---|---|
| Happy | a target inside starts the tool |
| Boundary | the implementer's six intents all go through the same check |
| Degradation | a refusal is an `error` result the agent can read |
| Hostile | `../`, an absolute path outside, a link that points outside, an outside entrypoint |
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.qa_runner.interfaces.facades import create_qa_runner_interface

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []

    def record(self: SubprocessExecutor, *args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        raise RuntimeError("no process in this test")

    monkeypatch.setattr(SubprocessExecutor, "execute", record)
    return calls


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'p'\n", encoding="utf-8")
    (root / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "outside").mkdir()
    (root / "escape").symlink_to(tmp_path / "outside", target_is_directory=True)
    return root


_CALLS = {
    "run_tests": lambda qa, t: qa.run_tests(target=t),
    "run_linter": lambda qa, t: qa.run_linter(target=t),
    "run_complexity": lambda qa, t: qa.run_complexity(target=t),
    "run_compiler": lambda qa, t: qa.run_compiler(target=t),
    "run_debugger": lambda qa, t: qa.run_debugger(target=t, entrypoint="src/mod.py"),
    "run_architecture": lambda qa, t: qa.run_architecture(target=t),
}


@pytest.mark.parametrize("intent", list(_CALLS))
@pytest.mark.parametrize("target", ["../outside", "ABSOLUTE", "escape/x.py"])
def test_an_outside_target_starts_nothing(
    project: Path, started: list[Any], intent: str, target: str
) -> None:
    given = str(project.parent / "outside") if target == "ABSOLUTE" else target
    qa = create_qa_runner_interface(role="implementer", cwd=project, language="python")

    result = _CALLS[intent](qa, given)

    assert result.status == "error"
    assert "outside" in result.message
    assert started == []


def test_an_outside_entrypoint_starts_nothing(project: Path, started: list[Any]) -> None:
    qa = create_qa_runner_interface(role="implementer", cwd=project, language="python")
    result = qa.run_debugger(target="src", entrypoint="../outside/evil.py")
    assert result.status == "error"
    assert started == []


def test_a_target_inside_starts_the_tool(project: Path, started: list[Any]) -> None:
    qa = create_qa_runner_interface(role="implementer", cwd=project, language="python")
    with suppress(RuntimeError):  # the recorder stops the process start
        qa.run_linter(target="src/mod.py")
    assert started != []
