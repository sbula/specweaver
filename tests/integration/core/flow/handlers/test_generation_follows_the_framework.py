# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A generate step adds the framework's guidance: its idioms to the code, its test style to the tests.

Proves: D-INTL-08 FR-8
Proves: D-INTL-08 NFR-1

The real runner, handlers, archetype resolver and prompt builder; only the model is doubled.

| Bucket | Case |
|---|---|
| Happy | a `quarkus` archetype folder: the code prompt carries Quarkus idioms, the tests prompt `@QuarkusTest` |
| Boundary | a FastAPI project keeps the Python text and adds `TestClient` (Q1); a Python project without a framework keeps today's prompt (pinned in `test_generation_speaks_the_language.py`) |
| Degradation | a project framework file without its sections stops the step, naming the file |
| Hostile | not applicable — archetype names are refused before any path is built (unit tests) |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.models import LLMResponse
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


class _Model:
    provider_name = "scripted"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        self.prompts.append(messages[-1].content)
        return LLMResponse(text="class Greeter {}", model="test-model")


def _run(root: Path, model: _Model, language: str, target: StepTarget) -> Any:
    context = RunContext(
        project_path=root,
        spec_path=root / "specs" / "greeter_spec.md",
        model=ModelAccess(config=MagicMock(), llm_router=FixedRouter(model)),
    )
    context.isolation = context.isolation.model_copy(update={"language": language})
    step = PipelineStep(name="write", action=StepAction.GENERATE, target=target)
    pipeline = PipelineDefinition(name="p", steps=[step])
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def _project(root: Path) -> Path:
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    return root


def test_a_quarkus_folder_gets_quarkus_guidance(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "src").mkdir()
    (root / "src" / "context.yaml").write_text("archetype: quarkus\n", encoding="utf-8")
    model = _Model()

    _run(root, model, "java", StepTarget.CODE)
    _run(root, model, "java", StepTarget.TESTS)

    assert "@ApplicationScoped" in model.prompts[0]
    assert "@QuarkusTest" not in model.prompts[0]
    assert "@QuarkusTest" in model.prompts[1]


def test_a_fastapi_project_keeps_python_and_adds_fastapi(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "g"\ndependencies = ["fastapi"]\n', encoding="utf-8"
    )
    model = _Model()

    _run(root, model, "python", StepTarget.TESTS)

    assert "1. Write tests using pytest." in model.prompts[0]
    assert "TestClient" in model.prompts[0]


def test_a_broken_project_framework_file_stops_the_step(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "src").mkdir()
    (root / "src" / "context.yaml").write_text("archetype: micronaut\n", encoding="utf-8")
    own = root / ".specweaver" / "frameworks" / "micronaut.md"
    own.parent.mkdir(parents=True)
    own.write_text("---\nname: Micronaut\nlanguages: java\n---\n# Code\nBeans.\n", "utf-8")

    run = _run(root, _Model(), "java", StepTarget.CODE)

    assert run.status != RunStatus.COMPLETED
    assert "micronaut.md" in (run.step_records[0].result.error_message or "")
