# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.drift import DriftCheckHandler, _load_plan
from specweaver.core.flow.run_state.run_context import RunContext


@pytest.mark.asyncio
async def test_drift_handler_execute_returns_error_on_unicode_decode(tmp_path: Path) -> None:
    # 1. Setup
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text("""
spec_path: file.md
spec_name: name
spec_hash: hash
timestamp: "2026-04-01T00:00:00Z"
tasks: []
file_layout: []
""")
    target_path = tmp_path / "binary.bin"
    target_path.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8

    context = RunContext(project_path=tmp_path, spec_path=plan_path, db=MagicMock())
    step = MagicMock()
    step.params = {"target_path": str(target_path), "plan_path": str(plan_path), "analyze": False}

    handler = DriftCheckHandler()

    # 2. Execute
    result = await handler.execute(step, context)

    # 3. Assert
    assert result.status == StepStatus.ERROR
    assert "valid UTF-8" in result.error_message


@pytest.mark.asyncio
async def test_drift_handler_execute_returns_success_on_polyglot_unsupported(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text("""
spec_path: file.md
spec_name: name
spec_hash: hash
timestamp: "2026-04-01T00:00:00Z"
tasks: []
file_layout: []
""")
    target_path = tmp_path / "script.ts"  # TypeScript file!
    target_path.write_text("console.log('hello');")

    context = RunContext(project_path=tmp_path, spec_path=plan_path, db=MagicMock())
    step = MagicMock()
    step.params = {"target_path": str(target_path), "plan_path": str(plan_path), "analyze": False}

    handler = DriftCheckHandler()

    result = await handler.execute(step, context)

    # Should safely skip parsing TS and return PASSED with 0 drift
    assert result.status == StepStatus.PASSED
    assert result.output["is_drifted"] is False


def test_drift_handler_load_plan_raises_exception_on_invalid_yaml(tmp_path: Path) -> None:
    plan_path = tmp_path / "invalid.yaml"
    plan_path.write_text("spec_path: \n  - dict\nspec_name: 123[]\n")  # Bad schema

    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _load_plan(str(plan_path))


def test_the_drift_handler_asks_no_model_itself() -> None:
    """Proves: TECH-082 FR-2. The model call lives in validation orchestration's `explain_drift`."""
    import inspect

    from specweaver.core.flow.handlers import drift

    source = inspect.getsource(drift)

    assert ".generate(" not in source
    assert "explain_drift" in source


@pytest.mark.asyncio
async def test_no_model_for_the_analysis_is_reported_not_raised(
    monkeypatch, tmp_path: Path
) -> None:
    from specweaver.core.flow.handlers import drift

    def no_model(*_a, **_k):
        raise RuntimeError("no model configured for review")

    monkeypatch.setattr(drift, "llm_for_step", no_model)
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "plan.yaml", db=MagicMock())

    text = await DriftCheckHandler()._analyze_drift(
        context, MagicMock(), MagicMock(findings=[]), "a.py"
    )

    assert text == "LLM analysis failed: no model configured for review"
