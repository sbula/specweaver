# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How a pipeline step reaches its model: through the run's router. Nothing else.

The router is fed by the LLM settings files, so a step never picks a model or builds an
adapter itself, and there is no fallback model here: the `default` role in the settings file is
the one fallback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.models import ROLE_OF_STEP

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition, PipelineStep
    from specweaver.core.flow.run_state.run_context import RunContext
    from specweaver.infrastructure.llm.models import GenerationConfig, TaskType


class LlmNotConfiguredError(RuntimeError):
    """The run has no resolved LLM settings, so no step may call a model."""


def llm_for(context: RunContext, task_type: TaskType) -> tuple[Any, GenerationConfig]:
    """The adapter and settings for this step's role, stamped with the run and the task type."""
    router = context.model.llm_router
    if router is None:
        msg = "no LLM settings were resolved for this run — check `sw config show`"
        raise LlmNotConfiguredError(msg)
    routed = router.get_for_task(task_type)
    dal = getattr(getattr(context, "isolation", None), "dal_level", None)
    config = routed.config.model_copy(
        update={
            "task_type": task_type,
            "run_id": context.run.run_id or "",
            "dal_level": str(dal) if dal is not None else "",
            "step_name": getattr(context.run, "step_name", None) or "",
        }
    )
    return routed.adapter, config


def llm_for_step(context: RunContext, step: PipelineStep) -> tuple[Any, GenerationConfig]:
    """The adapter and settings for the role the step table gives this step."""
    role = ROLE_OF_STEP.get((step.action, step.target))
    if role is None:
        msg = f"step '{step.name}' ({step.action}+{step.target}) calls no model in the step table"
        raise ValueError(msg)
    return llm_for(context, role)


def roles_of(pipeline: PipelineDefinition) -> list[TaskType]:
    """The roles a pipeline's steps use, in first-use order, each once."""
    roles: list[TaskType] = []
    for step in pipeline.steps:
        role = ROLE_OF_STEP.get((step.action, step.target))
        if role is not None and role not in roles:
            roles.append(role)
        if step.params.get("mode") == "dual_pipeline":
            # A dual run's two sides call models too; a missing one must stop the run now.
            from specweaver.core.flow.handlers.dual_pipeline import dual_side_pipelines

            for side in dual_side_pipelines():
                roles.extend(r for r in roles_of(side) if r not in roles)
    return roles
