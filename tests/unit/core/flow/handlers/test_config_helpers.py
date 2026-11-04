# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for flow config helpers — task_type wiring (stories 6-9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.run_state.run_context import ModelAccess, RunContext
from tests.scripted_llm import FixedRouter


def _make_context(*, with_config: bool = True) -> RunContext:
    """Build a RunContext with or without a config object."""
    config = MagicMock() if with_config else None
    return RunContext(
        model=ModelAccess(config=config, llm_router=FixedRouter(MagicMock())),
        project_path=Path("/tmp/fake-project"),
        spec_path=Path("/tmp/fake-project/spec.md"),
    )


def _step(action: StepAction, target: StepTarget) -> PipelineStep:
    """The step a helper reads its role from (TECH-082 FR-9)."""
    return PipelineStep(name="s", action=action, target=target)


_REVIEW = _step(StepAction.REVIEW, StepTarget.SPEC)
_CODE = _step(StepAction.GENERATE, StepTarget.CODE)
_PLAN = _step(StepAction.PLAN, StepTarget.SPEC)


class TestReviewConfigTaskType:
    """_resolve_review_routing sets task_type=REVIEW (story 6)."""

    def test_review_config_sets_review_task_type(self):
        from specweaver.core.flow.handlers.review import _resolve_review_routing

        context = _make_context()
        _adapter, config = _resolve_review_routing(context, _REVIEW)
        assert config.task_type == "review"

    def test_review_config_fallback_also_sets_review(self):
        """Fallback path (context.model.config=None) also sets task_type=REVIEW."""
        from specweaver.core.flow.handlers.review import _resolve_review_routing

        context = _make_context(with_config=False)
        _adapter, config = _resolve_review_routing(context, _REVIEW)
        assert config.task_type == "review"


class TestGenConfigTaskType:
    """_resolve_generation_routing task_type behavior (stories 7-8)."""

    def test_default_task_type_is_implement(self):
        """No explicit task_type → IMPLEMENT, from the run's router (story 7)."""
        from specweaver.core.flow.handlers.generation import _resolve_generation_routing

        context = _make_context()
        adapter, config = _resolve_generation_routing(context, _CODE)
        assert config.task_type == "implement"
        assert adapter is context.model.llm_router.adapter

    def test_a_scenario_step_gets_the_scenario_role(self):
        """The role follows the step, not the helper (TECH-082 FR-9)."""
        from specweaver.core.flow.handlers.generation import _resolve_generation_routing

        context = _make_context()
        _adapter, config = _resolve_generation_routing(
            context, _step(StepAction.GENERATE, StepTarget.SCENARIO)
        )
        assert config.task_type == "scenario"

    def test_a_step_with_no_role_raises(self):
        """A step the table gives no role never gets a model (TECH-082 FR-9)."""
        import pytest

        from specweaver.core.flow.handlers.generation import _resolve_generation_routing

        with pytest.raises(ValueError, match=r"generate\+contract"):
            _resolve_generation_routing(
                _make_context(), _step(StepAction.GENERATE, StepTarget.CONTRACT)
            )

    def test_without_a_router_the_step_refuses(self):
        """No resolved LLM settings → no model is guessed: the step refuses."""
        import pytest

        from specweaver.core.flow.handlers._llm import LlmNotConfiguredError
        from specweaver.core.flow.handlers.generation import _resolve_generation_routing

        context = _make_context()
        context.model = context.model.model_copy(update={"llm_router": None})
        with pytest.raises(LlmNotConfiguredError):
            _resolve_generation_routing(context, _CODE)


class TestPlanSpecConfigTaskType:
    """PlanSpecHandler._resolve_routing uses task_type=PLAN (story 9)."""

    def test_plan_config_sets_plan_task_type(self):
        from specweaver.core.flow.handlers.generation import PlanSpecHandler

        handler = PlanSpecHandler()
        context = _make_context()
        _adapter, config = handler._resolve_routing(context, _PLAN)
        assert config.task_type == "plan"

    def test_plan_config_fallback_sets_plan(self):
        """Fallback path (context.model.config=None) also sets task_type=PLAN."""
        from specweaver.core.flow.handlers.generation import PlanSpecHandler

        handler = PlanSpecHandler()
        context = _make_context(with_config=False)
        _adapter, config = handler._resolve_routing(context, _PLAN)
        assert config.task_type == "plan"
