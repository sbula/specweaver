# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw implement` in each of the five languages: generate, lint, run the task's tests, validate.

Proves: D-INTL-08 FR-9
Proves: D-INTL-08 FR-6
Proves: D-INTL-08 FR-7

US-3 P-5, the doubled half: the model and the language's runner are doubled, everything between them
is real — the CLI, the language detection, the task's files, the prompts, the lint loop, the QA
targets and the code validation. The real toolchains run in SF-05's `toolchain` tier.

| Bucket | Case |
|---|---|
| Happy | Python, Java, Kotlin, TypeScript and Rust each get their files at the derived paths, in the language, unfenced, with the language's tag asked for |
| Boundary | lint runs on the code file and asks the model to fix "this <Name> file"; the tests run on the task's test file; Rust's `lib.rs` declares the module |
| Degradation | a language without code rules says so and the run still ends well; Python keeps its rules |
| Hostile | not applicable — every input is the user's own project; hostile paths are proven by SF-01's derivation tests |
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    CompileRunResult,
    ComplexityRunResult,
    DebugRunResult,
    LintError,
    LintRunResult,
    QARunnerInterface,
    TestRunResult,
)
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e


@dataclass(frozen=True)
class _Language:
    key: str
    name: str
    fence: str
    tag: str
    manifest: tuple[str, str] | None
    code_file: str
    tests_file: str
    code: str
    tests: str


_LANGUAGES = [
    _Language(
        "python",
        "Python",
        "python",
        "# sw-artifact:",
        None,
        "src/greeter.py",
        "tests/test_greeter.py",
        "def greet() -> str:\n    return 'hi'",
        "from greeter import greet\n\n\ndef test_greet() -> None:\n    assert greet() == 'hi'",
    ),
    _Language(
        "java",
        "Java",
        "java",
        "// sw-artifact:",
        ("pom.xml", "<project><groupId>com.example</groupId></project>"),
        "src/main/java/com/example/Greeter.java",
        "src/test/java/com/example/GreeterTest.java",
        "package com.example;\n\npublic class Greeter {}",
        "package com.example;\n\nclass GreeterTest {}",
    ),
    _Language(
        "kotlin",
        "Kotlin",
        "kotlin",
        "// sw-artifact:",
        ("build.gradle.kts", 'plugins { kotlin("jvm") }\ngroup = "com.example"\n'),
        "src/main/kotlin/com/example/Greeter.kt",
        "src/test/kotlin/com/example/GreeterTest.kt",
        "package com.example\n\nclass Greeter",
        "package com.example\n\nclass GreeterTest",
    ),
    _Language(
        "typescript",
        "TypeScript",
        "ts",
        "// sw-artifact:",
        (
            "package.json",
            json.dumps({"scripts": {"test": "vitest"}, "devDependencies": {"vitest": "^3"}}),
        ),
        "src/greeter.ts",
        "tests/greeter.test.ts",
        "export const greet = (): string => 'hi';",
        "import { greet } from '../src/greeter';",
    ),
    _Language(
        "rust",
        "Rust",
        "rust",
        "// sw-artifact:",
        ("Cargo.toml", '[package]\nname = "greet"\n'),
        "src/greeter.rs",
        "tests/greeter.rs",
        'pub fn greet() -> &\'static str {\n    "hi"\n}',
        "use greet::greeter::greet;",
    ),
]


class _Model:
    """Answers in the language, fenced; records each call's role and prompt."""

    provider_name = "scripted"

    def __init__(self, language: _Language) -> None:
        self._language = language
        self.calls: list[tuple[str, str]] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        role = messages[0].content if len(messages) > 1 else ""
        prompt = messages[-1].content
        self.calls.append((role, prompt))
        body = self._language.tests if "test generator" in role else self._language.code
        return LLMResponse(text=f"```{self._language.fence}\n{body}\n```", model="test-model")

    async def generate_with_tools(self, messages: Any, config: Any, *_a: Any, **_k: Any):
        raise AssertionError("a one-shot run never hands the model tools")


