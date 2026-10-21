# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The generate steps write in the run's language: its instructions, role, tag, task and fences.

Proves: D-INTL-08 FR-4
Proves: D-INTL-08 NFR-1
Proves: D-INTL-08 NFR-4

The real runner, handlers, prompt builder and generator; only the model is doubled, and it records
what it is sent.

| Bucket | Case |
|---|---|
| Happy | a Java code step: Java instructions and role, a `//` tag, the task brief, the fence gone; a Java tests step names JUnit 5; a Kotlin step is tagged `//` |
| Boundary | Python's prompt and role are today's, byte for byte, with no brief (NFR-1); Rust declares its module once, in a `lib.rs` created beside `main.rs`; the agentic coder's role is the language's |
| Degradation | a second Rust run adds no second declaration |
| Hostile | a project whose manifests say Python, named Java in `[implement]`, gets a Java contract — no second detection (NFR-4) |
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.autonomy_policy import AutonomyPolicy
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

#: Today's Python text, copied before SF-03 moved it into `workflows/languages/python.md`.
_PY_CODE = """\
You are a Python code generator. You are implementing a component from its specification.

## Requirements:
1. Implement ALL functions/classes described in the Contract section.
2. Handle ALL error cases from the Policy section.
3. Follow the Protocol section step by step.
4. Include proper type hints on all public methods.
5. Include docstrings for all public methods.
6. Do NOT add functionality not described in the spec.

## Output:
Produce ONLY valid Python code. No markdown fences, no explanation.
Start with imports, then data models, then the main implementation.
Include a module docstring."""

_PY_TESTS = """\
You are a Python test generator. You are writing tests for a component from its specification.

## Requirements:
1. Write tests using pytest.
2. Cover ALL examples from the Contract section as test cases.
3. Cover ALL error cases from the Policy section.
4. Cover edge cases (empty input, None, boundary values).
5. Use descriptive test names (test_<scenario>).
6. Group tests in classes by concern.

## Output:
Produce ONLY valid Python code. No markdown fences, no explanation.
Start with imports, then test classes with test methods."""

_PY_CODE_ROLE = "You are a precise Python code generator. Output only valid Python code."
_PY_TESTS_ROLE = (
    "You are a precise Python test generator. Output only valid Python code using pytest."
)

_JAVA = "package com.example;\n\npublic class Greeter {}"


class _Model:
    """Answers with fenced code; records the system and user text of every call."""

    provider_name = "scripted"

    def __init__(self, answer: str = _JAVA, fence: str = "java") -> None:
        self._answer = f"```{fence}\n{answer}\n```"
        self.system: list[str] = []
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        self.system.append(messages[0].content)
        self.prompts.append(messages[-1].content)
        return LLMResponse(text=self._answer, model="test-model")

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any, **_k: Any
    ) -> LLMResponse:
        self.system.append(str(messages[0]["content"]))
        self.prompts.append(str(messages[-1]["content"]))
        await tool_executor.execute(
            "create_module", {"path": "src/greeter.rs", "code": "pub fn greet() {}\n"}
        )
        return LLMResponse(text="done", model="test-model")


def _project(root: Path, manifest: tuple[str, str] | None = None) -> Path:
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    if manifest:
        (root / manifest[0]).write_text(manifest[1], encoding="utf-8")
    return root


_POM = "<project><groupId>com.example</groupId></project>"


def _run(
    root: Path,
    model: _Model,
    language: str | None,
    target: StepTarget = StepTarget.CODE,
    *,
    mode: str | None = None,
) -> Any:
    context = RunContext(
        project_path=root,
        spec_path=root / "specs" / "greeter_spec.md",
        model=ModelAccess(config=MagicMock(), llm_router=FixedRouter(model)),
    )
    update: dict[str, Any] = {"language": language}
    if mode:
        update |= {
            "autonomy": AutonomyPolicy(agentic_max_dal=DALLevel.DAL_D),
            "dal_level": DALLevel.DAL_E,
        }
    context.isolation = context.isolation.model_copy(update=update)
    step = PipelineStep(name="write", action=StepAction.GENERATE, target=target, mode=mode)
    pipeline = PipelineDefinition(name="p", steps=[step])
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def test_python_speaks_as_it_always_did(tmp_path: Path) -> None:
    root = _project(tmp_path)
    model = _Model("def greet():\n    pass", fence="python")

    _run(root, model, "python")
    _run(root, model, "python", StepTarget.TESTS)

    assert model.system == [_PY_CODE_ROLE, _PY_TESTS_ROLE]
    assert _PY_CODE in model.prompts[0]
    assert _PY_TESTS in model.prompts[1]
    assert "# sw-artifact:" in model.prompts[0]
    assert "Task files" not in model.prompts[0]


