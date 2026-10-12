# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run_tests step runs a generated test that imports its module by name, in any project.

Proves: D-VAL-05 FR-3

`generate_tests` writes `from greet import hi`; a project made by `sw init` has no pytest settings
that put `src/` on the import path. Real pytest, no mocks.

| Bucket | Case |
|---|---|
| Happy | the generated test imports `src/greet.py` and passes |
| Boundary | a failing assertion still fails the step: the path fix hides nothing |
| Degradation | not applicable — a missing module is the next case's error |
| Hostile | not applicable — the files are the run's own |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _run(tmp_path: Path, expected: str):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / "src" / "greet.py").write_text(
        'def hi() -> str:\n    return "hi"\n', encoding="utf-8"
    )
    (tmp_path / "tests" / "test_greet.py").write_text(
        f'from greet import hi\n\n\ndef test_hi() -> None:\n    assert hi() == "{expected}"\n',
        encoding="utf-8",
    )
    spec = tmp_path / "specs" / "greet_spec.md"
    spec.write_text("# Greet\n", encoding="utf-8")
    step = PipelineStep(
        name="run_tests",
        action=StepAction.VALIDATE,
        target=StepTarget.TESTS,
        params={"target": "tests/test_greet.py", "kind": "unit"},
    )
    context = RunContext(project_path=tmp_path, spec_path=spec, output_dir=tmp_path / "src")
    return asyncio.run(ValidateTestsHandler().execute(step, context))


def test_the_generated_test_finds_its_module(tmp_path: Path) -> None:
    result = _run(tmp_path, "hi")

    assert result.status is StepStatus.PASSED, (result.error_message, result.output)


def test_a_wrong_result_still_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, "bye")

    assert result.status is StepStatus.FAILED
    assert result.output.get("failed") == 1, result.output
