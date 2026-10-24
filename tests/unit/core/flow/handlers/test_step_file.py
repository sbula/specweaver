# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every step that works on the generated code finds it one way.

Proves: TECH-078 FR-1
Proves: TECH-078 FR-2
Proves: TECH-078 NFR-3

| Bucket | Case |
|---|---|
| Happy | `target` names the file; `target_path` is still read; no target → the task's file per language |
| Boundary | `target` wins over `target_path`; an absolute target inside; Python keeps `output_dir` |
| Degradation | the task's file is missing → None; a target that is not a file is named |
| Hostile | `..`, an outside absolute path and a link out are refused, naming the target |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.drift import DriftCheckHandler
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.qa_targets import step_file, task_code_file
from specweaver.core.flow.handlers.review import ReviewCodeHandler
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

_POM = "<project><groupId>com.shop</groupId><artifactId>shop</artifactId></project>\n"
_JAVA_FILE = "src/main/java/com/shop/Greeter.java"


def _step(action: StepAction = StepAction.VALIDATE, **params: str) -> PipelineStep:
    return PipelineStep(name="s", action=action, target=StepTarget.CODE, params=params)


def _java_project(root: Path) -> RunContext:
    """A Maven project whose task file exists, and a stray `.py` where a glob would look."""
    (root / "pom.xml").write_text(_POM)
    spec = root / "greeter_spec.md"
    spec.write_text("# Greeter\n")
    (root / _JAVA_FILE).parent.mkdir(parents=True)
    (root / _JAVA_FILE).write_text("package com.shop;\npublic class Greeter {}\n")
    stray = root / "out"
    stray.mkdir()
    (stray / "aaa.py").write_text("x = 1\n")
    return RunContext(project_path=root, spec_path=spec, output_dir=stray)


def _python_project(root: Path) -> RunContext:
    spec = root / "greeter_spec.md"
    spec.write_text("# Greeter\n")
    out = root / "out"
    out.mkdir()
    (out / "aaa_decoy.py").write_text("x = 1\n")
    (out / "greeter.py").write_text("y = 2\n")
    return RunContext(project_path=root, spec_path=spec, output_dir=out)


