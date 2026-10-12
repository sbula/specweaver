# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A review's tool-round callback reaches the tool loop.

Proves: E-INTL-03 FR-4

The handlers pass `on_tool_round` to add mentioned files between rounds; the reviewer must hand it
to `generate_with_tools`, for a spec review and a code review alike.

| Bucket | Case |
|---|---|
| Happy | a spec review and a code review pass the callback on |
| Boundary | no callback: the loop gets None |
| Degradation | not applicable — the callback is passed, not called, here |
| Hostile | not applicable — no input crosses a trust boundary |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder
from specweaver.workflows.review.reviewer import Reviewer
from tests.scripted_llm import TEST_CONFIG

if TYPE_CHECKING:
    from pathlib import Path


class _Llm:
    def __init__(self) -> None:
        self.on_tool_round: Any = "never called"

    async def generate_with_tools(self, _messages, _config, _dispatcher, *, on_tool_round=None):
        self.on_tool_round = on_tool_round
        return LLMResponse(text="VERDICT: ACCEPTED\nfine", model="m")


class _Dispatcher:
    def available_tools(self) -> list[Any]:
        return []


def _callback(_round: int, _messages: list[Any]) -> None:
    return None


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path]:
    spec = tmp_path / "a_spec.md"
    spec.write_text("# A\n", encoding="utf-8")
    code = tmp_path / "a.py"
    code.write_text("x = 1\n", encoding="utf-8")
    return spec, code


@pytest.mark.parametrize("kind", ["spec", "code"])
async def test_the_callback_reaches_the_tool_loop(files: tuple[Path, Path], kind: str) -> None:
    llm = _Llm()
    reviewer = Reviewer(llm=llm, config=TEST_CONFIG, tool_dispatcher=_Dispatcher())
    spec, code = files

    if kind == "spec":
        await reviewer.review_spec(spec, PromptBuilder(), on_tool_round=_callback)
    else:
        await reviewer.review_code(code, spec, PromptBuilder(), on_tool_round=_callback)

    assert llm.on_tool_round is _callback


async def test_no_callback_gives_the_loop_none(files: tuple[Path, Path]) -> None:
    llm = _Llm()
    reviewer = Reviewer(llm=llm, config=TEST_CONFIG, tool_dispatcher=_Dispatcher())

    await reviewer.review_spec(files[0], PromptBuilder())

    assert llm.on_tool_round is None
