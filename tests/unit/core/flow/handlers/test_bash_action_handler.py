# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for BashActionHandler — runs a bash script via BashActionAtom."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.bash_action import BashActionHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.sandbox.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")


def _step(**kwargs) -> PipelineStep:
    defaults = {"name": "run_script", "action": StepAction.BASH, "target": StepTarget.SCRIPT}
    defaults.update(kwargs)
    return PipelineStep(**defaults)


class TestBashActionHandler:
    """Tests for the BashActionHandler."""

    @pytest.mark.asyncio
    async def test_success_maps_to_passed(self, tmp_path: Path) -> None:
        handler = BashActionHandler()
        mock_result = AtomResult(
            status=AtomStatus.SUCCESS,
            message="bash script 'x.sh' exited 0.",
            exports={"exit_code": 0, "stdout": "hi\n", "stderr": "", "duration_seconds": 0.1},
        )

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            result = await handler.execute(_step(params={"script": "x.sh"}), _ctx(tmp_path))

        assert result.status == StepStatus.PASSED
        assert result.output == mock_result.exports
        assert result.output["stdout"] == "hi\n"

    @pytest.mark.asyncio
    async def test_failure_maps_to_failed(self, tmp_path: Path) -> None:
        handler = BashActionHandler()
        mock_result = AtomResult(
            status=AtomStatus.FAILED,
            message="bash script 'x.sh' exited 3.",
            exports={"exit_code": 3, "stdout": "", "stderr": "boom", "duration_seconds": 0.1},
        )

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            result = await handler.execute(_step(params={"script": "x.sh"}), _ctx(tmp_path))

        assert result.status == StepStatus.FAILED
        assert result.error_message == "bash script 'x.sh' exited 3."
        assert result.output["exit_code"] == 3

    @pytest.mark.asyncio
    async def test_params_passed_through_unchanged(self, tmp_path: Path) -> None:
        handler = BashActionHandler()
        mock_result = AtomResult(status=AtomStatus.SUCCESS, message="ok", exports={})
        params = {
            "script": "x.sh",
            "args": ["a", "b"],
            "working_dir": "sub",
            "timeout_seconds": 30,
            "env": {"K": "V"},
        }

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            await handler.execute(_step(params=params), _ctx(tmp_path))

        mock_get.return_value.run.assert_called_once_with(params)

    @pytest.mark.asyncio
    async def test_missing_params_key_not_defaulted_by_handler(self, tmp_path: Path) -> None:
        """The handler must not paper over a missing 'script' key — BashActionAtom
        (SF-1) owns that validation, per Q1's resolved design intent (thin handler)."""
        handler = BashActionHandler()
        mock_result = AtomResult(status=AtomStatus.FAILED, message="Missing 'script'.", exports={})

        with patch.object(handler, "_get_atom", return_value=MagicMock()) as mock_get:
            mock_get.return_value.run.return_value = mock_result
            result = await handler.execute(_step(params={}), _ctx(tmp_path))

        mock_get.return_value.run.assert_called_once_with({})
        assert result.status == StepStatus.FAILED


class TestBashActionRegistration:
    """Direct unit assertion that registry.py's dict entry resolves correctly
    (Pre-Commit Phase 2 gap — the wiring was previously proven only implicitly
    via the integration tests using a real StepHandlerRegistry)."""

    def test_registry_resolves_bash_script_to_handler(self) -> None:
        handler = StepHandlerRegistry().get(StepAction.BASH, StepTarget.SCRIPT)
        assert isinstance(handler, BashActionHandler)