def test_a_java_code_step_speaks_java(tmp_path: Path) -> None:
    root = _project(tmp_path, ("pom.xml", _POM))
    model = _Model()

    run = _run(root, model, "java")

    assert run.status == RunStatus.COMPLETED
    assert "Java" in model.system[0]
    assert "Python" not in model.system[0]
    assert "You are a Python" not in model.prompts[0]
    assert "// sw-artifact:" in model.prompts[0]
    assert "src/main/java/com/example/Greeter.java" in model.prompts[0]
    assert "package `com.example`" in model.prompts[0]
    written = root / "src" / "main" / "java" / "com" / "example" / "Greeter.java"
    assert written.read_text(encoding="utf-8") == _JAVA + "\n"


def test_a_java_tests_step_names_junit(tmp_path: Path) -> None:
    root = _project(tmp_path, ("pom.xml", _POM))
    model = _Model()

    _run(root, model, "java", StepTarget.TESTS)

    assert "Java" in model.system[0]
    assert "JUnit 5" in model.prompts[0]
    assert (root / "src/test/java/com/example/GreeterTest.java").is_file()


def test_a_kotlin_step_is_tagged(tmp_path: Path) -> None:
    root = _project(tmp_path, ("build.gradle.kts", 'group = "com.example"\n'))
    model = _Model("package com.example\n\nclass Greeter", fence="kotlin")

    _run(root, model, "kotlin")

    assert "// sw-artifact:" in model.prompts[0]
    assert "Kotlin" in model.system[0]


_RUST = "pub fn greet() -> u8 {\n    1\n}"


def test_rust_declares_its_module_once(tmp_path: Path) -> None:
    root = _project(tmp_path, ("Cargo.toml", '[package]\nname = "greet"\n'))
    model = _Model(_RUST, fence="rust")

    _run(root, model, "rust")
    _run(root, model, "rust")

    lib = (root / "src" / "lib.rs").read_text(encoding="utf-8")
    assert lib.count("pub mod greeter;") == 1
    assert "`greet::greeter`" in model.prompts[0]


def test_rust_beside_main_gets_a_lib_and_main_is_kept(tmp_path: Path) -> None:
    root = _project(tmp_path, ("Cargo.toml", '[package]\nname = "greet"\n'))
    (root / "src").mkdir()
    (root / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")

    _run(root, _Model(_RUST, fence="rust"), "rust")

    assert "pub mod greeter;" in (root / "src" / "lib.rs").read_text(encoding="utf-8")
    assert (root / "src" / "main.rs").read_text(encoding="utf-8") == "fn main() {}\n"


def test_an_existing_declaration_is_not_repeated(tmp_path: Path) -> None:
    root = _project(tmp_path, ("Cargo.toml", '[package]\nname = "greet"\n'))
    (root / "src").mkdir()
    (root / "src" / "lib.rs").write_text("mod greeter;\npub mod other;\n", encoding="utf-8")

    _run(root, _Model(_RUST, fence="rust"), "rust")

    assert (root / "src" / "lib.rs").read_text(encoding="utf-8") == "mod greeter;\npub mod other;\n"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="git required")
def test_the_agentic_coder_speaks_the_language_and_declares_the_module(tmp_path: Path) -> None:
    root = _project(tmp_path, ("Cargo.toml", '[package]\nname = "greet"\n'))
    for args in (["init"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        _git(root, *args)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    model = _Model()

    run = _run(root, model, "rust", mode="agentic")

    assert run.status == RunStatus.COMPLETED, run.step_records[0].result
    assert model.system[0] == (
        "You are a precise Rust developer. You change files only through your tools."
    )
    assert "pub mod greeter;" in (root / "src" / "lib.rs").read_text(encoding="utf-8")


_CONTRACT_SPEC = '''# Greet

## 2. Contract

```python
def greet(name: str) -> str:
    """Return the greeting."""
```
'''


def test_the_contract_step_follows_the_named_language(tmp_path: Path) -> None:
    root = _project(tmp_path, ("pyproject.toml", '[project]\nname = "greet"\n'))
    (root / "specs" / "greeter_spec.md").write_text(_CONTRACT_SPEC, encoding="utf-8")
    context = RunContext(project_path=root, spec_path=root / "specs" / "greeter_spec.md")
    context.isolation = context.isolation.model_copy(update={"language": "java"})
    pipeline = PipelineDefinition(
        name="p",
        steps=[PipelineStep(name="c", action=StepAction.GENERATE, target=StepTarget.CONTRACT)],
    )

    run = asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())

    assert run.status == RunStatus.COMPLETED, run.step_records[0].result
    assert (root / "contracts" / "greeter_contract.java").is_file()
    assert not (root / "contracts" / "greeter_contract.py").exists()
