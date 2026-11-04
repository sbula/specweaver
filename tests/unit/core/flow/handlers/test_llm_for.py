# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every pipeline step reaches its model through the run's router, and nothing else.

Proves: C-FLOW-13 FR-10, FR-11, TECH-082 FR-9

| Bucket | Case |
|---|---|
| Happy | a step's role comes back with the run id and task type stamped on its settings |
| Boundary | the router's settings are copied, never changed in place |
| Degradation | a run without resolved LLM settings refuses the step, naming why |
| Hostile | not applicable — task types are a closed enum |
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from specweaver.core.flow.handlers._llm import LlmNotConfiguredError, llm_for
from specweaver.infrastructure.llm.models import GenerationConfig, TaskType
from specweaver.infrastructure.llm.router import RouterResult


class _Router:
    def __init__(self) -> None:
        self.config = GenerationConfig(
            model="qwen3-coder-next", temperature=1.0, max_output_tokens=1000
        )
        self.asked: list[TaskType] = []

    def get_for_task(self, task_type: TaskType) -> RouterResult:
        self.asked.append(task_type)
        return RouterResult(adapter="the-adapter", config=self.config)


def _context(router: object | None) -> SimpleNamespace:
    return SimpleNamespace(
        model=SimpleNamespace(llm_router=router), run=SimpleNamespace(run_id="run-7")
    )


def test_a_step_gets_its_roles_model_stamped_with_the_run() -> None:
    router = _Router()

    adapter, config = llm_for(_context(router), TaskType.REVIEW)

    assert adapter == "the-adapter"
    assert router.asked == [TaskType.REVIEW]
    assert (config.model, config.temperature) == ("qwen3-coder-next", 1.0)
    assert (config.task_type, config.run_id) == (TaskType.REVIEW, "run-7")
    assert router.config.task_type == TaskType.UNKNOWN  # the router's copy is untouched


def test_a_run_without_llm_settings_refuses_the_step() -> None:
    with pytest.raises(LlmNotConfiguredError, match="settings"):
        llm_for(_context(None), TaskType.DRAFT)


def test_a_step_asks_for_the_role_the_step_table_gives_it() -> None:
    """TECH-082 FR-9: the role comes from the step, not from the handler."""
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers._llm import llm_for_step

    router = _Router()
    step = PipelineStep(name="fix", action="lint_fix", target="code")

    _adapter, config = llm_for_step(_context(router), step)

    assert router.asked == [TaskType.CHECK]
    assert config.task_type == TaskType.CHECK


def test_a_step_with_no_role_is_refused_by_name() -> None:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers._llm import llm_for_step

    router = _Router()
    step = PipelineStep(name="check_it", action="validate", target="code")

    with pytest.raises(ValueError, match="check_it"):
        llm_for_step(_context(router), step)
    assert router.asked == []


def test_a_pipeline_names_the_roles_its_steps_use() -> None:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.handlers._llm import roles_of

    pipeline = PipelineDefinition.model_validate(
        {
            "name": "p",
            "steps": [
                {"name": "a", "action": "draft", "target": "spec"},
                {"name": "b", "action": "validate", "target": "spec"},
                {"name": "c", "action": "review", "target": "code"},
                {"name": "d", "action": "lint_fix", "target": "code"},
            ],
        }
    )

    assert roles_of(pipeline) == [TaskType.DRAFT, TaskType.REVIEW, TaskType.CHECK]
