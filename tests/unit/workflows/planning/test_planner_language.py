# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The planner tells the model the project's language.

Proves: TECH-078 FR-5

| Bucket | Case |
|---|---|
| Happy | the system prompt says "for a Rust project" when told Rust |
| Boundary | Python still reads "for a Python project" |
| Degradation | not applicable — the name is a plain string the handler resolves |
| Hostile | a planner built without a language is refused: no silent Python default |
"""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.infrastructure.llm.models import Role
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder
from specweaver.workflows.planning.planner import Planner
from tests.scripted_llm import TEST_CONFIG
from tests.unit.workflows.planning.test_planner import FakeLLM, _valid_plan_json


async def _system_prompt(language: str) -> str:
    llm = FakeLLM([_valid_plan_json()])
    planner = Planner(llm, config=TEST_CONFIG, language=language)
    await planner.generate_plan(
        spec_content="# Login",
        spec_path="specs/login_spec.md",
        spec_name="Login",
        base_prompt=PromptBuilder(),
    )
    messages: list[Any] = llm.messages_log[0]
    return next(m.content for m in messages if m.role == Role.SYSTEM)


@pytest.mark.asyncio
async def test_the_planner_names_rust(tmp_path: Any) -> None:
    prompt = await _system_prompt("Rust")

    assert "for a Rust project" in prompt
    assert "Python" not in prompt


@pytest.mark.asyncio
async def test_python_is_named_as_before() -> None:
    assert "for a Python project" in await _system_prompt("Python")


def test_a_planner_without_a_language_is_refused() -> None:
    with pytest.raises(TypeError, match="language"):
        Planner(FakeLLM([]), config=TEST_CONFIG)  # type: ignore[call-arg]
