# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Generation, the merge allow-list and `sw implement`'s QA targets name the same files, per language.

Proves: D-INTL-08 FR-3
Proves: D-INTL-08 NFR-1

Each language's sample project (a copy of `tests/fixtures/`), the real generate steps with a doubled
model, the real allow-list and the real `sw implement` pipeline. The model's text lands wherever the
step writes it; this proves *where*, not *what*.

| Bucket | Case |
|---|---|
| Happy | Java (Maven and Gradle), Kotlin, Rust and TypeScript: one set of files everywhere |
| Boundary | Python: byte-identical to before (`src/<stem>.py`, `tests/test_<stem>.py`) |
| Degradation | not applicable — names only |
| Hostile | not applicable — a hostile package is proven by the unit tests |
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.isolation import task_files
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.task_files import task_files_for
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.workflows.implementation.interfaces.cli import _build_implement_pipeline
from tests.scripted_llm import FixedRouter

pytestmark = pytest.mark.integration

_FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"


class _Model:
    def available(self) -> bool:
        return True

    async def generate(self, *_a: Any, **_k: Any) -> LLMResponse:
        return LLMResponse(text="// generated\n", model="test-model")


def _project(tmp_path: Path, kind: str) -> Path:
    root = tmp_path / "proj"
    if kind in {
        "java_maven_project",
        "java_gradle_project",
        "kotlin_gradle_project",
        "sample_project",
    }:
        shutil.copytree(_FIXTURES / kind, root)
    elif kind == "rust":
        (root / "src").mkdir(parents=True)
        (root / "Cargo.toml").write_text('[package]\nname = "p"\n', encoding="utf-8")
        (root / "src" / "lib.rs").write_text("", encoding="utf-8")
    else:
        root.mkdir()
        (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "specs").mkdir(exist_ok=True)
    (root / "specs" / "greet_service_spec.md").write_text("# G\n## 1. Purpose\nGreets.\n")
    return root


@pytest.mark.parametrize(
    ("kind", "code", "tests"),
    [
        ("sample_project", "src/greet_service.py", "tests/test_greet_service.py"),
        (
            "java_maven_project",
            "src/main/java/com/example/GreetService.java",
            "src/test/java/com/example/GreetServiceTest.java",
        ),
        (
            "java_gradle_project",
            "src/main/java/com/example/GreetService.java",
            "src/test/java/com/example/GreetServiceTest.java",
        ),
        (
            "kotlin_gradle_project",
            "src/main/kotlin/GreetService.kt",
            "src/test/kotlin/GreetServiceTest.kt",
        ),
        ("rust", "src/greet_service.rs", "tests/greet_service.rs"),
        ("typescript", "src/greet_service.ts", "tests/greet_service.test.ts"),
    ],
)
def test_one_set_of_files_everywhere(tmp_path: Path, kind: str, code: str, tests: str) -> None:
    root = _project(tmp_path, kind)
    spec = root / "specs" / "greet_service_spec.md"
    context = RunContext(
        project_path=root,
        spec_path=spec,
        output_dir=root / "src",
        model=ModelAccess(config=MagicMock(), llm_router=FixedRouter(_Model())),
    )
    steps = [
        PipelineStep(name="code", action=StepAction.GENERATE, target=StepTarget.CODE),
        PipelineStep(name="tests", action=StepAction.GENERATE, target=StepTarget.TESTS),
    ]

    asyncio.run(
        PipelineRunner(
            PipelineDefinition(name="p", steps=steps), context, registry=StepHandlerRegistry()
        ).run()
    )

    assert (root / code).is_file()
    assert (root / tests).is_file()
    assert task_files(context)[:2] == [code, tests]
    targets = {
        s.name: s.params.get("target")
        for s in _build_implement_pipeline(task_files_for(root, spec, None)).steps
    }
    assert (targets["lint_fix"], targets["validate_code"], targets["run_tests"]) == (
        code,
        code,
        tests,
    )
