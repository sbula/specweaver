# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for flow config helpers — task_type wiring (stories 6-9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from tests.scripted_llm import FixedRouter


def _make_context(*, with_config: bool = True) -> RunContext:
    """Build a RunContext with or without a config object."""
    config = MagicMock() if with_config else None
    return RunContext(
        model=ModelAccess(config=config, llm_router=FixedRouter(MagicMock())),
        project_path=Path("/tmp/fake-project"),
        spec_path=Path("/tmp/fake-project/spec.md"),
    )


class TestReviewConfigTaskType:
    """_resolve_review_routing sets task_type=REVIEW (story 6)."""

    def test_review_config_sets_review_task_type(self):
        from specweaver.core.flow.handlers.review import _resolve_review_routing

        context = _make_context()
        _adapter, config = _resolve_review_routing(context)
        assert config.task_type == "review"

    def test_review_config_fallback_also_sets_review(self):
        """Fallback path (context.model.config=None) also sets task_type=REVIEW."""
        from specweaver.core.flow.handlers.review import _resolve_review_routing

        context = _make_context(with_config=False)
        _adapter, config = _resolve_review_routing(context)
        assert config.task_type == "review"


class TestGenConfigTaskType:
    """_resolve_generation_routing task_type behavior (stories 7-8)."""

    def test_default_task_type_is_implement(self):
        """No explicit task_type → IMPLEMENT, from the run's router (story 7)."""
        from specweaver.core.flow.handlers.generation import _resolve_generation_routing

        context = _make_context()
        adapter, config = _resolve_generation_routing(context)
        assert config.task_type == "implement"
        assert adapter is context.model.llm_router.adapter

    def test_explicit_task_type_override(self):
        """Explicit task_type is used instead of default (story 8)."""
        from specweaver.core.flow.handlers.generation import _resolve_generation_routing
        from specweaver.infrastructure.llm.models import TaskType

        context = _make_context()
        _adapter, config = _resolve_generation_routing(context, task_type=TaskType.VALIDATE)
        assert config.task_type == "validate"

    def test_without_a_router_the_step_refuses(self):
        """No resolved LLM settings → no model is guessed: the step refuses."""
        import pytest

        from specweaver.core.flow.handlers._llm import LlmNotConfiguredError
        from specweaver.core.flow.handlers.generation import _resolve_generation_routing

        context = _make_context()
        context.model = context.model.model_copy(update={"llm_router": None})
        with pytest.raises(LlmNotConfiguredError):
            _resolve_generation_routing(context)


class TestPlanSpecConfigTaskType:
    """PlanSpecHandler._resolve_routing uses task_type=PLAN (story 9)."""

    def test_plan_config_sets_plan_task_type(self):
        from specweaver.core.flow.handlers.generation import PlanSpecHandler

        handler = PlanSpecHandler()
        context = _make_context()
        _adapter, config = handler._resolve_routing(context)
        assert config.task_type == "plan"

    def test_plan_config_fallback_sets_plan(self):
        """Fallback path (context.model.config=None) also sets task_type=PLAN."""
        from specweaver.core.flow.handlers.generation import PlanSpecHandler

        handler = PlanSpecHandler()
        context = _make_context(with_config=False)
        _adapter, config = handler._resolve_routing(context)
        assert config.task_type == "plan"
