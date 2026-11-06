# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run's profile: its language and build tool, decided once and carried by the run.

The run builder decides it with the `[implement]` pins; every step asks here, so the task files,
the QA runner and the sandbox get one answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.commons.project_profile import ProjectProfile, ProjectUndecidedError
from specweaver.workflows.implementation.task_files import TaskFiles, task_files_for

if TYPE_CHECKING:
    from specweaver.core.flow.run_state.run_context import RunContext


def run_profile(context: RunContext) -> ProjectProfile:
    """The run's profile; raises `ProjectUndecidedError` when the project root decides none.

    A context nobody decided for decides from its project root, with no pins, and keeps it.
    """
    isolation = context.isolation
    if isolation.profile is not None:
        return isolation.profile
    if isolation.undecided is not None:
        raise ProjectUndecidedError(isolation.undecided)
    from specweaver.workspace.project.project_profile import read_project_profile

    profile = read_project_profile(context.project_path)
    context.isolation = isolation.model_copy(update={"profile": profile})
    return profile


def run_task_files(context: RunContext) -> TaskFiles:
    """The files the run's task writes, in the run's language."""
    return task_files_for(context.project_path, context.spec_path, run_profile(context).language)