class _Runner(QARunnerInterface):
    """The language's runner, doubled: one lint error until the model has fixed it, every test
    passing. Records what it was asked to lint and test."""

    def __init__(self, language: str, log: dict[str, list[str]]) -> None:
        self._language = language
        self._log = log

    @property
    def language_name(self) -> str:
        return self._language

    def run_tests(self, target: str, *_a: Any, **_k: Any) -> TestRunResult:
        self._log["tests"].append(target)
        return TestRunResult(
            total=1, passed=1, failed=0, errors=0, skipped=0, duration_seconds=0.1, failures=[]
        )

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        if fix:
            self._log["fix"].append(target)
            return LintRunResult(error_count=0, fixable_count=0, fixed_count=0, errors=[])
        self._log["lint"].append(target)
        dirty = len(self._log["lint"]) <= 2
        errors = [LintError(file=target, line=1, code="L1", message="style")] if dirty else []
        return LintRunResult(error_count=len(errors), fixable_count=0, fixed_count=0, errors=errors)

    def run_complexity(self, target: str, max_complexity: int = 10) -> ComplexityRunResult:
        return ComplexityRunResult(violation_count=0, max_complexity=max_complexity, violations=[])

    def run_compiler(self, target: str) -> CompileRunResult:
        return CompileRunResult(error_count=0, warning_count=0, errors=[])

    def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:
        return DebugRunResult(exit_code=0, duration_seconds=0.0, events=[])

    def run_architecture_check(self, target: str, dal_level: Any = None) -> ArchitectureRunResult:
        return ArchitectureRunResult(violation_count=0, violations=[])


def _project(tmp_path: Path, language: _Language) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "poly", "--path", str(project)]).exit_code == 0
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    if language.manifest:
        (project / language.manifest[0]).write_text(language.manifest[1], encoding="utf-8")
    return project


def _implement(project: Path, language: _Language) -> tuple[Any, _Model, dict[str, list[str]]]:
    model = _Model(language)
    log: dict[str, list[str]] = {"tests": [], "lint": [], "fix": []}
    with (
        doubled_llm(model),
        patch(
            "specweaver.sandbox.qa_runner.core.factory.resolve_runner",
            side_effect=lambda cwd, executor=None, language=None: _Runner(language or "?", log),
        ),
    ):
        result = runner.invoke(
            app,
            ["implement", str(project / "specs" / "greeter_spec.md"), "--project", str(project)],
        )
    return result, model, log


@pytest.mark.usefixtures("_mock_db")
@pytest.mark.parametrize("language", _LANGUAGES, ids=[lang.key for lang in _LANGUAGES])
def test_sw_implement_speaks_the_language(tmp_path: Path, language: _Language) -> None:
    project = _project(tmp_path, language)

    result, model, log = _implement(project, language)

    assert result.exit_code == 0, result.output
    assert (project / language.code_file).read_text(encoding="utf-8") == language.code + "\n"
    assert (project / language.tests_file).read_text(encoding="utf-8") == language.tests + "\n"

    code_role, code_prompt = model.calls[0]
    assert language.name in code_role
    assert language.tag in code_prompt

    assert log["lint"][0] == language.code_file
    assert log["tests"] == [language.tests_file]
    fix_prompts = [prompt for role, prompt in model.calls if prompt.startswith("Fix the following")]
    assert fix_prompts, "the lint loop never asked the model"
    assert f"this {language.name} file" in fix_prompts[0]
    assert f"```{language.key}\n" in fix_prompts[0]

    if language.key == "python":
        assert shows(result.output, "rules passed")
    else:
        assert shows(result.output, f"no code rules for {language.key}")
        assert not re.search(r"failed rules:.*C0[12]", result.output)


@pytest.mark.usefixtures("_mock_db")
def test_rust_declares_the_module_in_its_library(tmp_path: Path) -> None:
    rust = next(lang for lang in _LANGUAGES if lang.key == "rust")
    project = _project(tmp_path, rust)

    result, _, _ = _implement(project, rust)

    assert result.exit_code == 0, result.output
    assert "pub mod greeter;" in (project / "src" / "lib.rs").read_text(encoding="utf-8")
