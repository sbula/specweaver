# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The lint step stops when the linter did not run, and asks no model to fix it.

Proves: TECH-087 FR-1, FR-4

Path P-1 of the design. Nothing is doubled between the step and the missing engine: the real
`LintFixHandler` builds the real `QARunnerAtom`, whose real Python runner goes through the real
container executor, which finds no Podman or Docker on `PATH`. Only the model is a double, and the
claim is that it is never called: before TECH-087 the step sent the `<toolchain>` error to it.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.core.config.settings import SandboxSettings
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.run_state.run_context import ModelAccess, RunContext
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
def test_a_lint_step_without_a_container_engine_fails_and_calls_no_model(
    sample_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    no_engines = tmp_path / "bin"
    no_engines.mkdir()
    monkeypatch.setenv("PATH", str(no_engines))
    model = MagicMock()
    model.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
    context = RunContext(
        project_path=sample_project,
        spec_path=sample_project / "specs" / "calculator.md",
        model=ModelAccess(
            config=SimpleNamespace(sandbox=SandboxSettings(execution_mode="container")),
            llm_router=FixedRouter(model),
        ),
    )
    step = PipelineStep(
        name="lint_fix",
        action=StepAction.LINT_FIX,
        target=StepTarget.CODE,
        params={"target": "src/greeter/core.py", "max_reflections": 2},
    )

    result = asyncio.run(LintFixHandler().execute(step, context))

    assert result.status == StepStatus.FAILED
    assert "The linter did not run" in result.error_message
    assert "No live container engine" in result.error_message
    assert result.output["reflections_used"] == 0
    model.generate.assert_not_called()
