# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw implement` in a Spring Boot, a Quarkus and a NestJS project asks for the framework's style.

Proves: D-INTL-08 FR-8

US-3 P-9. The model and the language's runner are doubled; the CLI, the detection from the build
file, the framework files and the prompts are real.

| Bucket | Case |
|---|---|
| Happy | Spring Boot (Maven parent), Quarkus (Gradle) and NestJS (`package.json`): the tests prompt names the framework's test style, and the run says which framework it used |
| Boundary | the code prompt carries the idioms but not the test style |
| Degradation | not applicable — a project without a framework is the language journey, `test_implement_in_every_language_e2e.py` |
| Hostile | not applicable — archetype names are refused before any path is built (unit tests) |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from specweaver.sandbox.qa_runner.core.interface import LintRunResult, TestRunResult
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

_CASES = [
    (
        "spring-boot",
        "pom.xml",
        "<project><groupId>com.example</groupId>"
        "<parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>",
        "@WebMvcTest",
    ),
    (
        "quarkus",
        "build.gradle",
        "plugins { id 'io.quarkus' }\ngroup = 'com.example'\n",
        "@QuarkusTest",
    ),
    (
        "nestjs",
        "package.json",
        json.dumps({"scripts": {"test": "jest"}, "dependencies": {"@nestjs/core": "^10"}}),
        "Test.createTestingModule",
    ),
]


class _Model:
    provider_name = "scripted"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        self.calls.append((messages[0].content, messages[-1].content))
        return LLMResponse(text="class Greeter {}", model="test-model")


class _Runner:
    """Clean lint, one passing test."""

    language_name = "doubled"

    def run_linter(self, target: str, fix: bool = False) -> LintRunResult:
        return LintRunResult(error_count=0, fixable_count=0, fixed_count=0, errors=[])

    def run_tests(self, target: str, *_a: Any, **_k: Any) -> TestRunResult:
        return TestRunResult(
            total=1, passed=1, failed=0, errors=0, skipped=0, duration_seconds=0.1, failures=[]
        )


@pytest.mark.usefixtures("_mock_db")
@pytest.mark.parametrize(("key", "manifest", "text", "style"), _CASES, ids=[c[0] for c in _CASES])
def test_sw_implement_asks_for_the_frameworks_style(
    tmp_path: Path, key: str, manifest: str, text: str, style: str
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "fw", "--path", str(project)]).exit_code == 0
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    (project / manifest).write_text(text, encoding="utf-8")
    model = _Model()

    with (
        doubled_llm(model),
        patch(
            "specweaver.sandbox.qa_runner.core.factory.resolve_runner",
            side_effect=lambda *_a, **_k: _Runner(),
        ),
    ):
        result = runner.invoke(
            app,
            ["implement", str(project / "specs" / "greeter_spec.md"), "--project", str(project)],
        )

    assert result.exit_code == 0, result.output
    code_prompt = next(p for role, p in model.calls if "code generator" in role)
    tests_prompt = next(p for role, p in model.calls if "test generator" in role)
    assert style in tests_prompt
    assert style not in code_prompt
    assert shows(result.output, f"Framework: {key} (build file)")
