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


# ---------------------------------------------------------------------------
# INT-US-24 SF-01 T1 (FR-3): scenario-kind semantics — no marker filter,
# 0-collected is a loud failure, other kinds byte-identical.
# ---------------------------------------------------------------------------


class TestScenarioKindSemantics:
    @pytest.mark.asyncio
    async def test_scenario_kind_suppresses_marker_at_atom_call(self, tmp_path: Path) -> None:
        # [Happy] kind "scenario" must reach the atom as "" (no pytest -m filter) —
        # the generated-file target path is the discriminator, and the converter
        # emits no `scenario` marker (a `-m scenario` run deselects everything).
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="All 4 tests passed.",
            exports={"passed": 4, "failed": 0, "errors": 0, "total": 4},
        )
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_atom = mock_get.return_value
            mock_atom.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            result = await handler.execute(step, _ctx(tmp_path))

        assert result.status == StepStatus.PASSED
        call_ctx = mock_atom.run.call_args[0][0]
        assert call_ctx["kind"] == ""

    @pytest.mark.asyncio
    async def test_resolve_targets_receives_original_kind(self, tmp_path: Path) -> None:
        # [Edge] marker suppression applies at the atom-call site ONLY —
        # _resolve_targets keeps the original kind for its tests/<kind> fallbacks.
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"passed": 1, "failed": 0, "errors": 0, "total": 1},
        )
        with (
            patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get,
            patch.object(
                handler, "_resolve_targets", return_value=["scenarios/generated/test_x.py"]
            ) as mock_resolve,
        ):
            mock_get.return_value.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            await handler.execute(step, _ctx(tmp_path))

        mock_resolve.assert_called_once()
        assert mock_resolve.call_args[0][2] == "scenario"

    @pytest.mark.asyncio
    async def test_other_kinds_pass_marker_through_unchanged(self, tmp_path: Path) -> None:
        # [Boundary/backward-compat] non-scenario kinds keep marker semantics.
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"passed": 2, "failed": 0, "errors": 0, "total": 2},
        )
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_atom = mock_get.return_value
            mock_atom.run.return_value = mock_result
            await handler.execute(_step(params={"kind": "e2e", "target": "tests"}), _ctx(tmp_path))

        assert mock_atom.run.call_args[0][0]["kind"] == "e2e"

    @pytest.mark.asyncio
    async def test_scenario_zero_collected_fails_loud(self, tmp_path: Path) -> None:
        # [Boundary] SUCCESS with total==0 on a scenario run is the false-green
        # signature (everything deselected / nothing generated) → FAILED.
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="All 0 tests passed.",
            exports={"passed": 0, "failed": 0, "errors": 0, "total": 0},
        )
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            result = await handler.execute(step, _ctx(tmp_path))

        assert result.status == StepStatus.FAILED
        assert "no scenario tests" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_scenario_failures_stay_failed_with_exports(self, tmp_path: Path) -> None:
        # [Happy-red] genuine failures → FAILED with the QA exports intact.
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.FAILED,
            message="2 failed, 0 errors out of 5 tests.",
            exports={"passed": 3, "failed": 2, "errors": 0, "total": 5, "failures": []},
        )
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            result = await handler.execute(step, _ctx(tmp_path))

        assert result.status == StepStatus.FAILED
        assert result.output["failed"] == 2

    @pytest.mark.asyncio
    async def test_unit_kind_zero_total_still_passes(self, tmp_path: Path) -> None:
        # [Boundary/backward-compat] the atom's pristine-targets SUCCESS
        # (total==0) must stay a PASS for non-scenario kinds.
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="All nodes pristine.",
            exports={"passed": 0, "failed": 0, "errors": 0, "total": 0},
        )
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            result = await handler.execute(
                _step(params={"kind": "unit", "target": "tests"}), _ctx(tmp_path)
            )

        assert result.status == StepStatus.PASSED


