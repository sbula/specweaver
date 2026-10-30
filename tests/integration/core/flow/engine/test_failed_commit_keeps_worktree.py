# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A failed worktree commit or merge fails the run and keeps the worktree with the work.

Proves: TECH-087 FR-7

Path P-3 of the design, on real git. The commit failures are real: the step's script takes the
worktree's index lock (`index.lock`), as a crashed git process leaves it, so `git add -A` fails.
The merge failures are real: the user has an uncommitted edit to the file the step changes.
Only the session's final commit, which runs after every step was already snapshotted, is made to
fail by a patched intent, because no real repo state fails it without failing a snapshot first.
Before TECH-087 every one of these runs deleted the worktree.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

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
from specweaver.core.flow.run_state.run_context import ModelAccess, RunContext

if TYPE_CHECKING:
    from pathlib import Path

_GIT = shutil.which("git")
_BASH = shutil.which("bash")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(_GIT is None or _BASH is None, reason="git and bash required"),
]

_LOCKS_INDEX = 'mkdir -p src\necho "def foo(): pass" > src/foo.py\ntouch "$(git rev-parse --git-dir)/index.lock"\n'
_WRITES_FOO = 'echo "def foo(): pass" > src/foo.py\n'


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _project(tmp_path: Path, script: str) -> Path:
    scripts = tmp_path / ".specweaver" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "gen.sh").write_text(script, encoding="utf-8", newline="\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("original\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", "src/foo.py", ".specweaver/scripts/gen.sh")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _step(*, use_worktree: bool) -> PipelineStep:
    return PipelineStep(
        name="gen",
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": "gen.sh"},
        use_worktree=use_worktree or None,
    )


def _context(project: Path, *, session: bool, task_id: str | None = None) -> RunContext:
    context = RunContext(
        project_path=project, spec_path=project / "spec.md", model=ModelAccess(config=MagicMock())
    )
    context.isolation = context.isolation.model_copy(
        update={"session_isolation": session, "allowed_paths": ["src/foo.py"]}
    )
    if task_id:
        context.run = context.run.model_copy(update={"task_id": task_id})
    return context


def _run(context: RunContext, *, session: bool):
    pipeline = PipelineDefinition(name="p", steps=[_step(use_worktree=not session)])
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def _kept(project: Path) -> Path:
    (worktree,) = [p for p in (project / ".worktrees").iterdir() if p.is_dir()]
    return worktree


def _assert_kept(project: Path, message: str) -> Path:
    worktree = _kept(project)
    assert (worktree / "src" / "foo.py").read_text(encoding="utf-8") == "def foo(): pass\n"
    assert f"kept at {worktree}" in message
    assert f"git worktree remove --force {worktree}" in message
    return worktree


def _error(run) -> str:
    return run.step_records[0].result.error_message or ""


# --- commit failures ----------------------------------------------------------------------


def test_a_sandboxed_step_whose_commit_fails_keeps_its_worktree(tmp_path: Path) -> None:
    project = _project(tmp_path, _LOCKS_INDEX)

    run = _run(_context(project, session=False, task_id="t1"), session=False)

    assert run.status == RunStatus.FAILED
    assert "worktree commit failed" in _error(run)
    _assert_kept(project, _error(run))
    assert (project / "src" / "foo.py").read_text(encoding="utf-8") == "original\n"


def test_a_session_step_whose_snapshot_fails_keeps_the_worktree(tmp_path: Path) -> None:
    project = _project(tmp_path, _LOCKS_INDEX)

    run = _run(_context(project, session=True), session=True)

    assert run.status == RunStatus.FAILED
    assert "snapshot" in _error(run)
    _assert_kept(project, _error(run))


def test_a_session_whose_final_commit_fails_keeps_the_worktree(tmp_path: Path) -> None:
    from specweaver.sandbox.base import AtomResult, AtomStatus
    from specweaver.sandbox.git.core.atom import GitAtom

    project = _project(tmp_path, _WRITES_FOO)
    real = GitAtom.run

    def final_commit_fails(self, context):
        if context.get("intent") == "worktree_commit" and "step" not in context:
            return AtomResult(status=AtomStatus.FAILED, message="fatal: disk full")
        return real(self, context)

    with (
        patch.object(GitAtom, "run", final_commit_fails),
        pytest.raises(RuntimeError) as raised,
    ):
        _run(_context(project, session=True), session=True)

    assert "worktree commit failed: fatal: disk full" in str(raised.value)
    _assert_kept(project, str(raised.value))


# --- merge failures (the user chose to keep these too, 2026-10-30) ------------------------


def test_a_sandboxed_step_whose_merge_fails_keeps_worktree_and_branch(tmp_path: Path) -> None:
    project = _project(tmp_path, _WRITES_FOO)
    (project / "src" / "foo.py").write_text("DIRTY LOCAL EDIT\n", encoding="utf-8")

    run = _run(_context(project, session=False, task_id="t2"), session=False)

    assert run.status == RunStatus.FAILED
    assert "strip-merge failed" in _error(run)
    _assert_kept(project, _error(run))
    assert "sf-p-t2" in _git(project, "branch")
    assert (project / "src" / "foo.py").read_text(encoding="utf-8") == "DIRTY LOCAL EDIT\n"


def test_a_session_whose_merge_fails_keeps_worktree_and_branch(tmp_path: Path) -> None:
    project = _project(tmp_path, _WRITES_FOO)
    (project / "src" / "foo.py").write_text("DIRTY LOCAL EDIT\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as raised:
        _run(_context(project, session=True), session=True)

    assert "strip-merge failed" in str(raised.value)
    _assert_kept(project, str(raised.value))
    assert "sf-session-" in _git(project, "branch")


# --- the next run -------------------------------------------------------------------------


def test_a_rerun_refuses_while_the_kept_worktree_is_there(tmp_path: Path) -> None:
    project = _project(tmp_path, _LOCKS_INDEX)
    _run(_context(project, session=False, task_id="t3"), session=False)
    worktree = _kept(project)

    rerun = _run(_context(project, session=False, task_id="t3"), session=False)

    assert rerun.status == RunStatus.FAILED
    assert f"git worktree remove --force {worktree}" in _error(rerun)
    assert (worktree / "src" / "foo.py").is_file()


def test_a_rerun_after_the_user_removed_it_starts_and_drops_the_marker(tmp_path: Path) -> None:
    project = _project(tmp_path, _LOCKS_INDEX)
    _run(_context(project, session=False, task_id="t4"), session=False)
    worktree = _kept(project)
    lock = _git(worktree, "rev-parse", "--absolute-git-dir").strip() + "/index.lock"
    subprocess.run(["rm", "-f", lock], check=True)
    _git(project, "worktree", "remove", "--force", str(worktree))
    (project / ".specweaver" / "scripts" / "gen.sh").write_text(_WRITES_FOO, encoding="utf-8")
    _git(project, "commit", "-q", "-am", "a script that takes no lock")

    rerun = _run(_context(project, session=False, task_id="t4"), session=False)

    assert rerun.status == RunStatus.COMPLETED
    assert not (project / ".worktrees" / "t4.kept").exists()
    assert (project / "src" / "foo.py").read_text(encoding="utf-8") == "def foo(): pass\n"
