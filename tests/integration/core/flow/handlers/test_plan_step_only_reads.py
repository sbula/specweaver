# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The plan step's model can read the project but change nothing in it.

Proves: D-INTL-03 FR-2

A plan decides what to write; writing is the code step's job. Found 2026-10-14: the plan step
built its tools for the implementer role, so the planner was offered add, replace and delete symbol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.generation import PlanSpecHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

_WRITES = {"add_symbol", "replace_symbol", "replace_symbol_body", "delete_symbol"}


async def test_the_planner_is_offered_no_write_tool(tmp_path: Path) -> None:
    # Proves: D-INTL-03 FR-2
    spec = tmp_path / "greeter_spec.md"
    spec.write_text("# Greeter\n\n## 1. Purpose\n\nGreets.\n", encoding="utf-8")
    adapter = MagicMock()
    adapter.generate_with_tools = MagicMock()
    context = RunContext(
        project_path=tmp_path, spec_path=spec, model=ModelAccess(llm_router=FixedRouter(adapter))
    )
    seen: dict[str, set[str]] = {}

    def capture(*args, tool_dispatcher=None, **kwargs):  # type: ignore[no-untyped-def]
        seen["tools"] = {t.name for t in tool_dispatcher.available_tools()}
        raise RuntimeError("stop after the tools are built")

    step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)
    with patch("specweaver.workflows.planning.planner.Planner.__init__", side_effect=capture):
        await PlanSpecHandler().execute(step, context)

    assert "read_file" in seen["tools"]
    assert not seen["tools"] & _WRITES, seen["tools"] & _WRITES