# ---------------------------------------------------------------------------
# INT-US-24 SF-01 T3 (FR-2 producer): scenario runs ALWAYS publish the raw QA
# export under the reserved feedback key — pass, fail, and zero-collected —
# so the arbiter judges real evidence (and its absence is a loud wiring bug).
# ---------------------------------------------------------------------------


class TestScenarioEvidencePublication:
    @pytest.mark.asyncio
    async def test_publishes_evidence_on_scenario_pass(self, tmp_path: Path) -> None:
        # [Happy] green run publishes too — the arbiter's no-LLM short-circuit
        # reads failed/errors/total from this payload.
        handler = ValidateTestsHandler()
        exports = {"passed": 4, "failed": 0, "errors": 0, "total": 4, "failures": []}
        mock_result = AtomResult(status=AtomStatus.SUCCESS, message="ok", exports=exports)
        ctx = _ctx(tmp_path)
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            await handler.execute(step, ctx)

        assert ctx.feedback["scenario_test_failures"] == exports

    @pytest.mark.asyncio
    async def test_publishes_evidence_on_scenario_fail(self, tmp_path: Path) -> None:
        # [Happy-red] failure evidence carries the real TestFailure dicts.
        handler = ValidateTestsHandler()
        exports = {
            "passed": 3,
            "failed": 2,
            "errors": 0,
            "total": 5,
            "failures": [
                {"nodeid": "test_x.py::test_a", "message": "boom", "stacktrace": "tb"},
            ],
        }
        mock_result = AtomResult(status=AtomStatus.FAILED, message="2 failed", exports=exports)
        ctx = _ctx(tmp_path)
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            await handler.execute(step, ctx)

        assert ctx.feedback["scenario_test_failures"]["failed"] == 2
        assert ctx.feedback["scenario_test_failures"]["failures"][0]["message"] == "boom"

    @pytest.mark.asyncio
    async def test_publishes_evidence_on_zero_collected(self, tmp_path: Path) -> None:
        # [Boundary] the T1 false-green guard FAILs the step, but the evidence
        # (total==0) must still reach the arbiter so IT also fails loud (E2).
        handler = ValidateTestsHandler()
        exports = {"passed": 0, "failed": 0, "errors": 0, "total": 0}
        mock_result = AtomResult(status=AtomStatus.SUCCESS, message="0 tests", exports=exports)
        ctx = _ctx(tmp_path)
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            result = await handler.execute(step, ctx)

        assert result.status == StepStatus.FAILED
        assert ctx.feedback["scenario_test_failures"]["total"] == 0

    @pytest.mark.asyncio
    async def test_timeout_shape_fails_and_publishes_empty_evidence(self, tmp_path: Path) -> None:
        # [Graceful degradation] G-a: QA atom timeout returns FAILED with
        # exports={} — the step must FAIL and still publish the (empty)
        # evidence so the arbiter fails loud instead of ERRORing on absence.
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.FAILED, message="Process timed out: 120s", exports={}
        )
        ctx = _ctx(tmp_path)
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            step = _step(params={"kind": "scenario", "target": "scenarios/generated/test_x.py"})
            result = await handler.execute(step, ctx)

        assert result.status == StepStatus.FAILED
        assert ctx.feedback["scenario_test_failures"] == {}

    @pytest.mark.asyncio
    async def test_non_scenario_kinds_never_touch_feedback(self, tmp_path: Path) -> None:
        # [Boundary/backward-compat] unit/integration/e2e runs must not pollute
        # the feedback dict — the reserved key is scenario-exclusive.
        handler = ValidateTestsHandler()
        mock_result = AtomResult(
            status=AtomStatus.FAILED,
            message="1 failed",
            exports={"passed": 0, "failed": 1, "errors": 0, "total": 1, "failures": []},
        )
        ctx = _ctx(tmp_path)
        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            await handler.execute(_step(params={"kind": "unit", "target": "tests"}), ctx)

        assert ctx.feedback == {}
