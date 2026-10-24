# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`validate_code` judges a non-Python file on its tests when no archetype brings rules.

Proves: TECH-078 FR-3

| Bucket | Case |
|---|---|
| Happy | a Kotlin file is judged by C02 and C03 only |
| Boundary | Python keeps every default rule |
| Degradation | a language with no test convention is still judged by no rule |
| Hostile | the Python-only rules (syntax, type hints) never judge a Kotlin file |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler

if TYPE_CHECKING:
    from pathlib import Path

_STEP = PipelineStep(name="v", action=StepAction.VALIDATE, target=StepTarget.CODE)


async def _rules_run(root: Path, code: str) -> set[str]:
    path = root / code
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n")
    spec = root / "orders_spec.md"
    spec.write_text("# Orders\n")
    context = RunContext(project_path=root, spec_path=spec)
    with patch(
        "specweaver.core.flow.handlers.validation_hydrator.hydrate_code_validation_context",
        return_value={},
    ):
        result = await ValidateCodeHandler().execute(
            _STEP.model_copy(update={"params": {"target": code}}), context
        )
    return {r["rule_id"] for r in result.output.get("results", [])}


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["src/main/kotlin/Orders.kt", "src/orders.js", "src/orders.rs"])
async def test_a_non_python_file_is_judged_by_c02_and_c03(tmp_path: Path, code: str) -> None:
    assert await _rules_run(tmp_path, code) == {"C02", "C03"}


@pytest.mark.asyncio
async def test_python_keeps_every_default_rule(tmp_path: Path) -> None:
    rules = await _rules_run(tmp_path, "src/orders.py")

    assert {"C01", "C02", "C03", "C08"} <= rules


@pytest.mark.asyncio
async def test_go_is_judged_by_no_rule(tmp_path: Path) -> None:
    assert await _rules_run(tmp_path, "main.go") == set()


@pytest.mark.asyncio
async def test_the_rules_judge_the_code_file_not_the_spec(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_widget.py").write_text("def test_w():\n    pass\n")
    path = tmp_path / "src" / "widget.py"
    path.parent.mkdir()
    path.write_text("x = 1\n")
    (tmp_path / "orders_spec.md").write_text("# Orders\n")
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "orders_spec.md")
    with patch(
        "specweaver.core.flow.handlers.validation_hydrator.hydrate_code_validation_context",
        return_value={},
    ):
        result = await ValidateCodeHandler().execute(
            _STEP.model_copy(update={"params": {"target": "src/widget.py"}}), context
        )

    c02 = next(r for r in result.output["results"] if r["rule_id"] == "C02")
    assert c02["status"] == "pass", c02
