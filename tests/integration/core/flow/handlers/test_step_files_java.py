# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""On a Java project, the steps after generation find the file generation wrote.

Proves: TECH-078 FR-1

The seam is `generate_code` writing where `task_files_for` says, and `review_code`,
`validate_code` and `lint_fix` reading from the same place. A stray `.py` sits in `output_dir`,
where the old glob looked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.generation import GenerateCodeHandler
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.review import ReviewCodeHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler
from tests.scripted_llm import FixedRouter, ScriptedLLM

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_JAVA = (
    'package com.shop;\n\npublic class Greeter {\n    public String hello() { return "hi"; }\n}\n'
)


class _Recording(ScriptedLLM):
    """Keeps every prompt, so the test sees which file reached the reviewer."""

    def __init__(self, payloads: list[str]) -> None:
        super().__init__(payloads)
        self.prompts: list[str] = []

    async def generate(self, messages: Any, config: Any = None, *args: Any, **kwargs: Any) -> Any:
        self.prompts.append("\n".join(str(getattr(m, "content", m)) for m in messages))
        return await super().generate(messages, config, *args, **kwargs)


def _step(action: StepAction) -> PipelineStep:
    return PipelineStep(name=action.value, action=action, target=StepTarget.CODE)


@pytest.fixture
def project(tmp_path: Path) -> tuple[RunContext, _Recording]:
    (tmp_path / "pom.xml").write_text(
        "<project><groupId>com.shop</groupId><artifactId>shop</artifactId></project>\n"
    )
    spec = tmp_path / "greeter_spec.md"
    spec.write_text("# Greeter\n\n## Intent\n\nSay hello.\n")
    stray = tmp_path / "out"
    stray.mkdir()
    (stray / "aaa.py").write_text("print('not the task file')\n")
    llm = _Recording([f"```java\n{_JAVA}```", "VERDICT: ACCEPTED\nLooks fine."])
    context = RunContext(
        project_path=tmp_path,
        spec_path=spec,
        output_dir=stray,
        model=ModelAccess(llm_router=FixedRouter(llm)),
    )
    return context, llm


@pytest.mark.asyncio
async def test_the_steps_after_generation_work_on_the_java_file(
    project: tuple[RunContext, _Recording],
) -> None:
    context, llm = project
    written = context.project_path / "src/main/java/com/shop/Greeter.java"

    generated = await GenerateCodeHandler().execute(_step(StepAction.GENERATE), context)
    assert generated.status == StepStatus.PASSED, generated
    assert "class Greeter" in written.read_text()

    await ReviewCodeHandler().execute(_step(StepAction.REVIEW), context)
    assert "class Greeter" in llm.prompts[-1]
    assert "not the task file" not in llm.prompts[-1]

    validated = await ValidateCodeHandler().execute(_step(StepAction.VALIDATE), context)
    assert validated.output.get("note") == "no code rules for java", validated

    assert LintFixHandler()._fix_file(context, "src/") == written
