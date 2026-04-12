# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow._drift import DriftCheckHandler, _load_plan
from specweaver.core.flow.runner import RunContext
from specweaver.core.flow.state import StepStatus


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


@pytest.mark.asyncio
async def test_drift_handler_analyze_drift_logic(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    from specweaver.core.flow.runner import RunContext
    from specweaver.assurance.validation.models import DriftFinding, DriftReport, Severity

    class MockConfig:
        llm = "mock_config_llm"

    mock_llm = MagicMock()

    class MockGen:
        text = "Mock root cause"

    mock_llm.generate = AsyncMock(return_value=MockGen())

    context = RunContext(
        project_path=tmp_path, spec_path=tmp_path / "plan.yaml", db=MagicMock(), config=MockConfig()
    )  # type: ignore
    context.llm = mock_llm

    report = DriftReport(
        is_drifted=True,
        findings=[
            DriftFinding(
                severity=Severity.ERROR,
                node_type="function",
                description="Bad signature",
                expected_signature="exp",
                actual_signature="act",
            )
        ],
    )

    handler = DriftCheckHandler()
    result = await handler._analyze_drift(context, report, "src/drifted.py")

    assert "Mock root cause" in result
    mock_llm.generate.assert_called_once()
