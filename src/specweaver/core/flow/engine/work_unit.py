# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A bounded agent loop, and the seam that lets a different one be dropped in.

`ExecutionMode.AGENTIC` needs something that iterates. This is that something, kept behind
`AgentRuntime` because *which* agent runtime SpecWeaver should stand on is an open strategic
question and building it into the dial would answer it by accident.

The shipped implementation drives the run's own LLM adapter in a tool loop. That adapter is
already wrapped by `TelemetryCollector`, so the run's spend ceiling applies here with no extra
wiring.

An external agent CLI is a legitimate second runtime but not the first one: `_CREDENTIAL_VARS`
strips every provider key from sandboxed children on purpose, so a subprocess runtime would need a
deliberate hole in that control before it could authenticate at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TURNS = 10


@dataclass(frozen=True)
class WorkUnit:
    """What an agentic step is asked to do."""

    instructions: str
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkUnitResult:
    """What it produced, and whether it finished or was cut off.

    `converged=False` is not an error — the output is still gated like any other step's. It
    records that the agent was still working when a bound stopped it, which is the difference
    between *this is done* and *this is as far as the budget went*.
    """

    output: str
    turns: int
    converged: bool


class AgentRuntime(Protocol):
    """Anything that can run a work unit to completion or to a bound."""

    async def run(self, unit: WorkUnit) -> WorkUnitResult: ...


class InProcessAgentRuntime:
    """Drives the run's LLM adapter in a tool loop until it stops asking for tools.

    Two bounds, and both are load-bearing. Turns stop a loop that calls cheap tools forever
    without the spend ceiling ever noticing; the spend ceiling stops ten turns that each cost a
    fortune. Either alone leaves the other case open.
    """

    def __init__(
        self,
        llm: Any,
        dispatcher: Any,
        *,
        config: Any = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
    ) -> None:
        if max_turns < 1:
            raise ValueError(
                f"max_turns must be at least 1, got {max_turns}. An agent loop without a turn "
                "ceiling is the runaway this capability exists to bound."
            )
        self._llm = llm
        self._dispatcher = dispatcher
        self._config = config
        self._max_turns = max_turns

    async def run(self, unit: WorkUnit) -> WorkUnitResult:
        """Iterate until the agent stops requesting tools, or a bound stops it.

        `BudgetExceededError` is deliberately not caught: the spend ceiling ends the run, and
        swallowing it here would turn a tripped breaker into a turn that merely failed.
        """
        messages: list[Any] = [{"role": "user", "content": unit.instructions}]
        if unit.context:
            messages.insert(0, {"role": "system", "content": unit.context})

        response: Any = None
        for turn in range(1, self._max_turns + 1):
            response = await self._llm.generate_with_tools(messages, self._config, self._dispatcher)
            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                return WorkUnitResult(
                    output=getattr(response, "text", ""), turns=turn, converged=True
                )

            for call in calls:
                result = await self._dispatcher.execute(call.name, call.args)
                messages.append({"role": "tool", "content": str(result)})

        logger.warning(
            "Work unit hit its turn ceiling of %d without converging; output is gated as usual",
            self._max_turns,
        )
        return WorkUnitResult(
            output=getattr(response, "text", ""), turns=self._max_turns, converged=False
        )
