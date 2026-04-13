# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration test for PipelineRunner Worktree Sandbox Bouncer."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow._base import RunContext
from specweaver.core.flow.models import PipelineDefinition, PipelineStep, StepAction, StepTarget
from specweaver.core.flow.runner import PipelineRunner
from specweaver.core.flow.state import StepResult, StepStatus
from specweaver.core.loom.atoms.base import AtomResult, AtomStatus


@pytest.mark.asyncio
@patch("specweaver.core.flow.reservation.SQLiteReservationSystem.release")
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
            "specweaver.core.loom.atoms.git.atom.GitAtom.run",
            autospec=True,
            side_effect=fake_atom_run,
        ),
        patch("specweaver.core.flow.runner.StepHandlerRegistry.get") as mock_get_handler,
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

        from specweaver.core.flow.state import RunStatus

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
        "specweaver.core.loom.atoms.git.atom.GitAtom.run", autospec=True, side_effect=fake_atom_run
    ):
        runner = PipelineRunner(pipeline, context)
        # It should catch the exception inside the runner and just mark the step/run as FAILED,
        # but let's see how _execute_loop catches errors.
        # Actually in runner, exceptions are caught as: `except Exception as exc: StepStatus.FAILED`
        result_run = await runner.run()

        from specweaver.core.flow.state import RunStatus

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
            "specweaver.core.loom.atoms.git.atom.GitAtom.run",
            autospec=True,
            side_effect=fake_atom_run,
        ),
        patch("specweaver.core.flow.runner.StepHandlerRegistry.get") as mock_get,
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
    # Create fake project cache folder
    (tmp_path / "node_modules").mkdir()

    step = PipelineStep(
        name="s1", action=StepAction.GENERATE, target=StepTarget.CODE, use_worktree=True
    )
    pipeline = PipelineDefinition(name="p1", steps=[step])
    context = RunContext(project_path=tmp_path, output_dir=tmp_path, spec_path=tmp_path / "Spec.md")

    with (
        patch("specweaver.core.loom.atoms.git.atom.GitAtom.run", autospec=True) as mock_atom,
        patch("os.symlink") as mock_symlink,
    ):
        mock_atom.return_value = AtomResult(status=AtomStatus.SUCCESS, message="")
        runner = PipelineRunner(pipeline, context)

        # Test symlink injection directly
        target_wt = ".worktrees/test1234"
        out_wt = tmp_path / ".worktrees" / "test1234"
        out_wt.mkdir(parents=True)

        runner._setup_sandbox_caches(target_wt)

        # Verify os.symlink was called correctly
        src_path = tmp_path / "node_modules"
        dst_path = out_wt / "node_modules"
        mock_symlink.assert_called_once_with(src_path, dst_path, target_is_directory=True)
