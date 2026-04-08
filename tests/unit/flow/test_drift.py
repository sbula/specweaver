# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the flow drift handler."""

from pathlib import Path
from typing import Any

import pytest

from specweaver.flow._base import RunContext
from specweaver.flow._drift import DriftCheckHandler
from specweaver.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.flow.state import StepStatus


@pytest.fixture
def plan_yaml_content() -> str:
    return """
spec_path: "specs/test_spec.md"
spec_name: "Test"
spec_hash: "123"
timestamp: "2026-01-01T00:00:00Z"
file_layout:
  - path: "src/test.py"
    action: "create"
    purpose: "Test file"
tasks:
  - sequence_number: 1
    name: "Task 1"
    description: "Do it"
    files: ["src/test.py"]
    dependencies: []
    expected_signatures:
      "src/test.py":
        - name: "my_func"
          parameters: ["x", "y"]
          return_type: "int"
"""


@pytest.mark.asyncio
async def test_drift_handler_no_target_path(tmp_path: Path) -> None:
    """Test handler fails if target_path not provided."""
    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check", action=StepAction.DETECT, target=StepTarget.DRIFT, params={}
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")

    result = await handler.execute(step, context)
    assert result.status == StepStatus.ERROR
    assert "target_path" in result.error_message


@pytest.mark.asyncio
async def test_drift_handler_no_plan_path(tmp_path: Path) -> None:
    """Test handler fails if plan_path not provided."""
    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        params={"target_path": "src/test.py"},
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")

    result = await handler.execute(step, context)
    assert result.status == StepStatus.ERROR
    assert "plan_path" in result.error_message


@pytest.mark.asyncio
async def test_drift_handler_success(tmp_path: Path, plan_yaml_content: str) -> None:
    """Test handler succeeds without drift."""
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_yaml_content)

    src_file = tmp_path / "src" / "test.py"
    src_file.parent.mkdir()
    src_file.write_text("def my_func(x, y) -> int:\n    return x + y\n")

    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        params={
            "target_path": str(src_file),
            "plan_path": str(plan_file),
        },
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")

    result = await handler.execute(step, context)
    print(f"DEBUG: {result.error_message}")
    assert result.status == StepStatus.PASSED
    assert result.output["drift_count"] == 0


class MockLLMResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class MockLLMAdapter:
    async def generate(
        self, messages: list[Any], config: Any = None, tool_dispatcher: Any = None
    ) -> Any:
        return MockLLMResponse("The parameter `z` in `my_func` is a typo and should be `y`.")


@pytest.mark.asyncio
async def test_drift_handler_analyze(tmp_path: Path, plan_yaml_content: str) -> None:
    """Test handler flags drift and invokes LLM when requested."""
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_yaml_content)

    src_file = tmp_path / "src" / "test.py"
    src_file.parent.mkdir()
    # INTENTIONAL DRIFT: Missing `my_func` entirely to cause ERROR
    src_file.write_text("def unrelated_func() -> int:\n    return 0\n")

    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        params={"target_path": str(src_file), "plan_path": str(plan_file), "analyze": True},
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")
    context.llm = MockLLMAdapter()

    result = await handler.execute(step, context)
    assert result.status == StepStatus.FAILED
    assert result.output["drift_count"] > 0
    assert result.output["is_drifted"] is True
    assert "llm_root_cause" in result.output
    assert "typo" in result.output["llm_root_cause"]


@pytest.mark.asyncio
async def test_drift_handler_invalid_plan(tmp_path: Path) -> None:
    """Test handler catches invalid plan gracefully."""
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text("]]invalid yaml[[")

    src_file = tmp_path / "src" / "test.py"
    src_file.parent.mkdir()
    src_file.write_text("def my_func():\n    pass\n")

    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        params={"target_path": str(src_file), "plan_path": str(plan_file)},
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")

    result = await handler.execute(step, context)
    assert result.status == StepStatus.ERROR
    assert "Failed to load PlanArtifact" in result.error_message


@pytest.mark.asyncio
async def test_drift_handler_non_utf8_target(tmp_path: Path, plan_yaml_content: str) -> None:
    """Test handler catches non-UTF8 target code."""
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_yaml_content)

    src_file = tmp_path / "src" / "test.py"
    src_file.parent.mkdir()
    src_file.write_bytes(bytes.fromhex("fefffeff"))

    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        params={"target_path": str(src_file), "plan_path": str(plan_file)},
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")

    result = await handler.execute(step, context)
    assert result.status == StepStatus.ERROR
    assert "not valid UTF-8" in result.error_message


@pytest.mark.asyncio
async def test_drift_handler_ast_parse_failure(
    tmp_path: Path, plan_yaml_content: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test handler catches Tree-Sitter parsing failure."""
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_yaml_content)

    src_file = tmp_path / "src" / "test.py"
    src_file.parent.mkdir()
    src_file.write_text("def my_func(): pass")

    # Mock TreeSitter to raise Exception during parse
    def mock_parse(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Mock parse error")

    import tree_sitter

    monkeypatch.setattr(tree_sitter.Parser, "parse", mock_parse)

    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        params={"target_path": str(src_file), "plan_path": str(plan_file)},
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")

    result = await handler.execute(step, context)
    assert result.status == StepStatus.ERROR
    assert "Failed to parse AST" in result.error_message


class FailingLLMAdapter:
    async def generate(
        self, messages: list[Any], config: Any = None, tool_dispatcher: Any = None
    ) -> Any:
        raise RuntimeError("API Timeout")


@pytest.mark.asyncio
async def test_drift_handler_analyze_failure(tmp_path: Path, plan_yaml_content: str) -> None:
    """Test handler handles LLM API failure gracefully."""
    plan_file = tmp_path / "plan.yaml"
    plan_file.write_text(plan_yaml_content)

    src_file = tmp_path / "src" / "test.py"
    src_file.parent.mkdir()
    src_file.write_text("def unrelated_func() -> int:\\n    return 0\\n")

    handler = DriftCheckHandler()
    step = PipelineStep(
        name="drift_check",
        action=StepAction.DETECT,
        target=StepTarget.DRIFT,
        params={"target_path": str(src_file), "plan_path": str(plan_file), "analyze": True},
    )
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md")
    context.llm = FailingLLMAdapter()

    result = await handler.execute(step, context)
    assert result.status == StepStatus.FAILED
    assert result.output["is_drifted"] is True
    assert "llm_root_cause" in result.output
    assert "LLM analysis failed: API Timeout" in result.output["llm_root_cause"]
