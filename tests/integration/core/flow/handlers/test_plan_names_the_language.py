# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's plan step tells the planner the project's language.

Proves: TECH-078 FR-5

The seam is `PlanSpecHandler` resolving the run's language (`task_files_for`, the language guide)
and the planner's prompt carrying it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.generation import PlanSpecHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.models import Role
from tests.scripted_llm import FixedRouter, ScriptedLLM

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_PLAN = json.dumps(
    {
        "spec_path": "greeter_spec.md",
        "spec_name": "Greeter",
        "spec_hash": "x",
        "timestamp": "2026-10-24T00:00:00Z",
        "file_layout": [],
        "reasoning": "small",
        "confidence": 80,
    }
)


class _Recording(ScriptedLLM):
    def __init__(self, payloads: list[str]) -> None:
        super().__init__(payloads)
        self.systems: list[str] = []

    async def generate(self, messages: Any, config: Any = None, *args: Any, **kwargs: Any) -> Any:
        self.systems += [m.content for m in messages if m.role == Role.SYSTEM]
        return await super().generate(messages, config, *args, **kwargs)


def _project(root: Path, manifest: str, text: str) -> RunContext:
    (root / manifest).write_text(text, encoding="utf-8")
    spec = root / "greeter_spec.md"
    spec.write_text("# Greeter\n\n## 1. Purpose\n\nGreets.\n", encoding="utf-8")
    return RunContext(project_path=root, spec_path=spec)


@pytest.mark.parametrize(
    ("manifest", "text", "name"),
    [
        ("Cargo.toml", '[package]\nname = "probe"\nversion = "0.1.0"\n', "Rust"),
        ("package.json", '{"name": "probe"}\n', "TypeScript"),
    ],
)
async def test_the_plan_step_names_the_projects_language(
    tmp_path: Path, manifest: str, text: str, name: str
) -> None:
    llm = _Recording([_PLAN])
    context = _project(tmp_path, manifest, text)
    context.model = ModelAccess(llm_router=FixedRouter(llm))

    result = await PlanSpecHandler().execute(
        PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC), context
    )

    assert result.status == StepStatus.PASSED, result
    assert f"for a {name} project" in llm.systems[0]


async def test_a_bad_package_line_fails_the_step_naming_it(tmp_path: Path) -> None:
    context = _project(tmp_path, "pom.xml", "<project><groupId>a</groupId></project>\n")
    context.spec_path.write_text("# Greeter\n> **Package**: Not-A.Package\n", encoding="utf-8")
    context.model = ModelAccess(llm_router=FixedRouter(_Recording([_PLAN])))

    result = await PlanSpecHandler().execute(
        PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC), context
    )

    assert result.status == StepStatus.ERROR
    assert "greeter_spec.md:2" in (result.error_message or "")
