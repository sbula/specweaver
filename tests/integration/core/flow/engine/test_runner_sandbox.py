# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration test for PipelineRunner Worktree Sandbox Bouncer."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.sandbox.base import AtomResult, AtomStatus


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.reservation.SQLiteReservationSystem.release")
async def test_pipeline_runner_sandbox_bouncer(mock_release: MagicMock, tmp_path: Path):
    """Verifies that Runner intercepts use_worktree, bouncing string-maps cleanly, and flushes DB native bindings."""

    # 1. Setup a step requiring worktree
    step = PipelineStep(
        name="test_bouncer",
        action=StepAction.GENERATE,
        target=StepTarget.CODE,
        use_worktree=True,
    )
    pipeline = PipelineDefinition(name="test_pipe", steps=[step])
    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")
    context.pipeline_name = "test_pipe"

    # 2. Mock handler and GitAtom run explicitly to spy on intents in order
    intents_called = []

    # Mock GitAtom.run to record intents
    def fake_atom_run(self, ctx_dict):
        intent = ctx_dict.get("intent")
        intents_called.append(intent)

        if intent == "worktree_add":
            assert ctx_dict.get("branch").startswith("sf-test_pipe-")
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message="",
                exports={"worktree_path": ".worktrees/temp", "branch": ctx_dict.get("branch")},
            )
        if intent == "strip_merge":
            return AtomResult(status=AtomStatus.SUCCESS, message="", exports={"stripped_files": []})

        return AtomResult(status=AtomStatus.SUCCESS, message="")

    with (
        patch(
            "specweaver.sandbox.git.core.atom.GitAtom.run",
            autospec=True,
            side_effect=fake_atom_run,
        ),
        patch("specweaver.core.flow.engine.runner.StepHandlerRegistry.get") as mock_get_handler,
    ):
        mock_handler = MagicMock()

        async def fake_execute(step_def, ctx):
            # Verify that context was updated to the worktree path!
            assert ".worktrees" in str(ctx.output_dir)
            return StepResult(status=StepStatus.PASSED, started_at="", completed_at="")

        mock_handler.execute.side_effect = fake_execute
        mock_get_handler.return_value = mock_handler

        runner = PipelineRunner(pipeline, context)
        result_run = await runner.run()

        from specweaver.core.flow.engine.state import RunStatus

        assert result_run.status == RunStatus.COMPLETED

        # 3. Verify exactly sequential execution lifecycle
        assert intents_called == [
            "worktree_add",
            "worktree_sync",
            "strip_merge",
            "worktree_teardown",
        ]

        # 4. Verify explicit database flush capability
        assert mock_release.called
        assert mock_release.call_args[0][0] == result_run.run_id


@pytest.mark.asyncio
async def test_bouncer_worktree_add_fail(tmp_path: Path):
    """RuntimeError if worktree initialization fails."""
    step = PipelineStep(
        name="s1", action=StepAction.GENERATE, target=StepTarget.CODE, use_worktree=True
    )
    pipeline = PipelineDefinition(name="p1", steps=[step])
    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")

    def fake_atom_run(self, ctx_dict):
        # Fail directly on add
        if ctx_dict.get("intent") == "worktree_add":
            return AtomResult(status=AtomStatus.FAILED, message="simulated worktree add failure")
        return AtomResult(status=AtomStatus.SUCCESS, message="")

    with patch(
        "specweaver.sandbox.git.core.atom.GitAtom.run", autospec=True, side_effect=fake_atom_run
    ):
        runner = PipelineRunner(pipeline, context)
        # It should catch the exception inside the runner and just mark the step/run as FAILED,
        # but let's see how _execute_loop catches errors.
        # Actually in runner, exceptions are caught as: `except Exception as exc: StepStatus.FAILED`
        result_run = await runner.run()

        from specweaver.core.flow.engine.state import RunStatus

        assert result_run.status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_bouncer_strip_merge_fail_resilience(tmp_path: Path):
    """Logs Warning but survives strip_merge fail and GUARANTEES teardown."""
    step = PipelineStep(
        name="s1", action=StepAction.GENERATE, target=StepTarget.CODE, use_worktree=True
    )
    pipeline = PipelineDefinition(name="p1", steps=[step])
    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")

    intents_called = []

    def fake_atom_run(self, ctx_dict):
        intent = ctx_dict.get("intent")
        intents_called.append(intent)
        if intent == "strip_merge":
            return AtomResult(status=AtomStatus.FAILED, message="strip_merge failed")
        return AtomResult(status=AtomStatus.SUCCESS, message="")

    with (
        patch(
            "specweaver.sandbox.git.core.atom.GitAtom.run",
            autospec=True,
            side_effect=fake_atom_run,
        ),
        patch("specweaver.core.flow.engine.runner.StepHandlerRegistry.get") as mock_get,
    ):
        mock_handler = MagicMock()

        async def fake_execute(*args, **kwargs):
            return StepResult(status=StepStatus.PASSED, started_at="", completed_at="")

        mock_handler.execute.side_effect = fake_execute
        mock_get.return_value = mock_handler

        runner = PipelineRunner(pipeline, context)
        await runner.run()

        # Ensures teardown executed despite strip_merge failure!
        assert "strip_merge" in intents_called
        assert "worktree_teardown" in intents_called
        assert intents_called[-1] == "worktree_teardown"


