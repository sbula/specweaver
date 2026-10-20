# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An agentic step iterates with tools, and cannot iterate for ever.

Proves: C-FLOW-11 FR-3, C-FLOW-11 FR-4, C-FLOW-11 FR-5, C-FLOW-11 NFR-2, C-FLOW-11 NFR-3

An agent loop is the shape that runs away. It is also the reason `B-FLOW-05` was built first: the
spend ceiling is one of this loop's two bounds, and without it "iterate until converged" is an
unbounded promise.

The other bound is turns — `[brake] agent_turns`, the adapter's round limit — and both are needed.
Spend alone cannot stop a loop calling cheap tools; turns alone cannot stop ten costly calls.
"""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.core.flow.engine.work_unit import (
    InProcessAgentRuntime,
    WorkUnit,
    WorkUnitResult,
)
from specweaver.infrastructure.llm.budget import BudgetExceededError
from specweaver.infrastructure.llm.errors import ToolRoundsExceededError
from specweaver.infrastructure.llm.models import LLMResponse, ToolCall


class _Dispatcher:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def available_tools(self) -> list[Any]:
        return []

    async def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.executed.append(name)
        return {"ok": True}


class _Adapter:
    """Stands in for an adapter whose own tool loop has already run; records what it was given."""

    def __init__(self, answer: LLMResponse | Exception) -> None:
        self._answer = answer
        self.calls: list[tuple[Any, Any, Any]] = []

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any = None, on_tool_round: Any = None
    ) -> LLMResponse:
        self.calls.append((messages, config, tool_executor))
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer


def _unit(**kwargs: Any) -> WorkUnit:
    return WorkUnit(instructions="write src/greeter.py", **kwargs)


async def test_one_tool_loop_runs_and_its_answer_comes_back() -> None:
    """FR-3: the adapter's tool loop is the iteration, given the coder's tools."""
    dispatcher = _Dispatcher()
    adapter = _Adapter(LLMResponse(text="written", model="stub"))

    result = await InProcessAgentRuntime(adapter, dispatcher, config="cfg").run(
        _unit(context="the spec")
    )

    assert result == WorkUnitResult(output="written")
    ((messages, config, executor),) = adapter.calls
    assert executor is dispatcher
    assert config == "cfg"
    assert [m["role"] for m in messages] == ["system", "user"]


async def test_the_runtime_runs_no_tools_of_its_own() -> None:
    """AD-2: the adapter runs the tools; a second loop here would run them twice and add a
    second turn limit."""
    dispatcher = _Dispatcher()
    pending = LLMResponse(text="", model="stub", tool_calls=[ToolCall(name="read_file", args={})])

    await InProcessAgentRuntime(_Adapter(pending), dispatcher).run(_unit())

    assert dispatcher.executed == []


async def test_the_round_limit_stops_the_unit() -> None:
    """FR-4: `[brake] agent_turns` is the one turn limit, and reaching it is not swallowed."""
    adapter = _Adapter(ToolRoundsExceededError.reached(3))

    with pytest.raises(ToolRoundsExceededError, match="agent_turns"):
        await InProcessAgentRuntime(adapter, _Dispatcher()).run(_unit())


async def test_a_spent_budget_stops_the_unit_rather_than_being_retried() -> None:
    """FR-4's other bound, NFR-3: the spend limit is independent of the turns."""
    adapter = _Adapter(BudgetExceededError("this run has spent $9.99 of $9.99", setting="x"))

    with pytest.raises(BudgetExceededError):
        await InProcessAgentRuntime(adapter, _Dispatcher()).run(_unit())


async def test_the_runtime_is_replaceable() -> None:
    """FR-5. The binding decision stays open: a second runtime is a class, not a rewrite."""

    class _StubRuntime:
        async def run(self, unit: WorkUnit) -> WorkUnitResult:
            return WorkUnitResult(output="stubbed")

    from specweaver.core.flow.engine.work_unit import AgentRuntime

    runtime: AgentRuntime = _StubRuntime()

    assert (await runtime.run(_unit())).output == "stubbed"
