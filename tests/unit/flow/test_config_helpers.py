# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for flow config helpers — task_type wiring (stories 6-9)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from specweaver.flow._base import RunContext


def _make_context(*, with_config: bool = True) -> RunContext:
    """Build a RunContext with or without a config object."""
    if with_config:
        config = MagicMock()
        config.llm.model = "gemini-3-flash-preview"
        config.llm.max_output_tokens = 4096
    else:
        config = None
    return RunContext(
        project_path=Path("/tmp/fake-project"),
        spec_path=Path("/tmp/fake-project/spec.md"),
        config=config,
        llm=MagicMock(),
    )


class TestReviewConfigTaskType:
    """_review_config_from_context sets task_type=REVIEW (story 6)."""

    def test_review_config_sets_review_task_type(self):
        from specweaver.flow._review import _review_config_from_context

        context = _make_context()
        config = _review_config_from_context(context)
        assert config.task_type == "review"

    def test_review_config_fallback_also_sets_review(self):
        """Fallback path (context.config=None) also sets task_type=REVIEW."""
        from specweaver.flow._review import _review_config_from_context

        context = _make_context(with_config=False)
        config = _review_config_from_context(context)
        assert config.task_type == "review"


class TestGenConfigTaskType:
    """_gen_config_from_context task_type behavior (stories 7-8)."""

    def test_default_task_type_is_implement(self):
        """No explicit task_type → defaults to IMPLEMENT (story 7)."""
        from specweaver.flow._generation import _gen_config_from_context

        context = _make_context()
        config = _gen_config_from_context(context)
        assert config.task_type == "implement"

    def test_explicit_task_type_override(self):
        """Explicit task_type is used instead of default (story 8)."""
        from specweaver.flow._generation import _gen_config_from_context
        from specweaver.llm.models import TaskType

        context = _make_context()
        config = _gen_config_from_context(context, task_type=TaskType.VALIDATE)
        assert config.task_type == "validate"

    def test_fallback_path_still_sets_task_type(self):
        """Fallback path (context.config=None) still sets task_type."""
        from specweaver.flow._generation import _gen_config_from_context

        context = _make_context(with_config=False)
        config = _gen_config_from_context(context)
        assert config.task_type == "implement"
        assert config.model == "gemini-3-flash-preview"


class TestPlanSpecConfigTaskType:
    """PlanSpecHandler._build_config uses task_type=PLAN (story 9)."""

    def test_plan_config_sets_plan_task_type(self):
        from specweaver.flow._generation import PlanSpecHandler

        handler = PlanSpecHandler()
        context = _make_context()
        config = handler._build_config(context)
        assert config.task_type == "plan"

    def test_plan_config_fallback_sets_plan(self):
        """Fallback path (context.config=None) also sets task_type=PLAN."""
        from specweaver.flow._generation import PlanSpecHandler

        handler = PlanSpecHandler()
        context = _make_context(with_config=False)
        config = handler._build_config(context)
        assert config.task_type == "plan"
