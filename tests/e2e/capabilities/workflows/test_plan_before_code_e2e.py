# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A plan is decided and saved before code is written, and the code is written against it.

Proves: D-INTL-03 FR-1
Proves: D-INTL-03 FR-2
Proves: D-INTL-03 FR-3

Real `sw run`, real plan and code steps; only the model's text is scripted.

| Bucket | Case |
|---|---|
| Happy | the plan file appears beside the spec, and the code prompt carries its file layout |
| Boundary | `new_feature` plans after the spec review and before any code step |
| Degradation | a model that never returns a valid plan fails the step and no code is written |
| Hostile | not applicable: the plan is the model's own output, validated by its schema |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_PLAN = {
    "spec_path": "x",
    "spec_name": "x",
    "spec_hash": "x",
    "timestamp": "2026-10-13T00:00:00Z",
    "file_layout": [
        {"path": "src/greeter/hello_core.py", "action": "create", "purpose": "the greeting"}
    ],
    "confidence": 80,
}

_PIPELINE = """name: plan_then_code
steps:
  - name: plan_spec
    action: plan
    target: spec
    gate:
      type: auto
      condition: completed
      on_fail: abort
  - name: generate_code
    action: generate
    target: code
"""


class _Model:
    def __init__(self, plan_reply: str) -> None:
        self.plan_reply = plan_reply
        self.code_prompts: list[str] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: list[Any], config: Any) -> LLMResponse:
        text = str(messages[-1].content if messages else "")
        if "implementation planner" in str(messages):
            return LLMResponse(text=self.plan_reply, model="m")
        self.code_prompts.append(text)
        return LLMResponse(
            text="def greet(name: str) -> str:\n    return f'Hello, {name}'\n", model="m"
        )


def _project(tmp_path: Path) -> Path:
    assert runner.invoke(app, ["init", "greet", "--path", str(tmp_path)]).exit_code == 0
    (tmp_path / "specs" / "greeter_spec.md").write_text(
        "# Greeter\n\n## 1. Purpose\n\nGreets a person by name.\n", encoding="utf-8"
    )
    (tmp_path / "plan_then_code.yaml").write_text(_PIPELINE, encoding="utf-8")
    return tmp_path


def _run(project: Path, model: _Model) -> Any:
    with doubled_llm(model):
        return runner.invoke(
            app,
            [
                "run",
                str(project / "plan_then_code.yaml"),
                "specs/greeter_spec.md",
                "--project",
                str(project),
            ],
        )


def test_the_code_is_written_against_the_saved_plan(tmp_path: Path) -> None:
    # Proves: D-INTL-03 FR-2
    project = _project(tmp_path)
    model = _Model(json.dumps(_PLAN))

    result = _run(project, model)

    assert result.exit_code == 0, result.output
    plan = project / "specs" / "greeter_spec_plan.yaml"
    assert plan.is_file()
    assert "src/greeter/hello_core.py" in plan.read_text(encoding="utf-8")
    assert model.code_prompts
    assert "src/greeter/hello_core.py" in model.code_prompts[0]


def test_new_feature_plans_after_the_review_and_before_any_code() -> None:
    # Proves: D-INTL-03 FR-1
    from pathlib import Path

    from specweaver.core.flow.engine.models import StepAction, StepTarget
    from specweaver.core.flow.engine.parser import load_pipeline

    steps = load_pipeline(Path("new_feature")).steps
    kinds = [(step.action, step.target) for step in steps]
    plan = kinds.index((StepAction.PLAN, StepTarget.SPEC))
    review = kinds.index((StepAction.REVIEW, StepTarget.SPEC))
    first_code = min(i for i, (action, _) in enumerate(kinds) if action == StepAction.GENERATE)
    assert review < plan < first_code


def test_no_valid_plan_means_no_code(tmp_path: Path) -> None:
    # Proves: D-INTL-03 FR-3
    project = _project(tmp_path)
    model = _Model("not json at all")

    result = _run(project, model)

    assert result.exit_code == 1, result.output
    assert not model.code_prompts
    assert not (project / "specs" / "greeter_spec_plan.yaml").exists()