class TestStepFile:
    def test_target_names_the_file(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        assert step_file(_step(target="pom.xml"), context) == (tmp_path / "pom.xml").resolve()

    def test_the_old_spelling_is_still_read(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        assert step_file(_step(target_path="pom.xml"), context) == (tmp_path / "pom.xml").resolve()

    def test_target_wins_over_the_old_spelling(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        found = step_file(_step(target=_JAVA_FILE, target_path="pom.xml"), context)

        assert found == (tmp_path / _JAVA_FILE).resolve()

    def test_an_absolute_target_inside_the_project(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        found = step_file(_step(target=str(tmp_path / "pom.xml")), context)

        assert found == (tmp_path / "pom.xml").resolve()

    def test_no_target_is_the_tasks_java_file_not_a_stray_py(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        assert step_file(_step(), context) == tmp_path / _JAVA_FILE

    def test_python_keeps_the_runs_output_dir(self, tmp_path: Path) -> None:
        context = _python_project(tmp_path)

        assert step_file(_step(), context) == tmp_path / "out" / "greeter.py"

    def test_python_without_output_dir_is_src(self, tmp_path: Path) -> None:
        context = _python_project(tmp_path)
        context.output_dir = None
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "greeter.py").write_text("z = 3\n")

        assert step_file(_step(), context) == tmp_path / "src" / "greeter.py"

    def test_an_empty_target_is_no_target(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        assert step_file(_step(target=""), context) == tmp_path / _JAVA_FILE

    def test_a_bad_package_line_is_named(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)
        context.spec_path.write_text("# Greeter\n> **Package**: Not-A.Package\n")

        with pytest.raises(ValueError, match=r"greeter_spec\.md:2"):
            step_file(_step(), context)

    def test_a_missing_task_file_is_none(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)
        (tmp_path / _JAVA_FILE).unlink()

        assert step_file(_step(), context) is None

    def test_a_target_that_is_not_a_file_is_named(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        with pytest.raises(ValueError, match="src/main"):
            step_file(_step(target="src/main"), context)

    def test_a_missing_target_is_named(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        with pytest.raises(ValueError, match=r"gone\.java"):
            step_file(_step(target="gone.java"), context)

    @pytest.mark.parametrize("target", ["../outside.py", "/etc/passwd"])
    def test_a_target_outside_the_project_is_refused(self, tmp_path: Path, target: str) -> None:
        project = tmp_path / "p"
        project.mkdir()
        (tmp_path / "outside.py").write_text("x = 1\n")
        context = _java_project(project)

        with pytest.raises(ValueError, match="outside the project"):
            step_file(_step(target=target), context)

    def test_a_link_out_of_the_project_is_refused(self, tmp_path: Path) -> None:
        project = tmp_path / "p"
        project.mkdir()
        (tmp_path / "secret.py").write_text("x = 1\n")
        context = _java_project(project)
        (project / "link.py").symlink_to(tmp_path / "secret.py")

        with pytest.raises(ValueError, match=r"link\.py"):
            step_file(_step(target="link.py"), context)


class TestTaskCodeFile:
    def test_java_is_the_task_file(self, tmp_path: Path) -> None:
        assert task_code_file(_java_project(tmp_path)) == tmp_path / _JAVA_FILE

    def test_python_is_output_dir_stem(self, tmp_path: Path) -> None:
        assert task_code_file(_python_project(tmp_path)) == tmp_path / "out" / "greeter.py"


def _with_llm(context: RunContext) -> RunContext:
    context.model = context.model.model_copy(update={"llm_router": FixedRouter(AsyncMock())})
    return context


class TestHandlersUseIt:
    @pytest.mark.asyncio
    async def test_review_refuses_a_target_outside(self, tmp_path: Path) -> None:
        context = _with_llm(_java_project(tmp_path))

        result = await ReviewCodeHandler().execute(
            _step(StepAction.REVIEW, target="../x.py"), context
        )

        assert result.status == StepStatus.ERROR
        assert "outside the project" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_review_reads_the_old_spelling_inside_only(self, tmp_path: Path) -> None:
        context = _with_llm(_java_project(tmp_path))

        result = await ReviewCodeHandler().execute(
            _step(StepAction.REVIEW, target_path="/etc/passwd"), context
        )

        assert result.status == StepStatus.ERROR
        assert "outside the project" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_review_without_target_reviews_the_java_file(self, tmp_path: Path) -> None:
        context = _with_llm(_java_project(tmp_path))
        verdict = MagicMock(findings=[], raw_response="ok", summary="ok")
        verdict.verdict.value = "accepted"

        with patch(
            "specweaver.workflows.review.reviewer.Reviewer.review_code", return_value=verdict
        ) as review:
            await ReviewCodeHandler().execute(_step(StepAction.REVIEW), context)

        assert review.call_args.args[0] == tmp_path / _JAVA_FILE

    @pytest.mark.asyncio
    async def test_review_with_nothing_generated_says_so(self, tmp_path: Path) -> None:
        context = _with_llm(_java_project(tmp_path))
        (tmp_path / _JAVA_FILE).unlink()

        result = await ReviewCodeHandler().execute(_step(StepAction.REVIEW), context)

        assert result.status == StepStatus.ERROR
        assert "No code file found" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_validate_names_a_bad_package_line(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)
        context.spec_path.write_text("# Greeter\n> **Package**: Not-A.Package\n")

        result = await ValidateCodeHandler().execute(_step(), context)

        assert result.status == StepStatus.ERROR
        assert "greeter_spec.md:2" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_validate_refuses_a_target_outside(self, tmp_path: Path) -> None:
        result = await ValidateCodeHandler().execute(
            _step(target="../x.py"), _java_project(tmp_path)
        )

        assert result.status == StepStatus.ERROR
        assert "outside the project" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_validate_without_target_judges_the_java_file(self, tmp_path: Path) -> None:
        result = await ValidateCodeHandler().execute(_step(), _java_project(tmp_path))

        assert "GreeterTest.java" in str(result.output.get("results")), result

    def test_lint_fix_fixes_the_task_file_when_target_is_a_folder(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        assert LintFixHandler()._fix_file(context, "src/") == tmp_path / _JAVA_FILE

    def test_lint_fix_refuses_a_file_target_outside(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        with pytest.raises(ValueError, match="outside the project"):
            LintFixHandler()._fix_file(context, "../x.py")

    @pytest.mark.asyncio
    async def test_drift_refuses_a_target_outside(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)
        step = _step(StepAction.DETECT, target="/etc/passwd", plan_path="plan.yaml")

        result = await DriftCheckHandler().execute(step, context)

        assert result.status == StepStatus.ERROR
        assert "outside the project" in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_drift_still_needs_an_explicit_target(self, tmp_path: Path) -> None:
        context = _java_project(tmp_path)

        result = await DriftCheckHandler().execute(
            _step(StepAction.DETECT, plan_path="plan.yaml"), context
        )

        assert result.status == StepStatus.ERROR
        assert "Missing 'target'" in (result.error_message or "")