@pytest.mark.asyncio
async def test_symlink_cache_folders(tmp_path: Path):
    """Verifies that heavy caches are appropriately symlinked (FR-2)."""
    # Create fake project cache folders
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".specweaver").mkdir()

    step = PipelineStep(
        name="s1", action=StepAction.GENERATE, target=StepTarget.CODE, use_worktree=True
    )
    pipeline = PipelineDefinition(name="p1", steps=[step])
    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")

    with (
        patch("specweaver.sandbox.git.core.atom.GitAtom.run", autospec=True) as mock_atom,
        patch("specweaver.sandbox.filesystem.core.atom.FileSystemAtom") as mock_fs_atom_cls,
    ):
        mock_atom.return_value = AtomResult(status=AtomStatus.SUCCESS, message="")
        mock_fs_atom = mock_fs_atom_cls.return_value
        mock_fs_atom.run.return_value = AtomResult(status=AtomStatus.SUCCESS, message="")

        PipelineRunner(pipeline, context)

        import logging

        from specweaver.core.flow.engine.runner_utils import setup_sandbox_caches

        target_wt = ".worktrees/test1234"
        out_wt = tmp_path / ".worktrees" / "test1234"
        out_wt.mkdir(parents=True)

        setup_sandbox_caches(context, target_wt, logging.getLogger())

        mock_fs_atom_cls.assert_called_with(cwd=tmp_path)

        from unittest.mock import call

        mock_fs_atom.run.assert_has_calls(
            [
                call(
                    {
                        "intent": "symlink",
                        "target": "node_modules",
                        "link_name": ".worktrees/test1234/node_modules",
                    }
                ),
                call(
                    {
                        "intent": "symlink",
                        "target": ".specweaver",
                        "link_name": ".worktrees/test1234/.specweaver",
                    }
                ),
            ],
            any_order=True,
        )


# ---------------------------------------------------------------------------
# INT-US-09 T7/T8: policy-aware isolation gate + execution_root propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("use_worktree", "enforce_isolation", "expect_isolated"),
    [
        (None, False, False),  # [Happy] unset + policy off -> host (backward compat)
        (None, True, True),  # [Happy] unset + policy on -> isolate
        (True, False, True),  # [Boundary] explicit on overrides policy off
        (False, True, False),  # [Boundary] explicit opt-out overrides policy on
        (True, True, True),  # [Boundary] both on
    ],
)
@patch("specweaver.core.flow.engine.reservation.SQLiteReservationSystem.release")
async def test_isolation_gate_resolution(
    mock_release, tmp_path: Path, use_worktree, enforce_isolation, expect_isolated
):
    """The gate resolves `step.use_worktree if not None else context.enforce_isolation`."""
    from unittest.mock import AsyncMock

    step = PipelineStep(
        name="s", action=StepAction.GENERATE, target=StepTarget.CODE, use_worktree=use_worktree
    )
    pipeline = PipelineDefinition(name="p", steps=[step])
    context = RunContext(
        project_path=tmp_path,
        output_dir=tmp_path,
        spec_path=tmp_path / "Spec.md",
        enforce_isolation=enforce_isolation,
    )
    context.pipeline_name = "p"
    passed = StepResult(status=StepStatus.PASSED, started_at="", completed_at="")

    with (
        patch(
            "specweaver.core.flow.engine.runner_utils.execute_in_sandbox",
            new=AsyncMock(return_value=passed),
        ) as mock_sandbox,
        patch("specweaver.core.flow.engine.runner.StepHandlerRegistry.get") as mock_get_handler,
    ):
        mock_handler = MagicMock()
        mock_handler.execute = AsyncMock(return_value=passed)
        mock_get_handler.return_value = mock_handler

        await PipelineRunner(pipeline, context).run()

        assert mock_sandbox.called is expect_isolated
        assert mock_handler.execute.called is (not expect_isolated)


