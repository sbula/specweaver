# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a step works on: its file, the generated code a test run imports, and the scenario mount."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.commons.spec_names import module_stem

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


#: Test-step targets that mean the whole project; only these are narrowed to what changed.
WHOLE_PROJECT = frozenset({".", "", "src", "src/", "tests", "tests/"})


def names_one_file(target: str) -> bool:
    """Whether a test target is one source file, in any language."""
    from specweaver.core.flow.handlers.archetype_pipelines import LANGUAGE_SUFFIXES

    suffix = Path(target).suffix.lower()
    return any(suffix in endings for endings in LANGUAGE_SUFFIXES.values())


def scenarios_root(context: RunContext) -> Path:
    """Where the scenario tests are kept, mounted at `/scenarios` for their run: the project's
    store, outside the project. An unregistered project's dual run has already refused."""
    from specweaver.core.flow.handlers.scenario_store import scenario_store

    return scenario_store(context) or context.project_path / "scenarios"


def in_scenarios_mount(target: str, root: Path) -> str:
    """`target` as the container sees it: under `/scenarios` when it is in the scenario folder."""
    path = Path(target)
    if path.is_absolute() and path.is_relative_to(root):
        return "/scenarios/" + path.relative_to(root).as_posix()
    return target


def requirement_coverage_of(context: RunContext) -> dict[str, str]:
    """Per requirement of the spec, which side's tests cover it; the coder's are the project's."""
    from specweaver.assurance.validation.rules.code.c09_traceability import requirement_coverage

    try:
        spec_text = context.spec_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("The spec is unreadable, so coverage per requirement is not shown: %s", exc)
        return {}
    coder_root = context.isolation.execution_root or context.project_path
    return requirement_coverage(spec_text, coder_root, scenarios_root(context))


def default_test_target(context: RunContext, kind: str) -> str:
    """The file a test step runs when it names none: the scenario file for the scenario step only.

    Every other step runs the coder's own tests, where `generate_tests` wrote them. Falling back to
    the scenario file for every kind retried the coder until the hidden scenario tests passed.
    """
    stem = module_stem(context.spec_path)
    if kind == "scenario":
        from specweaver.sandbox.language.core.scenario_converter_factory import (
            create_scenario_converter,
        )

        return str(
            create_scenario_converter(context.project_path).output_path(
                stem, scenarios_root(context).parent
            )
        )
    from specweaver.core.flow.engine.task_files import task_files_for

    # Relative: the QA atom reads it from where the step runs, the run's worktree included.
    return task_files_for(context.project_path, context.spec_path, context.isolation.language).tests


def task_file(context: RunContext, which: str) -> Path | None:
    """The task's code or tests file outside Python; None for Python, whose `output_dir` stays."""
    from specweaver.core.flow.engine.task_files import task_files_for

    files = task_files_for(context.project_path, context.spec_path, context.isolation.language)
    relative = files.code if which == "code" else files.tests
    return None if relative.endswith(".py") else context.project_path / relative


def task_code_file(context: RunContext) -> Path:
    """The task's code file, where generation writes it; Python keeps the run's `output_dir`."""
    stem = module_stem(context.spec_path)
    return task_file(context, "code") or (
        (context.output_dir or context.project_path / "src") / f"{stem}.py"
    )


def step_file(step: PipelineStep, context: RunContext) -> Path | None:
    """The file a step works on: its `target` (old spelling `target_path`), else the task's code
    file; None when that file is not there yet.

    Raises `ValueError` naming a given target that is outside the project or not a file.
    """
    params = step.params or {}
    target = params.get("target") or params.get("target_path")
    if not target:
        code = task_code_file(context)
        return code if code.is_file() else None
    return file_inside(context.project_path, str(target))


def resolve_inside(project: Path, target: str) -> Path:
    """`target` resolved against `project`; raises `ValueError` naming it when it is outside the
    project, a link out included."""
    candidate = (project / target).resolve()
    if not candidate.is_relative_to(project.resolve()):
        msg = f"target {target!r} is outside the project"
        raise ValueError(msg)
    return candidate


def file_inside(project: Path, target: str) -> Path:
    """`resolve_inside`, and also refused when it is not a file."""
    candidate = resolve_inside(project, target)
    if not candidate.is_file():
        msg = f"target {target!r} is not a file"
        raise ValueError(msg)
    return candidate


def generated_code(context: RunContext) -> str:
    """The run's generated module, relative to where its tests run; "" when there is none."""
    from specweaver.core.flow.handlers.archetype_pipelines import relative_to_root

    code = task_code_file(context)
    root = context.isolation.execution_root or context.project_path
    if not code.is_file():
        return ""
    relative = relative_to_root(code, root)
    if relative is None:
        logger.warning("%s is outside %s; the tests run without it as their source", code, root)
        return ""
    return relative
