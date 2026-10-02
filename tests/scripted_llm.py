# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Double the LLM and nothing else, so everything downstream of it is the real thing.

Imported explicitly rather than provided as a fixture, on purpose: the import line is the only
place a reader can see that a test doubles the model. `TECH-017` spent a boundary discovering that
`INT-US-24`'s e2e doubles `GenerateCodeHandler` itself — a fact recorded only in its docstring, and
one that changed a verdict once it was read. Doubling should be visible at the call site.

> [!CAUTION]
> **`scripted_world` patches the one path every model call takes: `RoleResolver`.** Commands, the
> router and the REST API all get their adapters from it (C-FLOW-13), so one patch covers them all.
> The old setup needed two, because the router could build a **real provider** past a patched
> factory — a live API call inside a test that read as mocked (`INT-US-02`'s e2e). With one path
> that hole is closed by construction; do not add a second way to build an adapter.

Extracted from `test_feature_decomposition_e2e.py` by `TECH-017` SF-04 CB-1, where it had been
file-local; that suite's 24 scenarios are the proof the extraction is faithful.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse
from specweaver.infrastructure.llm.router import RouterResult

if TYPE_CHECKING:
    from collections.abc import Iterator


class ScriptedLLM:
    """Returns queued payloads in order, and counts calls so `INT-US-21` NFR-3 (LLM economy) is
    assertable.

    The story id is spelled out because this module names several — a bare `NFR-3` here would be
    ambiguous and credit nothing (`TECH-017`, the citation-grammar rule). The extraction dropped
    this citation on its first pass and `check_nfr_sweep` caught it as a regression of 1.

    The last payload repeats once the queue is exhausted, so a test that drives more calls than it
    scripted degrades to a stuck answer rather than an `IndexError` — the failure then shows up as
    the assertion that actually matters instead of as a crash in the double.
    """

    def __init__(self, payloads: list[str]) -> None:
        self._payloads = list(payloads)
        self.calls = 0

    async def generate(
        self, messages: Any, config: Any = None, *args: Any, **kwargs: Any
    ) -> LLMResponse:
        idx = min(self.calls, len(self._payloads) - 1)
        self.calls += 1
        return LLMResponse(text=self._payloads[idx], model="scripted-1")

    async def generate_with_tools(
        self, messages: Any, config: Any, dispatcher: Any, **kwargs: Any
    ) -> LLMResponse:
        return await self.generate(messages, config)


def settings_mock() -> MagicMock:
    """Settings shaped like the real ones, with a REAL `SandboxSettings` rather than a mock.

    The sandbox block is read for actual decisions (isolation, execution mode), so a `MagicMock`
    there yields truthy values for every knob and silently turns policies on.
    """
    from specweaver.core.config.settings import SandboxSettings

    settings = MagicMock()
    settings.llm.model = "scripted-1"
    settings.llm.temperature = 0.2
    settings.llm.max_output_tokens = 4096
    settings.sandbox = SandboxSettings()
    return settings


@contextlib.contextmanager
def doubled_llm(adapter: Any, model: str = "test-model", **settings: Any) -> Iterator[Any]:
    """Every role resolves to `adapter`: the one place adapters come from (`RoleResolver`) is doubled.

    Commands, the router and the REST API all take their adapters from the resolver, so this one
    patch covers every path a model call can take. The run flushes `adapter` if it has a flush.
    Yields the generation settings every role gets.
    """
    from specweaver.infrastructure.llm.resolve import RoleResolver

    config = GenerationConfig(model=model, **({"max_output_tokens": 4096} | settings))

    def _for_role(_resolver: Any, _role: str) -> tuple[Any, GenerationConfig]:
        return adapter, config

    # A bare AsyncMock has an awaitable `flush` the run would call without awaiting: not a collector.
    flush = getattr(adapter, "flush", None)
    flushable = [adapter] if flush is not None and not isinstance(flush, AsyncMock) else []
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(RoleResolver, "for_role", _for_role))
        stack.enter_context(patch.object(RoleResolver, "require", lambda _resolver, _roles: None))
        stack.enter_context(patch.object(RoleResolver, "collectors", lambda _resolver: flushable))
        yield config


@contextlib.contextmanager
def scripted_world(llm: ScriptedLLM) -> Iterator[None]:
    """Only the LLM is doubled. Everything downstream of it is the real thing."""
    with doubled_llm(llm, model="scripted-1"):
        yield


class FixedRouter:
    """A router that answers every task type with one adapter — for tests that build a
    `RunContext` by hand. Production runs get theirs from `RoleResolver`."""

    def __init__(self, adapter: Any, model: str = "test-model", **settings: Any) -> None:
        self.adapter = adapter
        self.config = GenerationConfig(model=model, **({"max_output_tokens": 4096} | settings))

    def get_for_task(self, task_type: Any) -> RouterResult:
        return RouterResult(adapter=self.adapter, config=self.config)

    def collectors(self) -> list[Any]:
        return [self.adapter] if hasattr(self.adapter, "flush") else []


#: Generation settings for tests that build a workflow class by hand. Production code gets its
#: settings from the resolver; there is no default model to fall back on.
TEST_CONFIG = GenerationConfig(model="test-model", max_output_tokens=4096)
