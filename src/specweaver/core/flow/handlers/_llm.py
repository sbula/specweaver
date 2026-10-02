# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How a pipeline step reaches its model: through the run's router. Nothing else.

The router is fed by the LLM settings files, so a step never picks a model or builds an
adapter itself, and there is no fallback model here: the `default` role in the settings file is
the one fallback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.models import StepAction, StepTarget
from specweaver.infrastructure.llm.models import TaskType

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.infrastructure.llm.models import GenerationConfig

#: The role each model-calling step uses. A run resolves every role its steps need before the first
#: call, so an unset role refuses at the start, not halfway through a paid run.
ROLE_OF_STEP: dict[tuple[StepAction, StepTarget], TaskType] = {
    (StepAction.DRAFT, StepTarget.SPEC): TaskType.DRAFT,
    (StepAction.DRAFT, StepTarget.FEATURE): TaskType.DRAFT,
    (StepAction.REVIEW, StepTarget.SPEC): TaskType.REVIEW,
    (StepAction.REVIEW, StepTarget.CODE): TaskType.REVIEW,
    (StepAction.ARBITRATE, StepTarget.VERDICT): TaskType.REVIEW,
    (StepAction.DETECT, StepTarget.DRIFT): TaskType.REVIEW,
    (StepAction.GENERATE, StepTarget.CODE): TaskType.IMPLEMENT,
    (StepAction.GENERATE, StepTarget.TESTS): TaskType.IMPLEMENT,
    (StepAction.GENERATE, StepTarget.SCENARIO): TaskType.IMPLEMENT,
    (StepAction.PLAN, StepTarget.SPEC): TaskType.PLAN,
    (StepAction.DECOMPOSE, StepTarget.FEATURE): TaskType.PLAN,
    (StepAction.LINT_FIX, StepTarget.CODE): TaskType.CHECK,
    (StepAction.ENRICH, StepTarget.STANDARDS): TaskType.CHECK,
}


class LlmNotConfiguredError(RuntimeError):
    """The run has no resolved LLM settings, so no step may call a model."""


def llm_for(context: RunContext, task_type: TaskType) -> tuple[Any, GenerationConfig]:
    """The adapter and settings for this step's role, stamped with the run and the task type."""
    router = context.model.llm_router
    if router is None:
        msg = "no LLM settings were resolved for this run — check `sw config show`"
        raise LlmNotConfiguredError(msg)
    routed = router.get_for_task(task_type)
    config = routed.config.model_copy(
        update={"task_type": task_type, "run_id": context.run.run_id or ""}
    )
    return routed.adapter, config


def roles_of(pipeline: PipelineDefinition) -> list[TaskType]:
    """The roles a pipeline's steps use, in first-use order, each once."""
    roles: list[TaskType] = []
    for step in pipeline.steps:
        role = ROLE_OF_STEP.get((step.action, step.target))
        if role is not None and role not in roles:
            roles.append(role)
    return roles
