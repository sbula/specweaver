# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Double the LLM and nothing else, so everything downstream of it is the real thing.

Imported explicitly rather than provided as a fixture, on purpose: the import line is the only
place a reader can see that a test doubles the model. `TECH-017` spent a boundary discovering that
`INT-US-24`'s e2e doubles `GenerateCodeHandler` itself — a fact recorded only in its docstring, and
one that changed a verdict once it was read. Doubling should be visible at the call site.

> [!CAUTION]
> **`scripted_world` patches two things and both are load-bearing.** Patching only the adapter
> factory leaves `ModelRouter.get_for_task` free to build a **real provider** from the registry,
> bypassing the patch entirely — a live API call inside a test that reads as mocked. That was found
> for real in `INT-US-02`'s e2e. Anything that copies or re-implements this must carry both.

Extracted from `test_feature_decomposition_e2e.py` by `TECH-017` SF-04 CB-1, where it had been
file-local; that suite's 24 scenarios are the proof the extraction is faithful.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from specweaver.infrastructure.llm.models import LLMResponse

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
def scripted_world(llm: ScriptedLLM) -> Iterator[None]:
    """Only the LLM is doubled. Everything downstream of it is the real thing."""
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.factory.create_llm_adapter",
                return_value=(settings_mock(), llm, MagicMock()),
            )
        )
        # Without this the router builds a REAL provider adapter from the registry, bypassing the
        # factory patch entirely — a live API call inside a "mocked" test (vacuous-proof pattern 5,
        # found for real in INT-US-02's e2e). None makes handlers fall back to context.model.llm.
        stack.enter_context(
            patch(
                "specweaver.infrastructure.llm.router.ModelRouter.get_for_task",
                return_value=None,
            )
        )
        yield
