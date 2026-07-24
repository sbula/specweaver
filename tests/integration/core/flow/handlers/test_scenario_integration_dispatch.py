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


# ---------------------------------------------------------------------------
# INT-US-24 SF-02 T3: seam-chain pins — the arbiter's verdict feedback reaches
# the REAL regeneration handlers, opaque on the coding side (FR-6) and
# delta-carrying on the scenario side (FR-4).
# ---------------------------------------------------------------------------

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget  # noqa: E402
from specweaver.core.flow.handlers.arbiter import (  # noqa: E402
    SCENARIO_VOCABULARY,
    ArbitrateVerdictHandler,
)


def _evidence_with_failure() -> dict:
    return {
        "passed": 2,
        "failed": 1,
        "errors": 0,
        "total": 3,
        "failures": [
            {
                "nodeid": "test_greet_scenarios.py::test_greet_happy",
                "message": "AssertionError: greeting mismatch",
                "stacktrace": "tb",
            }
        ],
    }


@pytest.mark.asyncio
async def test_fr6_leaky_verdict_reaches_code_generator_vocabulary_free(tmp_path: Path) -> None:
    # [Hostile→Happy chain] the LLM's code_bug feedback LEAKS scenario
    # vocabulary → the real guard rewrites it → the REAL GenerateCodeHandler
    # extracts it and hands the Generator a validation_findings text with no
    # scenario vocabulary. Pins NFR-8 on the integrated path, not just the
    # guard's unit tests.
    ctx = _ctx(tmp_path)
    ctx.feedback["scenario_test_failures"] = _evidence_with_failure()
    ctx.llm.generate.return_value = (
        '{"verdict": "code_bug", "spec_clause": "FR-1", '
        '"coding_feedback": "The scenario test failed on pytest parametrize inputs."}'
    )
    arb_step = PipelineStep(
        name="arbitrate_verdict", action=StepAction.ARBITRATE, target=StepTarget.VERDICT
    )
    with patch(
        "specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter"
    ) as mock_filter:
        mock_filter.return_value.filter.return_value = "Filtered"
        arb_result = await ArbitrateVerdictHandler().execute(arb_step, ctx)
    assert arb_result.status.value == "failed"
    assert "generate_code" in ctx.feedback

    # Now the REAL coding handler consumes what the arbiter wrote.
    from specweaver.core.flow.handlers.generation import GenerateCodeHandler

    gen_step = PipelineStep(name="generate_code", action=StepAction.GENERATE, target=StepTarget.CODE)
    with (
        patch("specweaver.workflows.implementation.generator.Generator") as mock_gen_cls,
        patch(
            "specweaver.core.flow.handlers.context_assembler.evaluate_and_fetch_skeleton_context",
            return_value=[],
        ),
        patch(
            "specweaver.core.flow.handlers.mcp_assembler.evaluate_and_fetch_mcp_context",
            return_value=None,
        ),
        patch(
            "specweaver.core.flow.handlers.generation._build_tool_dispatcher",
            return_value=MagicMock(),
        ),
    ):
        mock_gen = mock_gen_cls.return_value
        mock_gen.generate_code = AsyncMock(return_value=tmp_path / "project" / "src" / "greet.py")
        await GenerateCodeHandler().execute(gen_step, ctx)

    assert mock_gen.generate_code.await_count == 1
    findings_text = mock_gen.generate_code.call_args.kwargs["validation_findings"]
    assert findings_text  # the arbiter's verdict DID reach the generator
    lowered = findings_text.lower()
    for banned in SCENARIO_VOCABULARY:
        assert banned.lower() not in lowered, f"vocabulary leak: {banned!r}"
    # Consumed once: the key is gone after extraction.
    assert "generate_code" not in ctx.feedback


@pytest.mark.asyncio
async def test_fr4_scenario_error_reaches_scenario_generator_with_delta(tmp_path: Path) -> None:
    # [Happy chain] arbiter scenario_error → REAL GenerateScenarioHandler →
    # ScenarioGenerator receives the behavioral delta; key popped.
    ctx = _ctx(tmp_path)
    ctx.feedback["scenario_test_failures"] = _evidence_with_failure()
    ctx.llm.generate.return_value = (
        '{"verdict": "scenario_error", "spec_clause": "FR-1", '
        '"scenario_feedback": "Expected greeting includes the salutation per FR-1."}'
    )
    arb_step = PipelineStep(
        name="arbitrate_verdict", action=StepAction.ARBITRATE, target=StepTarget.VERDICT
    )
    with patch(
        "specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter"
    ) as mock_filter:
        mock_filter.return_value.filter.return_value = "Filtered"
        arb_result = await ArbitrateVerdictHandler().execute(arb_step, ctx)
    assert arb_result.status.value == "failed"
    assert "generate_scenarios" in ctx.feedback

    from specweaver.core.flow.handlers.scenario import GenerateScenarioHandler

    scen_step = PipelineStep(
        name="generate_scenarios", action=StepAction.GENERATE, target=StepTarget.SCENARIO
    )
    scenario_set = MagicMock()
    scenario_set.scenarios = []
    scenario_set.model_dump.return_value = {"scenarios": []}
    with patch(
        "specweaver.workflows.scenarios.scenario_generator.ScenarioGenerator"
    ) as mock_sg_cls:
        mock_sg_cls._extract_req_ids.return_value = ["FR-1"]
        mock_sg = mock_sg_cls.return_value
        mock_sg.generate_scenarios = AsyncMock(return_value=scenario_set)
        result = await GenerateScenarioHandler().execute(scen_step, ctx)

    assert result.status.value == "passed"
    fb = mock_sg.generate_scenarios.call_args.kwargs["feedback"]
    assert "[FR-1]" in fb
    assert "Expected greeting includes the salutation" in fb
    assert "generate_scenarios" not in ctx.feedback


def test_yaml_step_name_contract_for_verdict_feedback_keys() -> None:
    # [Boundary] the arbiter writes the FIXED keys generate_code /
    # generate_scenarios — the bundled pipelines must name their steps exactly
    # so, or verdict feedback is silently stranded.
    pkg = importlib.resources.files("specweaver.workflows.pipelines")
    nf = yaml.safe_load((pkg / "new_feature.yaml").read_text("utf-8"))
    sv = yaml.safe_load((pkg / "scenario_validation.yaml").read_text("utf-8"))
    assert any(s.get("name") == "generate_code" for s in nf["steps"])
    assert any(s.get("name") == "generate_scenarios" for s in sv["steps"])
