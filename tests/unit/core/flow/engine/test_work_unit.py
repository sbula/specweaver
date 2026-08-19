# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An agentic step iterates with tools, and cannot iterate for ever.

Proves: C-FLOW-11 FR-3, C-FLOW-11 FR-4, C-FLOW-11 FR-5

An agent loop is the shape that runs away. It is also the reason `B-FLOW-05` was built first: the
spend ceiling is one of this loop's two bounds, and without it "iterate until converged" is an
unbounded promise.

The other bound is turns, and both are needed. Spend alone cannot stop a loop calling cheap tools
with no LLM call between them; turns alone cannot stop ten calls that each cost a fortune.
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
from specweaver.infrastructure.llm.models import LLMResponse, ToolCall


class _Dispatcher:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def available_tools(self) -> list[Any]:
        return []

    async def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.executed.append(name)
        return {"ok": True}


class _ScriptedLLM:
    """Answers with a fixed sequence: tool calls, then a final answer."""

    def __init__(self, *turns: list[ToolCall]) -> None:
        self._turns = list(turns)
        self.calls = 0

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any = None, on_tool_round: Any = None
    ) -> LLMResponse:
        self.calls += 1
        pending = self._turns.pop(0) if self._turns else []
        return LLMResponse(text="done", model="stub", tool_calls=list(pending))


def _unit(**kwargs: Any) -> WorkUnit:
    return WorkUnit(instructions="do the thing", **kwargs)


async def test_a_work_unit_that_needs_no_tools_returns_immediately() -> None:
    llm = _ScriptedLLM()

    result = await InProcessAgentRuntime(llm, _Dispatcher()).run(_unit())

    assert isinstance(result, WorkUnitResult)
    assert result.converged is True
    assert result.turns == 1


async def test_a_work_unit_iterates_while_the_agent_calls_tools() -> None:
    """FR-3. Iteration is the capability; a runtime that stops after one turn is the oneshot
    handler with extra ceremony."""
    dispatcher = _Dispatcher()
    llm = _ScriptedLLM([ToolCall(name="read_file", args={})], [])

    result = await InProcessAgentRuntime(llm, dispatcher).run(_unit())

    assert dispatcher.executed == ["read_file"]
    assert result.turns == 2
    assert result.converged is True


async def test_the_loop_stops_at_the_turn_ceiling() -> None:
    """FR-4. The agent never says it is finished, which is exactly the runaway case."""
    forever = [ToolCall(name="read_file", args={})]
    llm = _ScriptedLLM(*[forever] * 50)

    result = await InProcessAgentRuntime(llm, _Dispatcher(), max_turns=4).run(_unit())

    assert result.turns == 4
    assert result.converged is False


def test_the_turn_ceiling_cannot_be_disabled() -> None:
    """The control for FR-4. An unbounded ceiling is the failure dressed as a configuration."""
    with pytest.raises(ValueError, match="max_turns"):
        InProcessAgentRuntime(_ScriptedLLM(), _Dispatcher(), max_turns=0)


async def test_a_spent_budget_stops_the_loop_rather_than_being_retried() -> None:
    """FR-4's other bound. The budget lives in the adapter, so the runtime must let its error out
    instead of treating it as a turn that failed."""

    class _BrokeLLM:
        calls = 0

        async def generate_with_tools(self, *args: Any, **kwargs: Any) -> LLMResponse:
            raise BudgetExceededError("this run has spent $9.99 of $9.99", setting="max_spend_usd")

    with pytest.raises(BudgetExceededError):
        await InProcessAgentRuntime(_BrokeLLM(), _Dispatcher()).run(_unit())


async def test_the_runtime_is_replaceable() -> None:
    """FR-5. The binding decision stays open: a second runtime is a class, not a rewrite."""

    class _StubRuntime:
        async def run(self, unit: WorkUnit) -> WorkUnitResult:
            return WorkUnitResult(output="stubbed", turns=1, converged=True)

    from specweaver.core.flow.engine.work_unit import AgentRuntime

    runtime: AgentRuntime = _StubRuntime()

    assert (await runtime.run(_unit())).output == "stubbed"
