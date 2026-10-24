# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Lint repair, code validation and the task's test run each speak the run's language.

Proves: D-INTL-08 FR-6
Proves: D-INTL-08 FR-7
Proves: D-INTL-08 FR-5

| Bucket | Case |
|---|---|
| Happy | a Java file is fixed as "this Java file", fenced ```` ```java ````, its tag `//`; a Java file is judged by its test rules only, C02 naming `GreeterTest.java` |
| Boundary | a Python file keeps today's prompt and rules; a Spring Boot `.java` file runs its archetype's rules; a fence inside the fixed code stays |
| Degradation | a Java test file that ran no tests fails the step, as a Python one does |
| Hostile | the model's lost tag is put back in the file's own comment syntax, never `#` in Java |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler, ValidateTestsHandler
from specweaver.sandbox.base import AtomResult, AtomStatus
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

_UUID = "11111111-2222-3333-4444-999999999999"
_JAVA = "src/main/java/com/example/Greeter.java"


def _lint(errors: int) -> AtomResult:
    return AtomResult(
        status=AtomStatus.SUCCESS if errors == 0 else AtomStatus.FAILED,
        message="lint",
        exports={
            "error_count": errors,
            "fixable_count": 0,
            "fixed_count": 0,
            "errors": [{"file": _JAVA, "line": 1, "code": "L1", "message": "style"}] * errors,
        },
    )


def _context(tmp_path: Path, language: str | None, llm: object | None = None) -> RunContext:
    (tmp_path / "specs").mkdir(exist_ok=True)
    context = RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "specs" / "greeter_spec.md",
        model=ModelAccess(llm_router=FixedRouter(llm) if llm is not None else None),
    )
    context.isolation = context.isolation.model_copy(update={"language": language})
    return context


async def _fix(tmp_path: Path, path: str, code: str, answer: str, language: str) -> MagicMock:
    file = tmp_path / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(code, encoding="utf-8")
    atom = MagicMock()
    atom.run.side_effect = [_lint(1), _lint(1), _lint(1), _lint(0)]
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=MagicMock(text=answer))
    handler = LintFixHandler()
    handler._get_atom = lambda _ctx: atom  # type: ignore[method-assign]
    step = PipelineStep(
        name="lint_fix", action=StepAction.LINT_FIX, target=StepTarget.CODE, params={"target": path}
    )

    result = await handler.execute(step, _context(tmp_path, language, llm))

    assert result.status == StepStatus.PASSED, result
    return llm


def _prompt(llm: MagicMock) -> str:
    return llm.generate.call_args[0][0][0].content


async def test_a_java_file_is_fixed_as_java(tmp_path: Path) -> None:
    llm = await _fix(
        tmp_path,
        _JAVA,
        f"// sw-artifact: {_UUID}\nclass Greeter {{}}\n",
        "```java\nclass Greeter {}\n```",
        "java",
    )

    prompt = _prompt(llm)
    assert "this Java file" in prompt
    assert "```java\n" in prompt
    assert "fixed Java code" in prompt
    assert f"// sw-artifact: {_UUID}" in prompt
    assert "Python" not in prompt
    assert (tmp_path / _JAVA).read_text(encoding="utf-8") == (
        f"// sw-artifact: {_UUID}\nclass Greeter {{}}\n"
    )


async def test_a_python_file_keeps_its_prompt(tmp_path: Path) -> None:
    llm = await _fix(tmp_path, "src/greeter.py", "x=1\n", "x = 1", "python")

    prompt = _prompt(llm)
    assert prompt.startswith("Fix the following lint errors in this Python file.")
    assert "```python\n" in prompt
    assert prompt.rstrip().endswith("Return ONLY the fixed Python code, no explanations.")


async def test_a_fence_inside_the_fixed_code_stays(tmp_path: Path) -> None:
    code = 'val doc = """\n```\nx\n```\n"""'
    await _fix(
        tmp_path, "src/main/kotlin/G.kt", "val doc = 1\n", f"```kotlin\n{code}\n```", "kotlin"
    )

    assert (tmp_path / "src/main/kotlin/G.kt").read_text(encoding="utf-8") == code + "\n"


async def test_a_lost_tag_comes_back_in_the_files_syntax(tmp_path: Path) -> None:
    await _fix(
        tmp_path,
        "src/greeter.rs",
        f"// sw-artifact: {_UUID}\npub fn f() {{}}\n",
        "pub fn f() {}",
        "rust",
    )

    first = (tmp_path / "src/greeter.rs").read_text(encoding="utf-8").splitlines()[0]
    assert first == f"// sw-artifact: {_UUID}"


async def _validate(tmp_path: Path, path: str, content: str) -> object:
    file = tmp_path / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")
    (tmp_path / "specs").mkdir(exist_ok=True)
    (tmp_path / "specs" / "greeter_spec.md").write_text("# Greeter\n", encoding="utf-8")
    step = PipelineStep(
        name="validate_code",
        action=StepAction.VALIDATE,
        target=StepTarget.CODE,
        params={"target": path},
    )
    return await ValidateCodeHandler().execute(step, _context(tmp_path, None))


async def test_a_java_file_is_judged_on_its_tests_only(tmp_path: Path) -> None:
    result = await _validate(tmp_path, _JAVA, "class Greeter {}\n")

    assert result.status == StepStatus.FAILED
    assert {r["rule_id"] for r in result.output["results"]} == {"C02", "C03"}
    assert "GreeterTest.java" in str(result.output["results"])


async def test_a_python_file_keeps_its_rules(tmp_path: Path) -> None:
    result = await _validate(tmp_path, "src/greeter.py", "def greet() -> str:\n    return 'hi'\n")

    assert "note" not in result.output
    assert {r["rule_id"] for r in result.output["results"]} >= {"C01", "C02"}


async def test_an_archetype_with_java_rules_runs_them(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "context.yaml").write_text(
        "name: app\nlevel: module\narchetype: spring-boot\n", encoding="utf-8"
    )

    result = await _validate(tmp_path, _JAVA, "@RestController\nclass Greeter {}\n")

    assert "note" not in result.output
    assert "C12" in {r["rule_id"] for r in result.output["results"]}


@pytest.mark.parametrize(
    "target", ["src/test/java/com/example/GreeterTest.java", "tests/greeter.rs", "tests/test_g.py"]
)
async def test_one_test_file_that_ran_nothing_fails(tmp_path: Path, target: str) -> None:
    handler = ValidateTestsHandler()
    empty = AtomResult(
        status=AtomStatus.SUCCESS,
        message="All 0 tests passed.",
        exports={"passed": 0, "failed": 0, "errors": 0, "total": 0},
    )
    with patch.object(handler, "_get_atom", return_value=MagicMock()) as atom:
        atom.return_value.run.return_value = empty
        step = PipelineStep(
            name="run_tests",
            action=StepAction.VALIDATE,
            target=StepTarget.TESTS,
            params={"kind": "unit", "target": target},
        )
        result = await handler.execute(step, _context(tmp_path, None))

    assert result.status == StepStatus.FAILED
    assert "no tests executed" in (result.error_message or "").lower()
