# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for ValidateTestsHandler — runs tests via QARunnerAtom."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.sandbox.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")


def _step(**kwargs) -> PipelineStep:
    defaults = {"name": "run_tests", "action": StepAction.VALIDATE, "target": StepTarget.TESTS}
    defaults.update(kwargs)
    return PipelineStep(**defaults)


class TestValidateTestsHandler:
    """Tests for the ValidateTestsHandler."""

    @pytest.mark.asyncio
    async def test_all_tests_pass(self, tmp_path: Path) -> None:
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="All 10 tests passed.",
            exports={"passed": 10, "failed": 0, "errors": 0, "total": 10},
        )

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            result = await handler.execute(_step(), _ctx(tmp_path))

        assert result.status == StepStatus.PASSED
        assert result.output["passed"] == 10

    @pytest.mark.asyncio
    async def test_some_tests_fail(self, tmp_path: Path) -> None:
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.FAILED,
            message="3 failed, 0 errors out of 10 tests.",
            exports={"passed": 7, "failed": 3, "errors": 0, "total": 10, "failures": []},
        )

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            result = await handler.execute(_step(), _ctx(tmp_path))

        assert result.status == StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_custom_params(self, tmp_path: Path) -> None:
        """Custom step params (kind, scope, timeout) are passed to atom."""
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"passed": 3, "failed": 0, "total": 3},
        )

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_atom = mock_get.return_value
            mock_atom.run.return_value = mock_result
            step = _step(params={"kind": "integration", "scope": "flow", "timeout": 60})
            await handler.execute(step, _ctx(tmp_path))

        call_ctx = mock_atom.run.call_args[0][0]
        assert call_ctx["kind"] == "integration"
        assert call_ctx["scope"] == "flow"
        assert call_ctx["timeout"] == 60

    @pytest.mark.asyncio
    async def test_with_coverage(self, tmp_path: Path) -> None:
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"passed": 5, "failed": 0, "total": 5, "coverage_pct": 82.0},
        )

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_atom = mock_get.return_value
            mock_atom.run.return_value = mock_result
            step = _step(params={"coverage": True})
            result = await handler.execute(step, _ctx(tmp_path))

        assert result.status == StepStatus.PASSED
        assert result.output["coverage_pct"] == 82.0


# ---------------------------------------------------------------------------
# B-EXEC-01: sandbox_settings passthrough
# ---------------------------------------------------------------------------


class TestGetAtomSandboxSettings:
    def test_passes_none_when_context_config_is_none(self, tmp_path: Path) -> None:
        handler = ValidateTestsHandler()
        context = _ctx(tmp_path)
        assert context.config is None

        with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom") as mock_atom_cls:
            handler._get_atom(context)

        mock_atom_cls.assert_called_once_with(cwd=tmp_path, sandbox_settings=None)

    def test_passes_sandbox_settings_from_context_config(self, tmp_path: Path) -> None:
        from specweaver.core.config.settings import SandboxSettings, SpecWeaverSettings

        handler = ValidateTestsHandler()
        config = SpecWeaverSettings(
            llm={"model": "test-model"}, sandbox=SandboxSettings(execution_mode="container")
        )
        context = _ctx(tmp_path)
        context.config = config

        with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom") as mock_atom_cls:
            handler._get_atom(context)

        mock_atom_cls.assert_called_once_with(cwd=tmp_path, sandbox_settings=config.sandbox)


# ---------------------------------------------------------------------------
# INT-US-09 CB-3 (T10): run_tests execution binds cwd to the worktree
# ---------------------------------------------------------------------------


class TestGetAtomExecutionRoot:
    """ValidateTests (run_tests/pytest) is an untrusted-execution surface: under
    isolation its QARunnerAtom cwd must bind to the worktree (execution_root)."""

    def test_binds_cwd_to_execution_root_when_set(self, tmp_path: Path) -> None:
        # [Happy] isolated step → cwd is the worktree; sandbox_settings stay None
        # (container-neutral — context.config is not populated on this path).
        handler = ValidateTestsHandler()
        wt = tmp_path / ".worktrees" / "task-1"
        context = _ctx(tmp_path)
        context.execution_root = wt
        assert context.config is None
        with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom") as mock_atom_cls:
            handler._get_atom(context)
        mock_atom_cls.assert_called_once_with(cwd=wt, sandbox_settings=None)

    def test_falls_back_to_project_path_when_execution_root_none(self, tmp_path: Path) -> None:
        # [Boundary/backward-compat] non-isolated step → cwd unchanged.
        handler = ValidateTestsHandler()
        context = _ctx(tmp_path)
        assert context.execution_root is None
        with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom") as mock_atom_cls:
            handler._get_atom(context)
        mock_atom_cls.assert_called_once_with(cwd=tmp_path, sandbox_settings=None)

    def test_rebind_preserves_sandbox_settings_from_config(self, tmp_path: Path) -> None:
        # [Edge] if context.config IS populated (e.g. workflow CLIs), the rebind must
        # still pass through sandbox_settings unchanged alongside the new cwd.
        from specweaver.core.config.settings import SandboxSettings, SpecWeaverSettings

        handler = ValidateTestsHandler()
        wt = tmp_path / ".worktrees" / "task-1"
        context = _ctx(tmp_path)
        context.execution_root = wt
        context.config = SpecWeaverSettings(
            llm={"model": "test-model"}, sandbox=SandboxSettings(enforce_worktree_isolation=True)
        )
        with patch("specweaver.sandbox.qa_runner.core.atom.QARunnerAtom") as mock_atom_cls:
            handler._get_atom(context)
        mock_atom_cls.assert_called_once_with(cwd=wt, sandbox_settings=context.config.sandbox)
