# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run's language: the one named, else the one the project's manifests show.

The task-file code takes the language as given; callers that may not import `sandbox` (the API,
the `sw implement` CLI) ask here and get the flow handlers' answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workflows.implementation.task_files import TaskFiles, task_files_for

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.run_state.run_context import RunContext


def run_language(project_root: Path, language: str | None) -> str:
    """`language` when named, else the one `detect_language` finds in `project_root`."""
    from specweaver.sandbox.language.core.detect import detect_language

    return language or detect_language(project_root)


def run_task_files(context: RunContext) -> TaskFiles:
    """The files the run's task writes, in the run's language."""
    root = context.project_path
    return task_files_for(root, context.spec_path, run_language(root, context.isolation.language))
