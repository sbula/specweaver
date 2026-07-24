# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-24 SF-01 T5: scenario_integration.yaml through the REAL handler registry.

Unlike the legacy sequencing test (which mocks every handler), this drives the
real OrchestrateComponentsHandler → ArbitrateDualPipelineHandler dispatch, the
real ValidateTestsHandler evidence publication, and the real ArbitrateVerdictHandler
consumption. Only the leaf edges are scripted: the dual sub-runners (via the
`_build_runner` seam — NOT PipelineRunner globally, which would stub the outer
runner too), the QA atom, and the LLM adapter.
"""

from __future__ import annotations

import importlib.resources
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.sandbox.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

SPEC = '''# Greet Service Spec

## Contract

```python
def greet(name: str) -> str:
    """Return a greeting for the given name."""
```

## Scenarios

```yaml
scenarios:
  - id: S1
    req_id: FR-1
```
'''


def _load_pipeline() -> PipelineDefinition:
    text = (
        importlib.resources.files("specweaver.workflows.pipelines") / "scenario_integration.yaml"
    ).read_text("utf-8")
    return PipelineDefinition(**yaml.safe_load(text))


def _ctx(tmp_path: Path) -> RunContext:
    project = tmp_path / "project"
    (project / "specs").mkdir(parents=True)
    spec_path = project / "specs" / "greet_spec.md"
    spec_path.write_text(SPEC, encoding="utf-8")
    ctx = RunContext(project_path=project, spec_path=spec_path)
    ctx.llm = AsyncMock()
    return ctx


def _sub_run_ok() -> MagicMock:
    return MagicMock(status=StepStatus.PASSED)


def _qa(passed: int, failed: int, errors: int, total: int, failures: list) -> AtomResult:
    status = AtomStatus.FAILED if (failed or errors) else AtomStatus.SUCCESS
    return AtomResult(
        status=status,
        message=f"{failed} failed, {errors} errors out of {total} tests.",
        exports={
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total": total,
            "failures": failures,
        },
    )


@pytest.mark.asyncio
async def test_green_path_completes_with_zero_llm_calls(tmp_path: Path) -> None:
    # [Happy] contract → dual dispatch → scenario tests green → arbiter
    # short-circuits → COMPLETED. The LLM is never consulted.
    ctx = _ctx(tmp_path)
    runner = PipelineRunner(pipeline=_load_pipeline(), context=ctx)

    stub_runner = MagicMock()
    stub_runner.run = AsyncMock(return_value=_sub_run_ok())
    mock_atom = MagicMock()
    mock_atom.run.return_value = _qa(passed=3, failed=0, errors=0, total=3, failures=[])

    with (
        patch(
            "specweaver.core.flow.handlers.dual_pipeline.ArbitrateDualPipelineHandler._build_runner",
            return_value=stub_runner,
        ),
        patch(
            "specweaver.core.flow.handlers.validation.ValidateTestsHandler._get_atom",
            return_value=mock_atom,
        ),
    ):
        result = await runner.run()

    assert result.status == RunStatus.COMPLETED
    ctx.llm.generate.assert_not_called()
    # Both sub-pipelines were fanned out through the real dispatch chain.
    assert stub_runner.run.await_count == 2
    # Terminal green verdict consumed the evidence.
    assert "scenario_test_failures" not in ctx.feedback


@pytest.mark.asyncio
async def test_red_path_arbitrates_with_real_evidence_and_loops_back(tmp_path: Path) -> None:
    # [Happy-red] first round fails → arbiter reads the REAL published QA
    # evidence, verdicts code_bug (vocabulary-guarded feedback for the coding
    # side), loop_back re-runs the dual step; second round green → COMPLETED.
    ctx = _ctx(tmp_path)
    runner = PipelineRunner(pipeline=_load_pipeline(), context=ctx)

    stub_runner = MagicMock()
    stub_runner.run = AsyncMock(return_value=_sub_run_ok())
    mock_atom = MagicMock()
    mock_atom.run.side_effect = [
        _qa(
            passed=2,
            failed=1,
            errors=0,
            total=3,
            failures=[
                {
                    "nodeid": "test_greet_scenarios.py::test_greet_happy",
                    "message": "AssertionError: expected 'Hello Bob' got 'Bob'",
                    "stacktrace": "traceback-frames",
                }
            ],
        ),
        _qa(passed=3, failed=0, errors=0, total=3, failures=[]),
    ]
    ctx.llm.generate.return_value = (
        '{"verdict": "code_bug", "spec_clause": "FR-1", '
        '"coding_feedback": "The greeting must include the salutation required by FR-1."}'
    )

    with (
        patch(
            "specweaver.core.flow.handlers.dual_pipeline.ArbitrateDualPipelineHandler._build_runner",
            return_value=stub_runner,
        ),
        patch(
            "specweaver.core.flow.handlers.validation.ValidateTestsHandler._get_atom",
            return_value=mock_atom,
        ),
    ):
        result = await runner.run()

    assert result.status == RunStatus.COMPLETED
    # Exactly one arbitration LLM call (round 1); round 2 short-circuited green.
    assert ctx.llm.generate.await_count == 1
    # loop_back re-ran the dual step: 2 sub-runs per round x 2 rounds.
    assert stub_runner.run.await_count == 4
    # The coding-side feedback was routed and is scenario-vocabulary-free.
    coding = ctx.feedback["generate_code"]["findings"]["results"][0]["message"]
    assert "scenario" not in coding.lower()
    assert "FR-1" in ctx.feedback["generate_code"]["findings"]["results"][0]["rule_id"]
