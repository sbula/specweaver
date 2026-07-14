# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for `action: bash` pipeline steps (C-EXEC-02 SF-2).

Runs BashActionHandler through the real PipelineRunner + StepHandlerRegistry,
executing a real script under `.specweaver/scripts/` — no mocks on the
handler/atom/executor chain.
"""

from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.models import (
    GateDefinition,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    RouterDefinition,
    RouterRule,
    RuleOperator,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, StepHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path

_BASH_UNAVAILABLE = shutil.which("bash") is None
pytestmark = pytest.mark.skipif(_BASH_UNAVAILABLE, reason="bash not on PATH")


def _write_script(tmp_path: Path, name: str, body: str) -> None:
    scripts_dir = tmp_path / ".specweaver" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / name).write_text(body, encoding="utf-8", newline="\n")


def test_bash_step_runs_end_to_end(tmp_path: Path) -> None:
    """A real `action: bash` step executes its script via the real PipelineRunner."""
    _write_script(tmp_path, "hello.sh", "echo hello-from-bash\n")

    pipeline = PipelineDefinition.create_single_step(
        name="run_hello",
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": "hello.sh"},
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    runner = PipelineRunner(pipeline, context, registry=StepHandlerRegistry())

    run_state = asyncio.run(runner.run())

    assert run_state.status == RunStatus.COMPLETED
    record = run_state.step_records[0]
    assert record.status == StepStatus.PASSED
    assert record.result is not None
    assert record.result.output["exit_code"] == 0
    assert "hello-from-bash" in record.result.output["stdout"]


def test_downstream_step_reads_step_records(tmp_path: Path) -> None:
    """A downstream step reads a bash step's output via `context.step_records`."""
    _write_script(tmp_path, "greet.sh", "echo from-bash-step\n")

    class ReadsStepRecordsHandler:
        async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
            import datetime

            assert context.step_records is not None
            bash_record = context.step_records[0]
            stdout = bash_record["result"]["output"]["stdout"]
            return StepResult(
                status=StepStatus.PASSED,
                output={"seen_stdout": stdout},
                started_at=datetime.datetime.now(datetime.UTC).isoformat(),
                completed_at=datetime.datetime.now(datetime.UTC).isoformat(),
            )

    pipeline = PipelineDefinition(
        name="bash_then_read",
        steps=[
            PipelineStep(
                name="run_greet",
                action=StepAction.BASH,
                target=StepTarget.SCRIPT,
                params={"script": "greet.sh"},
            ),
            PipelineStep(
                name="read_records",
                action=StepAction.DRAFT,
                target=StepTarget.SPEC,
            ),
        ],
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, ReadsStepRecordsHandler())
    runner = PipelineRunner(pipeline, context, registry=registry)

    run_state = asyncio.run(runner.run())

    assert run_state.status == RunStatus.COMPLETED
    downstream_record = run_state.step_records[1]
    assert downstream_record.result is not None
    assert "from-bash-step" in downstream_record.result.output["seen_stdout"]


class _FakeHandler(StepHandler):
    """Minimal handler for router-branch targets — no logic under test here."""

    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.call_count += 1
        return StepResult(status=StepStatus.PASSED, output={}, started_at="2026", completed_at="2026")


def _router_step(script_name: str) -> PipelineStep:
    """A bash step routing on `output.exit_code`, tolerant of a nonzero exit."""
    return PipelineStep(
        name="run_script",
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": script_name},
        gate=GateDefinition(on_fail=OnFailAction.CONTINUE),
        router=RouterDefinition(
            rules=[RouterRule(field="exit_code", operator=RuleOperator.EQ, value=0, target="on_success")],
            default_target="on_failure",
        ),
    )


def test_router_branches_on_exit_code(tmp_path: Path) -> None:
    """A bash step's `exit_code == 0` routes to the success branch, skipping failure (FR-7).

    `on_success` is placed last so the router jump proves it *skipped* `on_failure`,
    rather than merely running both sequentially.
    """
    _write_script(tmp_path, "ok.sh", "exit 0\n")

    on_success, on_failure = _FakeHandler(), _FakeHandler()
    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, on_success)
    registry.register(StepAction.REVIEW, StepTarget.SPEC, on_failure)
    pipeline = PipelineDefinition(
        name="bash_router_success",
        steps=[
            _router_step("ok.sh"),
            PipelineStep(name="on_failure", action=StepAction.REVIEW, target=StepTarget.SPEC),
            PipelineStep(name="on_success", action=StepAction.DRAFT, target=StepTarget.SPEC),
        ],
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    runner = PipelineRunner(pipeline, context, registry=registry)

    run_state = asyncio.run(runner.run())

    assert run_state.status == RunStatus.COMPLETED
    assert on_success.call_count == 1
    assert on_failure.call_count == 0
    assert run_state.step_records[1].status == StepStatus.PENDING
    assert run_state.step_records[2].status == StepStatus.PASSED


def test_router_branches_on_nonzero_exit(tmp_path: Path) -> None:
    """A bash step's nonzero exit code fails the rule match and routes to `default_target`,
    skipping the success branch (FR-7)."""
    _write_script(tmp_path, "fail.sh", "exit 7\n")

    on_success, on_failure = _FakeHandler(), _FakeHandler()
    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, on_success)
    registry.register(StepAction.REVIEW, StepTarget.SPEC, on_failure)
    pipeline = PipelineDefinition(
        name="bash_router_failure",
        steps=[
            _router_step("fail.sh"),
            PipelineStep(name="on_success", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(name="on_failure", action=StepAction.REVIEW, target=StepTarget.SPEC),
        ],
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md", config=MagicMock())
    runner = PipelineRunner(pipeline, context, registry=registry)

    run_state = asyncio.run(runner.run())

    assert run_state.status == RunStatus.COMPLETED
    assert on_success.call_count == 0
    assert on_failure.call_count == 1
    assert run_state.step_records[0].status == StepStatus.FAILED
    assert run_state.step_records[1].status == StepStatus.PENDING
    assert run_state.step_records[2].status == StepStatus.PASSED
