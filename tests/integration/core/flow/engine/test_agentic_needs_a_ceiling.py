# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run that would go agentic with no ceiling set is refused before any step runs.

Proves: C-FLOW-11 FR-2
Proves: C-FLOW-11 NFR-1
Proves: C-FLOW-11 NFR-2

The real runner over real `bash` steps; the refused step is never reached, so no model is needed.

| Bucket | Case |
|---|---|
| Happy | a ceiling set: the run starts |
| Boundary | the project's own `mode = "agentic"` with no ceiling refuses too; with no generate step at all, it does not |
| Degradation | not applicable — the check reads the policy and the pipeline only |
| Hostile | `mode: agentic` on a generate step, no ceiling: refused, naming `[autonomy] agentic_max_dal`, and the bash step before it never ran |
"""

from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.autonomy_policy import AutonomyPolicy
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

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("bash") is None, reason="bash required"),
]


def _bash() -> PipelineStep:
    return PipelineStep(
        name="first", action=StepAction.BASH, target=StepTarget.SCRIPT, params={"script": "s.sh"}
    )


def _generate(mode: str | None) -> PipelineStep:
    return PipelineStep(name="code", action=StepAction.GENERATE, target=StepTarget.CODE, mode=mode)


def _run(root: Path, steps: list[PipelineStep], **policy: Any):
    scripts = root / ".specweaver" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "s.sh").write_text("echo ran >> steps.log\n", encoding="utf-8")
    context = RunContext(
        project_path=root, spec_path=root / "spec.md", model=ModelAccess(config=MagicMock())
    )
    context.isolation = context.isolation.model_copy(
        update={"autonomy": AutonomyPolicy(**policy), "dal_level": DALLevel.DAL_E}
    )
    runner = PipelineRunner(
        PipelineDefinition(name="p", steps=steps), context, registry=StepHandlerRegistry()
    )
    return asyncio.run(runner.run())


def test_an_agentic_step_without_a_ceiling_refuses_the_run(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\[autonomy\] agentic_max_dal") as caught:
        _run(tmp_path, [_bash(), _generate("agentic")])

    assert "code" in str(caught.value)
    assert not (tmp_path / "steps.log").exists()


def test_the_projects_agentic_default_without_a_ceiling_refuses_too(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="agentic_max_dal"):
        _run(tmp_path, [_bash(), _generate(None)], mode="agentic")


def test_a_project_default_with_no_generate_step_runs(tmp_path: Path) -> None:
    run = _run(tmp_path, [_bash()], mode="agentic")

    assert run.status == RunStatus.COMPLETED


def test_no_agentic_anywhere_runs_as_before(tmp_path: Path) -> None:
    run = _run(tmp_path, [_bash()])

    assert run.status == RunStatus.COMPLETED
    assert (tmp_path / "steps.log").read_text(encoding="utf-8") == "ran\n"


def test_a_ceiling_lets_the_run_start(tmp_path: Path) -> None:
    """The control: the refusal is about the missing ceiling, not about agentic itself."""
    run = _run(tmp_path, [_bash(), _generate("oneshot")], mode="agentic", agentic_max_dal="DAL_D")

    assert (tmp_path / "steps.log").exists()
    assert run.step_records[0].result is not None
