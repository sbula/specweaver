# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration test for generation loopback feedback propagation.

Verifies that human feedback parked in the pipeline context reliably
travels through Flow Engine hooks out into the Generator API and
finally into the formatted LLM adapter string payload.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from specweaver.core.flow._base import RunContext
from specweaver.core.flow.models import PipelineDefinition, StepAction, StepTarget
from specweaver.core.flow.runner import PipelineRunner
from specweaver.core.flow.state import RunStatus, StepStatus

if TYPE_CHECKING:
    from pathlib import Path


def test_generation_feedback_loopback_e2e(tmp_path: Path) -> None:
    """Verifies feedback is fully mapped from context to prompt string via the actual Flow Handlers."""
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Test Spec\n", encoding="utf-8")

    # Construct the base pipeline for code gen
    pipeline = PipelineDefinition.create_single_step(
        name="gen_code_step",
        action=StepAction.GENERATE,
        target=StepTarget.CODE,
        description="Loopback target",
    )

    # We provide a mock adapter directly on context
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(
        return_value=MagicMock(
            text="```python\ndef pass_test(): pass\n```", finish_reason=1, parsed=None
        )
    )

    context = RunContext(
        project_path=tmp_path, spec_path=spec_path, output_dir=tmp_path / "src", llm=mock_llm
    )
    context.run_id = "test-e2e-run"
    context.db = MagicMock()

    # 1. Inject the parsed hitl feedback structure matching loop_back output
    context.feedback = {
        "gen_code_step": {
            "findings": {
                "hitl_verdict": "reject",
                "remarks": "Change this UI to dark mode exactly.",
                "results": [{"status": "FAIL", "rule_id": "TEST1", "message": "Fails edge case"}],
            }
        }
    }

    # 2. Run the actual engine (using real GenerateCodeHandler internally)
    with patch(
        "specweaver.core.loom.commons.git.executor.GitExecutor.run", return_value=(0, "", "")
    ):
        runner = PipelineRunner(pipeline, context)
        run_state = asyncio.run(runner.run())

    # 3. Assert Runner completed successfully
    assert run_state.status == RunStatus.COMPLETED
    assert len(run_state.step_records) == 1
    assert run_state.step_records[0].status == StepStatus.PASSED

    # 4. Assert LLM was called with the assembled string via the real PromptBuilder
    mock_llm.generate.assert_called_once()
    call_args = mock_llm.generate.call_args
    messages = call_args[0][0]
    prompt_string = messages[-1].content

    # 5. E2E verification of formatting payload parsing
    assert "<dictator-overrides>" in prompt_string
    assert "Change this UI to dark mode exactly." in prompt_string
    assert '<context label="validation_errors">' in prompt_string
    assert "[TEST1] Fails edge case" in prompt_string

    # 6. Verify Context memory was flushed correctly to prevent infinite loop
    assert "gen_code_step" not in context.feedback
