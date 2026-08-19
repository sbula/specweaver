# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A module's DAL decides the validate step's verdict, not just the CLI's exit code.

Proves: TECH-067 FR-1, TECH-067 FR-2

`seed_dal_level` resolves a module's DAL onto `context.isolation` when the runner starts, and
`test_runner_dal_injection.py` proves that. `ValidateCodeHandler` then called
`execute_validation_flow` without it and counted only FAILs, so code from `sw implement` was
validated at the packaged default strictness whatever its `context.yaml` declared — a `DAL_A` module
judged exactly like a `DAL_E` one.

`sw check` never had this gap because it applies strictness at the summary, where a WARN under a
strict DAL becomes exit 1. This is that rule, at the step verdict, so the two paths agree.

**The lenient run is the load-bearing half.** A handler that failed every step with a warning would
satisfy a strict-only assertion perfectly. Both runs use one source file and one project layout; the
only difference is the `dal_level` line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

CONTEXT = """module: widget
purpose: Adds two numbers.
archetype: pure-logic
operational:
  dal_level: {dal}
"""

SOURCE = '''"""A widget."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''

#: Named for the archetype the resolver picks from `context.yaml`, because the handler loads
#: `validation_code_<archetype>` and falls back to the default. Naming it `validation_code_default`
#: instead makes `extends` self-referential, which raises inside the fallback that was meant to
#: catch it — the step then ERRORs and both assertions below pass for the wrong reason.
LEAN_PIPELINE = """name: validation_code_pure-logic
type: validation_pipeline
extends: validation_code_default
target: code
remove:
  - c05_import_direction
"""


def _project(tmp_path: Path, dal: str) -> Path:
    """A minimal real project whose only variable is the declared DAL."""
    project = tmp_path / f"proj_{dal.lower()}"
    (project / "src").mkdir(parents=True)
    (project / "src" / "context.yaml").write_text(CONTEXT.format(dal=dal), encoding="utf-8")
    (project / "src" / "widget.py").write_text(SOURCE, encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_widget.py").write_text(
        "def test_add():\n    assert True\n", encoding="utf-8"
    )
    pipelines = project / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True)
    (pipelines / "validation_code_pure-logic.yaml").write_text(LEAN_PIPELINE, encoding="utf-8")
    # Named for the module, not "spec": C02 derives the expected test file from the SPEC stem, so a
    # `spec.md` makes it look for `test_spec.py` and FAIL — and any FAIL fails the step whatever the
    # strictness, which would make the strict assertion below pass without the DAL doing anything.
    (project / "widget.md").write_text("# Widget\n", encoding="utf-8")
    return project


async def _verdict(tmp_path: Path, dal: str):
    from specweaver.core.config.dal_resolver import DALResolver

    project = _project(tmp_path, dal)
    context = RunContext(project_path=project, spec_path=project / "widget.md")
    resolved = DALResolver(project).resolve(project / "src" / "widget.py")
    assert resolved is not None, f"the fixture's {dal} was not resolved — the test proves nothing"
    context.isolation = context.isolation.model_copy(update={"dal_level": resolved})

    step = PipelineStep(
        name="validate_code",
        action=StepAction.VALIDATE,
        target=StepTarget.CODE,
        params={"target": "src/widget.py"},
    )
    return await ValidateCodeHandler().execute(step, context)


async def test_a_lenient_dal_lets_the_step_pass(tmp_path: Path) -> None:
    """The control. Without it, a handler failing everything would read as correct."""
    result = await _verdict(tmp_path, "DAL_E")

    assert result.status == StepStatus.PASSED, result.output


async def test_a_strict_dal_fails_the_step_on_the_same_code(tmp_path: Path) -> None:
    result = await _verdict(tmp_path, "DAL_A")

    assert result.status == StepStatus.FAILED, result.output


async def test_the_two_runs_produce_the_same_findings(tmp_path: Path) -> None:
    """Same warnings, opposite verdicts — which is what enforcing a DAL has to mean.

    If the strict run had produced an extra finding, the verdict would move for a reason that is not
    the DAL at all, and the pair above would pass while proving something else.
    """
    lenient = (await _verdict(tmp_path, "DAL_E")).output
    strict = (await _verdict(tmp_path, "DAL_A")).output

    def warns(output: dict) -> int:
        return sum(1 for r in output["results"] if r["status"] == "warn")

    assert warns(strict) == warns(lenient) > 0
    assert strict["total"] == lenient["total"]
