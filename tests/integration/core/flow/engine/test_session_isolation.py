# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-01 (T3): per-run (session) worktree isolation — real git, unmocked.

Proves the thing the INT-US-09 per-step model cannot do: a multi-step run shares ONE
worktree, so a file written by step 1 survives for step 2 to read — while the real
source root stays unmutated (no reconcile in SF-01) and the worktree + branch are
cleaned up. Needs git + bash; skips cleanly otherwise.

Proves: C-EXEC-06 FR-7, B-FLOW-05 FR-7
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

_WRITE = 'echo "SESSION_CONTENT" > shared.txt\n'
_READ = 'if [ -f shared.txt ]; then cat shared.txt; else echo "MISSING"; fi\n'


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True)


def _write_scripts(tmp_path: Path) -> None:
    scripts = tmp_path / ".specweaver" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "write.sh").write_text(_WRITE, encoding="utf-8", newline="\n")
    (scripts / "read.sh").write_text(_READ, encoding="utf-8", newline="\n")


def _commit_project(tmp_path: Path) -> None:
    _write_scripts(tmp_path)
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    _git(
        tmp_path, "add", "README.md", ".specweaver/scripts/write.sh", ".specweaver/scripts/read.sh"
    )
    _git(tmp_path, "commit", "-m", "init")


def _bash_step(name: str, script: str, *, use_worktree: bool | None = None) -> PipelineStep:
    return PipelineStep(
        name=name,
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": script},
        use_worktree=use_worktree,
    )


def _ctx(tmp_path: Path, *, session: bool) -> RunContext:
    ctx = RunContext(
        project_path=tmp_path, spec_path=tmp_path / "spec.md", model=ModelAccess(config=MagicMock())
    )
    ctx.isolation = ctx.isolation.model_copy(update={"session_isolation": session})
    return ctx


def _run(pipeline: PipelineDefinition, context: RunContext):
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


# --- Happy: file persists across steps in ONE worktree --------------------


def test_session_persists_file_across_steps(tmp_path: Path) -> None:
    _commit_project(tmp_path)
    pipe = PipelineDefinition(
        name="p", steps=[_bash_step("w", "write.sh"), _bash_step("r", "read.sh")]
    )
    run_state = _run(pipe, _ctx(tmp_path, session=True))

    assert run_state.status == RunStatus.COMPLETED, run_state
    # Step 2 read the file step 1 wrote → they shared one worktree.
    read_stdout = run_state.step_records[1].result.output["stdout"]
    assert "SESSION_CONTENT" in read_stdout
    # Isolation (no reconcile in SF-01): the real source root was NOT mutated.
    assert not (tmp_path / "shared.txt").exists()
    # Cleanup: worktree gone, session branch gone.
    assert not (tmp_path / ".worktrees").exists() or not any((tmp_path / ".worktrees").iterdir())
    branches = subprocess.run([_GIT, "branch"], cwd=tmp_path, capture_output=True, text=True).stdout
    assert "sf-session-" not in branches


# --- Graceful degradation: non-git project fails closed -------------------


def test_session_on_non_git_project_fails_closed(tmp_path: Path) -> None:
    _write_scripts(tmp_path)  # NO git init
    pipe = PipelineDefinition(name="p", steps=[_bash_step("w", "write.sh")])
    with pytest.raises(RuntimeError):
        _run(pipe, _ctx(tmp_path, session=True))
    # Fail-closed: the step never ran against the real root.
    assert not (tmp_path / "shared.txt").exists()


# --- Boundary: empty pipeline under session is a clean no-op --------------


def test_session_empty_pipeline_noop(tmp_path: Path) -> None:
    _commit_project(tmp_path)
    run_state = _run(PipelineDefinition(name="p", steps=[]), _ctx(tmp_path, session=True))
    assert run_state.status == RunStatus.COMPLETED


# --- Control: session off → per-step path unchanged (runs at real root) ----


def test_no_session_runs_at_real_root(tmp_path: Path) -> None:
    _commit_project(tmp_path)
    run_state = _run(
        PipelineDefinition(name="p", steps=[_bash_step("w", "write.sh")]),
        _ctx(tmp_path, session=False),
    )
    assert run_state.status == RunStatus.COMPLETED
    # Not isolated → the file was written at the real root.
    assert (tmp_path / "shared.txt").exists()


# --- T4: session-active bypass of per-step isolation ----------------------


def test_explicit_use_worktree_step_still_shares_session_worktree(tmp_path: Path) -> None:
    """[Happy] A step with explicit use_worktree=True inside a session must run in the
    SESSION worktree, NOT a nested per-step one — otherwise it wouldn't see step 1's file."""
    _commit_project(tmp_path)
    pipe = PipelineDefinition(
        name="p",
        steps=[_bash_step("w", "write.sh"), _bash_step("r", "read.sh", use_worktree=True)],
    )
    run_state = _run(pipe, _ctx(tmp_path, session=True))

    assert run_state.status == RunStatus.COMPLETED, run_state
    # If per-step isolation had NOT been bypassed, step 2 would get its own worktree and read MISSING.
    assert "SESSION_CONTENT" in run_state.step_records[1].result.output["stdout"]


# --- A park keeps the session worktree for resume (B-FLOW-05 #2) -----------


