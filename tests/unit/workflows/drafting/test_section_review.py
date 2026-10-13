# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""After the model writes a section, the person keeps it, asks for a change, or skips it.

Proves: E-INTL-02 FR-2

| Bucket | Case |
|---|---|
| Happy | Enter keeps the section; a typed change rewrites it with the change and the old text |
| Boundary | several changes in a row; `skip` after a rewrite leaves a TODO |
| Degradation | a provider without a terminal keeps every section, one model call each |
| Hostile | `SKIP` in capitals skips; a change is never mistaken for the new section text |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from rich.console import Console

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.hitl_provider import HITLProvider
from specweaver.workflows.drafting.drafter import Drafter
from specweaver.workspace.context.provider import ContextProvider
from tests.scripted_llm import TEST_CONFIG

if TYPE_CHECKING:
    from pathlib import Path


class _Person(ContextProvider):
    """Answers every question, then gives one scripted verdict per shown section."""

    def __init__(self, verdicts: list[str]) -> None:
        self.verdicts = list(verdicts)
        self.shown: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return "person"

    async def ask(self, question: str, *, section: str = "") -> str:
        return f"answer for {section}"

    async def review(self, section: str, text: str) -> str:
        self.shown.append((section, text))
        return self.verdicts.pop(0) if self.verdicts else ""


class _Headless(ContextProvider):
    @property
    def name(self) -> str:
        return "headless"

    async def ask(self, question: str, *, section: str = "") -> str:
        return f"answer for {section}"


def _llm(*texts: str) -> AsyncMock:
    llm = AsyncMock()
    replies = [LLMResponse(text=t, model="m") for t in texts]
    llm.generate.side_effect = lambda *a, **k: (
        replies.pop(0) if replies else LLMResponse(text="later", model="m")
    )
    return llm


async def _draft(tmp_path: Path, person: ContextProvider, llm: AsyncMock) -> str:
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

    drafter = Drafter(
        base_prompt=PromptBuilder(), llm=llm, context_provider=person, config=TEST_CONFIG
    )
    path = await drafter.draft("greeter", tmp_path)
    return path.read_text(encoding="utf-8")


def _purpose(spec: str) -> str:
    return spec.split("## 1. Purpose", 1)[1].split("## 2.", 1)[0]


async def test_enter_keeps_the_section(tmp_path: Path) -> None:
    # Proves: E-INTL-02 FR-2
    person = _Person([""])
    spec = await _draft(tmp_path, person, _llm("first purpose"))

    assert "first purpose" in _purpose(spec)
    assert person.shown[0] == ("Purpose", "first purpose")


async def test_a_typed_change_rewrites_the_section_with_it(tmp_path: Path) -> None:
    # Proves: E-INTL-02 FR-2
    person = _Person(["say it greets in German too", ""])
    llm = _llm("first purpose", "purpose with German")

    spec = await _draft(tmp_path, person, llm)

    assert "purpose with German" in _purpose(spec)
    assert "first purpose" not in spec
    rewrite_prompt = llm.generate.call_args_list[1].args[0][0].content
    assert "say it greets in German too" in rewrite_prompt
    assert "first purpose" in rewrite_prompt
    assert person.shown[1] == ("Purpose", "purpose with German")


async def test_skip_after_a_rewrite_leaves_a_todo(tmp_path: Path) -> None:
    person = _Person(["shorter", "SKIP"])
    spec = await _draft(tmp_path, person, _llm("first purpose", "short purpose"))

    assert "TODO: Fill in Purpose section." in _purpose(spec)
    assert "short purpose" not in spec


async def test_several_changes_in_a_row(tmp_path: Path) -> None:
    person = _Person(["a", "b", ""])
    llm = _llm("v1", "v2", "v3")
    spec = await _draft(tmp_path, person, llm)

    assert "v3" in _purpose(spec)
    assert [text for section, text in person.shown if section == "Purpose"] == ["v1", "v2", "v3"]


async def test_a_provider_without_a_terminal_keeps_every_section(tmp_path: Path) -> None:
    # Proves: E-INTL-02 FR-2
    llm = _llm()
    spec = await _draft(tmp_path, _Headless(), llm)

    assert llm.generate.call_count == len(Drafter.SECTIONS)
    assert "TODO" not in spec


async def test_the_terminal_shows_the_section_and_reads_the_answer(monkeypatch) -> None:
    # Proves: E-INTL-02 FR-2
    console = Console(record=True, width=120)
    monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a, **k: "  make it shorter  ")

    answer = await HITLProvider(console=console).review("Purpose", "The greeter greets.")

    assert answer == "make it shorter"
    shown = console.export_text()
    assert "Purpose" in shown
    assert "The greeter greets." in shown
