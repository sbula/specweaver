# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A bounded agent loop, and the seam that lets a different one be dropped in.

`ExecutionMode.AGENTIC` needs something that iterates. This is that something, kept behind
`AgentRuntime` because *which* agent runtime SpecWeaver should stand on is an open strategic
question and building it into the dial would answer it by accident.

The shipped implementation hands the coder's tools to the run's own LLM adapter, whose tool loop
stops at `[brake] agent_turns`. That adapter is already wrapped by `TelemetryCollector`, so the
run's spend limits apply here with no extra wiring.

An external agent CLI is a legitimate second runtime but not the first one: `_CREDENTIAL_VARS`
strips every provider key from sandboxed children on purpose, so a subprocess runtime would need a
deliberate hole in that control before it could authenticate at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkUnit:
    """What an agentic step is asked to do."""

    instructions: str
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkUnitResult:
    """What the agent said when it stopped asking for tools."""

    output: str


class AgentRuntime(Protocol):
    """Anything that can run a work unit to completion or to a bound."""

    async def run(self, unit: WorkUnit) -> WorkUnitResult: ...


class InProcessAgentRuntime:
    """Gives the run's LLM adapter the coder's tools and lets its tool loop run once.

    Two bounds, both outside this class: the adapter's round limit (`[brake] agent_turns`) stops
    cheap tool calls without end, and the run's spend limits stop costly ones. Neither error is
    caught here — a stopped loop ends the step, it is not a turn that merely failed.
    """

    def __init__(self, llm: Any, dispatcher: Any, *, config: Any = None) -> None:
        self._llm = llm
        self._dispatcher = dispatcher
        self._config = config

    async def run(self, unit: WorkUnit) -> WorkUnitResult:
        messages: list[Any] = [{"role": "user", "content": unit.instructions}]
        if unit.context:
            messages.insert(0, {"role": "system", "content": unit.context})
        response = await self._llm.generate_with_tools(messages, self._config, self._dispatcher)
        return WorkUnitResult(output=getattr(response, "text", ""))
