# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests for the planning feature (Feature 3.6a).

E1: Pipeline with plan_spec step validates via validate_flow().
E2: Full pipeline: spec → validate → plan → generate (mock LLM, real runner).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.flow.models import (
    GateCondition,
    GateDefinition,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.flow.state import StepStatus

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# E1: Pipeline with plan_spec step validates via validate_flow()
# ---------------------------------------------------------------------------


class TestPlanSpecPipelineValidation:
    """E1: A pipeline containing plan+spec passes validate_flow."""

    def test_plan_spec_pipeline_validates(self) -> None:
        """Pipeline with draft → validate → plan → generate validates cleanly."""
        steps = [
            PipelineStep(
                name="draft_spec",
                action=StepAction.DRAFT,
                target=StepTarget.SPEC,
            ),
            PipelineStep(
                name="validate_spec",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                gate=GateDefinition(
                    condition=GateCondition.ALL_PASSED,
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="draft_spec",
                ),
            ),
            PipelineStep(
                name="plan_spec",
                action=StepAction.PLAN,
                target=StepTarget.SPEC,
            ),
            PipelineStep(
                name="generate_code",
                action=StepAction.GENERATE,
                target=StepTarget.CODE,
            ),
        ]
        pipeline = PipelineDefinition(name="feature_with_plan", steps=steps)
        errors = pipeline.validate_flow()
        assert errors == []


# ---------------------------------------------------------------------------
# E2: Full pipeline: spec → validate → plan → generate (mock LLM, real runner)
# ---------------------------------------------------------------------------


@dataclass
class _FakeResponse:
    text: str


class FakeLLM:
    """Fake LLM that returns pre-configured responses per call."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._idx = 0

    async def generate(self, messages: Any, config: Any = None) -> _FakeResponse:
        idx = min(self._idx, len(self._responses) - 1)
        self._idx += 1
        return _FakeResponse(text=self._responses[idx])


class TestFullPlanPipelineE2E:
    """E2: Full pipeline with mock LLM exercises spec→validate→plan→generate."""

    @pytest.mark.asyncio()
    async def test_spec_validate_plan_generate(self, tmp_path: Path) -> None:
        """Full pipeline: spec exists → validate → plan → generate code (mock LLM)."""
        from specweaver.flow.handlers import (
            GenerateCodeHandler,
            PlanSpecHandler,
            RunContext,
            ValidateSpecHandler,
        )

        # 1. Create a valid spec
        spec = tmp_path / "login_spec.md"
        spec.write_text(
            "# Login Component\n\n"
            "## 1. Purpose\n\n"
            "Users must be able to log in with email and password.\n"
            "The system authenticates credentials against the user store.\n",
            encoding="utf-8",
        )

        # 2. Validate spec (real validator, no LLM needed)
        ctx_validate = RunContext(project_path=tmp_path, spec_path=spec)
        step_validate = PipelineStep(
            name="validate_spec",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
        )
        validate_result = await ValidateSpecHandler().execute(step_validate, ctx_validate)
        # Spec might fail some rules but shouldn't error
        assert validate_result.status in (StepStatus.PASSED, StepStatus.FAILED)

        # 3. Plan spec (mock LLM returns valid plan JSON)
        plan_json = json.dumps({
            "spec_path": str(spec),
            "spec_name": "Login",
            "spec_hash": "auto",
            "timestamp": "2026-03-22T12:00:00Z",
            "file_layout": [
                {"path": "src/auth/login.py", "action": "create", "purpose": "Login handler"},
                {"path": "tests/test_login.py", "action": "create", "purpose": "Login tests"},
            ],
            "architecture": {
                "module_layout": "auth/ service module",
                "dependency_direction": "downward",
                "archetype": "adapter",
            },
            "reasoning": "Standard adapter pattern for auth.",
            "confidence": 85,
        })
        plan_llm = FakeLLM([plan_json])

        ctx_plan = RunContext(project_path=tmp_path, spec_path=spec, llm=plan_llm)
        step_plan = PipelineStep(
            name="plan_spec",
            action=StepAction.PLAN,
            target=StepTarget.SPEC,
        )
        plan_result = await PlanSpecHandler().execute(step_plan, ctx_plan)
        assert plan_result.status == StepStatus.PASSED
        assert plan_result.output["confidence"] == 85
        assert plan_result.output["file_count"] == 2

        # 4. Load the plan YAML and verify it's valid
        from ruamel.yaml import YAML

        from specweaver.planning.models import PlanArtifact

        plan_yaml_path = tmp_path / "login_spec_plan.yaml"
        assert plan_yaml_path.exists()
        loaded_plan = PlanArtifact.model_validate(
            YAML().load(plan_yaml_path.read_text(encoding="utf-8")),
        )
        plan_text = loaded_plan.model_dump_json()

        # 5. Generate code (mock LLM, plan injected via context)
        from unittest.mock import AsyncMock, MagicMock

        gen_llm = MagicMock()
        gen_llm.generate = AsyncMock(
            return_value=MagicMock(
                text="class LoginHandler:\n    pass\n",
                finish_reason=1, parsed=None,
            ),
        )
        src_dir = tmp_path / "src"
        src_dir.mkdir(exist_ok=True)

        ctx_generate = RunContext(
            project_path=tmp_path, spec_path=spec,
            output_dir=src_dir, llm=gen_llm,
            plan=plan_text,
        )
        step_generate = PipelineStep(
            name="generate_code",
            action=StepAction.GENERATE,
            target=StepTarget.CODE,
        )
        gen_result = await GenerateCodeHandler().execute(step_generate, ctx_generate)
        assert gen_result.status == StepStatus.PASSED
        assert "generated_path" in gen_result.output

        # Verify plan was injected into the LLM prompt
        prompt = gen_llm.generate.call_args[0][0][-1].content
        assert "<plan>" in prompt