@pytest.mark.asyncio
@patch("specweaver.core.flow.engine.reservation.SQLiteReservationSystem.release")
async def test_execute_in_sandbox_rebinds_execution_root(mock_release, tmp_path: Path):
    """T8: execute_in_sandbox sets the isolated context's execution_root to the worktree
    source-tree path (so untrusted-execution handlers bind their cwd there, not project_path)."""
    step = PipelineStep(
        name="s", action=StepAction.GENERATE, target=StepTarget.CODE, use_worktree=True
    )
    pipeline = PipelineDefinition(name="p", steps=[step])
    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")
    context.pipeline_name = "p"

    def fake_atom_run(self, ctx_dict):
        if ctx_dict.get("intent") == "worktree_add":
            return AtomResult(status=AtomStatus.SUCCESS, message="", exports={})
        return AtomResult(status=AtomStatus.SUCCESS, message="")

    seen = {}

    async def fake_execute(step_def, ctx):
        seen["execution_root"] = ctx.execution_root
        return StepResult(status=StepStatus.PASSED, started_at="", completed_at="")

    with (
        patch(
            "specweaver.sandbox.git.core.atom.GitAtom.run", autospec=True, side_effect=fake_atom_run
        ),
        patch("specweaver.core.flow.engine.runner.StepHandlerRegistry.get") as mock_get_handler,
    ):
        mock_handler = MagicMock()
        mock_handler.execute.side_effect = fake_execute
        mock_get_handler.return_value = mock_handler

        await PipelineRunner(pipeline, context).run()

    # The isolated context handed to the handler points execution_root inside the worktree.
    assert seen["execution_root"] is not None
    assert ".worktrees" in str(seen["execution_root"])
    # The ORIGINAL context is untouched (non-isolated steps keep project_path fallback).
    assert context.execution_root is None


# ---------------------------------------------------------------------------
# INT-US-09 T11: fail-closed worktree-add error is actionable + surfaces cause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worktree_add_failure_raises_actionable_error(tmp_path: Path):
    """[Graceful Degradation] when isolation is engaged but worktree_add fails
    (e.g. the project is not a git repo), the error surfaces GitAtom's actual
    message AND gives an actionable hint (git-repo requirement + how to disable)."""
    import logging
    from types import SimpleNamespace

    from specweaver.core.flow.engine.runner_utils import execute_in_sandbox

    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")
    context.pipeline_name = "p"
    runner = SimpleNamespace(_context=context)

    def fake_run(self, ctx_dict):
        if ctx_dict.get("intent") == "worktree_add":
            return AtomResult(status=AtomStatus.FAILED, message="fatal: not a git repository")
        return AtomResult(status=AtomStatus.SUCCESS, message="")

    with (
        patch("specweaver.sandbox.git.core.atom.GitAtom.run", autospec=True, side_effect=fake_run),
        pytest.raises(RuntimeError) as exc,
    ):
        await execute_in_sandbox(
            runner, MagicMock(), MagicMock(), MagicMock(), logging.getLogger("t")
        )

    msg = str(exc.value)
    assert "fatal: not a git repository" in msg  # GitAtom's ACTUAL message surfaced
    assert "git repositor" in msg.lower()  # actionable: git-repo requirement
    assert "enforce_worktree_isolation" in msg  # actionable: how to disable
    assert str(tmp_path) in msg  # names the offending project


@pytest.mark.asyncio
async def test_worktree_add_failure_does_not_assume_non_git_cause(tmp_path: Path):
    """[Hostile/Wrong Input] the message must NOT hard-assume 'not a git repo' — a
    different failure (e.g. a stale worktree) must be surfaced verbatim."""
    import logging
    from types import SimpleNamespace

    from specweaver.core.flow.engine.runner_utils import execute_in_sandbox

    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")
    context.pipeline_name = "p"
    runner = SimpleNamespace(_context=context)

    def fake_run(self, ctx_dict):
        if ctx_dict.get("intent") == "worktree_add":
            return AtomResult(status=AtomStatus.FAILED, message="fatal: worktree already exists")
        return AtomResult(status=AtomStatus.SUCCESS, message="")

    with (
        patch("specweaver.sandbox.git.core.atom.GitAtom.run", autospec=True, side_effect=fake_run),
        pytest.raises(RuntimeError) as exc,
    ):
        await execute_in_sandbox(
            runner, MagicMock(), MagicMock(), MagicMock(), logging.getLogger("t")
        )

    assert "worktree already exists" in str(exc.value)  # actual cause, not assumed
