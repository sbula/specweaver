# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a generate step does beyond asking the model: the agentic coder's run, and Rust's module
declaration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.engine.task_files import TaskFiles
    from specweaver.core.flow.handlers.run_context import RunContext


async def run_coder(
    step: PipelineStep,
    context: RunContext,
    output_path: Path,
    extra_files: list[str],
    adapter: Any,
    config: Any,
    base_prompt: Any,
    prompt_parts: dict[str, Any],
    *,
    role: str,
) -> str | None:
    """Let the coder write the step's target with its tools; why it could not, if it did not.

    Its tools write only that one file, within the project's `[docs]` rules for this step.
    """
    from specweaver.core.flow.engine.isolation import task_files
    from specweaver.core.flow.engine.work_unit import InProcessAgentRuntime, WorkUnit
    from specweaver.sandbox.dispatcher import ToolDispatcher
    from specweaver.sandbox.security import WorkspaceBoundary
    from specweaver.workflows.implementation.generator import generation_prompt

    target = output_path.relative_to(context.project_path).as_posix()
    if target not in task_files(context):
        return f"the step's target {target} is not among the run's task files"
    dispatcher = ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[context.project_path]),
        role="implementer",
        allowed_tools=["ast"],
        task_files=[target, *extra_files],
        doc_policy=context.isolation.doc_policy,
        step=step.name,
    )
    prompt = generation_prompt(context.spec_path, base_prompt, **prompt_parts)
    unit = WorkUnit(
        instructions=f"{prompt}\n\nWrite `{target}` with your tools. Answer with a short note.",
        context=role,
    )
    await InProcessAgentRuntime(adapter, dispatcher, config=config).run(unit)
    if not (context.project_path / target).is_file():
        return f"the coder ended without writing {target}"
    return None


def declare_rust_module(project_root: Path, files: TaskFiles) -> None:
    """`pub mod <module>;` in the crate root, once; the root is created when missing."""
    import re

    root = project_root / files.extra[0]
    module = files.code.rsplit("/", 1)[-1].removesuffix(".rs")
    text = root.read_text(encoding="utf-8") if root.is_file() else ""
    if re.search(rf"^\s*(pub(\([^)]*\))?\s+)?mod\s+{re.escape(module)}\s*;", text, re.MULTILINE):
        return
    root.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if not text or text.endswith("\n") else "\n"
    root.write_text(f"{text}{separator}pub mod {module};\n", encoding="utf-8")
