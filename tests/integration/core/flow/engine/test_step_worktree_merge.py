# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step in its own worktree lands its target files in the project, and nothing else.

Proves: D-EXEC-02 FR-3, D-EXEC-02 FR-4

Real git and bash; skips cleanly without them. The allow-list is the session rule: the spec's
generation targets, `src/<stem>.py` and `tests/test_<stem>.py`.

| Bucket | Case |
|---|---|
| Happy | the step's target file lands in the real project |
| Boundary | a file outside the targets is stripped |
| Degradation | a dirty real tree refuses the merge and fails the step; a failed step lands nothing |
| Hostile | a write to `README.md` never lands; a step writing through its project path stays in the worktree |
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
_BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(_GIT is None or _BASH is None, reason="git and bash required")

_WRITE = (
    "mkdir -p src\n"
    'echo "def greet(): return 1" > src/greet.py\n'
    'echo "stray" > other.txt\n'
    'echo "hijacked" > README.md\n'
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True)


def _project(tmp_path: Path) -> Path:
    scripts = tmp_path / ".specweaver" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "write.sh").write_text(_WRITE, encoding="utf-8", newline="\n")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    return tmp_path


def _run(project: Path, *, script: str = "write.sh", registry: StepHandlerRegistry | None = None):
    step = PipelineStep(
        name="w",
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": script},
        use_worktree=True,
    )
    context = RunContext(
        project_path=project,
        spec_path=project / "specs" / "greet_spec.md",
        model=ModelAccess(config=MagicMock()),
    )
    pipeline = PipelineDefinition(name="p", steps=[step])
    runner = PipelineRunner(pipeline, context, registry=registry or StepHandlerRegistry())
    return asyncio.run(runner.run())


def test_the_steps_target_file_lands_and_nothing_else(tmp_path: Path) -> None:
    project = _project(tmp_path)

    run = _run(project)

    assert run.status == RunStatus.COMPLETED, run
    assert (project / "src" / "greet.py").read_text(encoding="utf-8").strip()
    assert not (project / "other.txt").exists()
    assert (project / "README.md").read_text(encoding="utf-8") == "seed\n"


def test_a_dirty_real_tree_fails_the_step(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "README.md").write_text("my unsaved edit\n", encoding="utf-8")

    run = _run(project)

    assert run.status != RunStatus.COMPLETED
    assert (project / "README.md").read_text(encoding="utf-8") == "my unsaved edit\n"
    assert not (project / "src" / "greet.py").exists()


def test_a_failed_step_lands_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path)
    scripts = project / ".specweaver" / "scripts"
    (scripts / "fail.sh").write_text(_WRITE + "exit 1\n", encoding="utf-8", newline="\n")
    _git(project, "add", ".")
    _git(project, "commit", "-m", "fail script")

    _run(project, script="fail.sh")

    assert not (project / "src" / "greet.py").exists()


class _WritesThroughProjectPath:
    async def execute(self, _step, context):
        from specweaver.core.flow.engine.state import StepResult, StepStatus

        (context.project_path / "src").mkdir(exist_ok=True)
        (context.project_path / "src" / "greet.py").write_text("x = 1\n", encoding="utf-8")
        (context.project_path / "other.txt").write_text("stray\n", encoding="utf-8")
        return StepResult(status=StepStatus.PASSED, started_at="t0", completed_at="t1")


def test_a_step_writing_through_its_project_path_stays_in_the_worktree(tmp_path: Path) -> None:
    project = _project(tmp_path)
    registry = StepHandlerRegistry()
    registry.register(StepAction.BASH, StepTarget.SCRIPT, _WritesThroughProjectPath())

    run = _run(project, registry=registry)

    assert run.status == RunStatus.COMPLETED, run
    assert (project / "src" / "greet.py").exists()
    assert not (project / "other.txt").exists()
