# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test step and a lint step with no target work on the task's own files.

Proves: TECH-078 FR-1

| Bucket | Case |
|---|---|
| Happy | Python's `run_tests` runs `tests/test_<stem>.py`; `lint_fix` lints the task's code file |
| Boundary | a run whose `output_dir` is `src` (every door's run) still runs `tests/`; Java keeps its layout |
| Degradation | an explicit `target` is used as given |
| Hostile | not applicable — no input here comes from outside the project |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.handlers.qa_targets import default_test_target
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _python(root: Path) -> RunContext:
    (root / "greeter_spec.md").write_text("# Greeter\n")
    return RunContext(
        project_path=root, spec_path=root / "greeter_spec.md", output_dir=root / "src"
    )


def _java(root: Path) -> RunContext:
    (root / "pom.xml").write_text("<project><groupId>com.shop</groupId></project>\n")
    (root / "greeter_spec.md").write_text("# Greeter\n")
    return RunContext(
        project_path=root, spec_path=root / "greeter_spec.md", output_dir=root / "src"
    )


def test_python_runs_the_tests_where_generation_writes_them(tmp_path: Path) -> None:
    assert default_test_target(_python(tmp_path), "unit") == "tests/test_greeter.py"


def test_java_runs_its_task_test_file(tmp_path: Path) -> None:
    assert default_test_target(_java(tmp_path), "unit") == "src/test/java/com/shop/GreeterTest.java"


def _linted(context: RunContext, **params: Any) -> str:
    atom = MagicMock()
    atom.run.return_value = MagicMock(exports={"error_count": 0})
    step = PipelineStep(name="l", action=StepAction.LINT_FIX, target=StepTarget.CODE, params=params)
    handler = LintFixHandler()
    with patch.object(handler, "_get_atom", return_value=atom):
        import asyncio

        asyncio.run(handler.execute(step, context))
    return atom.run.call_args.args[0]["target"]


@pytest.mark.parametrize(
    ("build", "expected"),
    [(_python, "src/greeter.py"), (_java, "src/main/java/com/shop/Greeter.java")],
)
def test_lint_fix_without_target_lints_the_task_file(tmp_path: Path, build, expected) -> None:
    assert _linted(build(tmp_path)) == expected


def test_lint_fix_keeps_an_explicit_target(tmp_path: Path) -> None:
    assert _linted(_python(tmp_path), target="src/") == "src/"