def _parks_once_on(step_name: str):
    """BashActionHandler.execute that parks `step_name` once, then runs it for real."""
    from specweaver.core.flow.engine.state import StepResult, StepStatus
    from specweaver.core.flow.handlers.bash_action import BashActionHandler

    real = BashActionHandler.execute
    parked: list[str] = []

    async def execute(self, step, context):
        if step.name == step_name and not parked:
            parked.append(step.name)
            return StepResult(
                status=StepStatus.WAITING_FOR_INPUT, started_at="t0", completed_at="t1"
            )
        return await real(self, step, context)

    return execute


def _two_steps() -> PipelineDefinition:
    return PipelineDefinition(
        name="p", steps=[_bash_step("w", "write.sh"), _bash_step("r", "read.sh")]
    )


def test_a_parked_run_resumes_in_the_worktree_it_parked_in(tmp_path: Path) -> None:
    from unittest.mock import patch

    from specweaver.core.flow.engine.store import StateStore

    _commit_project(tmp_path)
    store = StateStore(tmp_path / "state.db")

    def runner() -> PipelineRunner:
        return PipelineRunner(
            _two_steps(), _ctx(tmp_path, session=True), registry=StepHandlerRegistry(), store=store
        )

    with patch(
        "specweaver.core.flow.handlers.bash_action.BashActionHandler.execute",
        new=_parks_once_on("r"),
    ):
        parked = asyncio.run(runner().run())
        worktree = tmp_path / ".worktrees" / f"session-{parked.run_id}"
        assert parked.status == RunStatus.PARKED
        assert (worktree / "shared.txt").exists(), "the parked run lost its worktree"

        resumed = asyncio.run(runner().resume(parked.run_id))

    assert resumed.status == RunStatus.COMPLETED, resumed
    assert "SESSION_CONTENT" in resumed.step_records[1].result.output["stdout"]
    assert not worktree.exists()


def test_a_park_nobody_can_resume_ends_the_run_and_removes_the_worktree(tmp_path: Path) -> None:
    from unittest.mock import patch

    _commit_project(tmp_path)
    with patch(
        "specweaver.core.flow.handlers.bash_action.BashActionHandler.execute",
        new=_parks_once_on("r"),
    ):
        run_state = _run(_two_steps(), _ctx(tmp_path, session=True))

    assert run_state.status == RunStatus.PARKED
    assert not (tmp_path / ".worktrees" / f"session-{run_state.run_id}").exists()
    assert not (tmp_path / "shared.txt").exists()


def test_a_resume_whose_worktree_is_gone_refuses(tmp_path: Path) -> None:
    from unittest.mock import patch

    from specweaver.core.flow.engine.store import StateStore

    _commit_project(tmp_path)
    store = StateStore(tmp_path / "state.db")

    def runner() -> PipelineRunner:
        return PipelineRunner(
            _two_steps(), _ctx(tmp_path, session=True), registry=StepHandlerRegistry(), store=store
        )

    with patch(
        "specweaver.core.flow.handlers.bash_action.BashActionHandler.execute",
        new=_parks_once_on("r"),
    ):
        parked = asyncio.run(runner().run())
    _git(tmp_path, "worktree", "remove", "--force", f".worktrees/session-{parked.run_id}")

    with pytest.raises(RuntimeError, match="worktree"):
        asyncio.run(runner().resume(parked.run_id))
    assert not (tmp_path / "shared.txt").exists()


# --- Q3: idempotent create recovers from a crash-orphaned worktree/branch --


def test_crash_orphan_worktree_is_pruned_before_readd(tmp_path: Path) -> None:
    """[Graceful degradation] A hard crash can skip teardown, leaving a stale
    .worktrees/session-<id> + sf-session-<id>. A retry with the SAME run_id must prune it
    and recreate — not fail-closed on 'branch already exists'."""
    import uuid
    from unittest.mock import patch

    _commit_project(tmp_path)
    fixed = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    wt = f".worktrees/session-{fixed}"
    branch = f"sf-session-{fixed}"
    # Simulate the orphan left by a crashed prior run.
    _git(tmp_path, "worktree", "add", "-b", branch, wt, "HEAD")
    assert (tmp_path / wt).exists()

    pipe = PipelineDefinition(
        name="p", steps=[_bash_step("w", "write.sh"), _bash_step("r", "read.sh")]
    )
    with patch("specweaver.core.flow.engine.runner.uuid.uuid4", return_value=fixed):
        run_state = _run(pipe, _ctx(tmp_path, session=True))

    assert run_state.status == RunStatus.COMPLETED, run_state
    assert "SESSION_CONTENT" in run_state.step_records[1].result.output["stdout"]
    # Recovered + cleaned up again.
    assert not (tmp_path / wt).exists()


# --- Context is restored after a session run ------------------------------


def test_context_restored_after_a_parked_session(tmp_path: Path) -> None:
    """[Boundary] The runner's context is the original again, not the worktree copy."""
    from unittest.mock import patch

    _commit_project(tmp_path)
    ctx = _ctx(tmp_path, session=True)
    runner = PipelineRunner(_two_steps(), ctx, registry=StepHandlerRegistry())
    with patch(
        "specweaver.core.flow.handlers.bash_action.BashActionHandler.execute",
        new=_parks_once_on("w"),
    ):
        asyncio.run(runner.run())

    assert runner._context is ctx
    assert runner._context.project_path == tmp_path
