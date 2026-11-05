# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which model roles a pipeline needs, so a run can check them all before its first step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.flow.engine.models import ROLE_OF_STEP, SIDE_RUNNING_STEPS
from specweaver.core.flow.handlers.dual_pipeline import dual_side_pipelines

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.infrastructure.llm.models import TaskType


def roles_of(pipeline: PipelineDefinition) -> list[TaskType]:
    """The roles a pipeline's steps use, in first-use order, each once."""
    roles: list[TaskType] = []
    for step in pipeline.steps:
        role = ROLE_OF_STEP.get((step.action, step.target))
        if role is not None and role not in roles:
            roles.append(role)
        if (step.action, step.target) in SIDE_RUNNING_STEPS:
            # A dual run's two sides call models too; a missing one must stop the run now.
            for side in dual_side_pipelines():
                roles.extend(r for r in roles_of(side) if r not in roles)
    return roles
