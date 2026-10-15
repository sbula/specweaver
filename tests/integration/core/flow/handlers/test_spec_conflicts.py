# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A spec review checks the spec against the project's other specs and contracts, and names each conflict.

Proves: B-FLOW-01 FR-20

The real review step over a real project; the scripted model reads with its real file tools.

| Bucket | Case |
|---|---|
| Happy | two specs disagree on behaviour: the reviewer reads the other spec, names the conflict, the review is denied |
| Boundary | a project with no other spec: the map says so, and an accepted review stays accepted |
| Degradation | a conflict whose quote is not in the file it names stays a warning and does not deny |
| Hostile | a contract method declared twice with different parameters denies even when the model saw nothing; a path outside the project proves nothing |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.review import ReviewSpecHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.models import LLMResponse
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_GREET = """# Greet

## 1. Purpose

Greets a person by name.

## Functional Requirements

| FR-91 | Empty name | an empty name raises ValueError |
"""

_WELCOME = """# Welcome Banner

## 1. Purpose

Shows the welcome banner, built from the greeting.

## Functional Requirements

| FR-91 | Empty name | an empty name returns an empty string |
"""

_REAL = (
    'CONFLICT: specs/welcome_spec.md says "an empty name returns an empty string", '
    'this spec says "an empty name raises ValueError"'
)


class _Reviewer:
    """A model that reads the other spec with its tools, then answers."""

    model = "scripted-1"

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompt = ""
        self.read: Any = None

    async def generate(self, messages: Any, config: Any = None) -> LLMResponse:
        self.prompt = "\n".join(m.content for m in messages)
        return LLMResponse(text=self.answer, model=self.model)

    async def generate_with_tools(
        self, messages: Any, config: Any, dispatcher: Any, **_: Any
    ) -> LLMResponse:
        self.read = await dispatcher.execute("read_file", {"path": "specs/welcome_spec.md"})
        return await self.generate(messages, config)


def _project(tmp_path: Path, **specs: str) -> RunContext:
    (tmp_path / "specs").mkdir()
    for name, text in {"greet_spec.md": _GREET, **specs}.items():
        (tmp_path / "specs" / name).write_text(text, encoding="utf-8")
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "greet_spec.md")


async def _review(context: RunContext, model: _Reviewer) -> Any:
    context.model = ModelAccess(llm_router=FixedRouter(model))
    step = PipelineStep(name="review_spec", action=StepAction.REVIEW, target=StepTarget.SPEC)
    return await ReviewSpecHandler().execute(step, context)


def _messages(result: Any) -> list[str]:
    return [f["message"] for f in result.output["findings"]]


@pytest.mark.asyncio
async def test_a_behaviour_conflict_found_by_reading_denies(tmp_path: Path) -> None:
    model = _Reviewer(f"VERDICT: ACCEPTED\n- {_REAL}\nOtherwise fine.")

    result = await _review(_project(tmp_path, **{"welcome_spec.md": _WELCOME}), model)

    assert "specs/welcome_spec.md" in model.prompt and "Welcome Banner" in model.prompt
    assert "Empty name" in model.prompt.split("specs/welcome_spec.md", 1)[1]
    assert "an empty name returns an empty string" in json.dumps(model.read)
    assert result.status == StepStatus.FAILED
    assert result.output["verdict"] == "denied"
    assert any(m.startswith("CONFLICT:") for m in _messages(result))


@pytest.mark.asyncio
async def test_a_lone_spec_stays_accepted(tmp_path: Path) -> None:
    model = _Reviewer("VERDICT: ACCEPTED\nFine.")

    result = await _review(_project(tmp_path), model)

    assert result.status == StepStatus.PASSED
    assert "no other spec" in model.prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invented",
    [
        'CONFLICT: specs/welcome_spec.md says "an empty name is ignored silently"',
        'CONFLICT: specs/missing_spec.md says "an empty name returns an empty string"',
        'CONFLICT: ../../etc/passwd says "root"',
    ],
    ids=["quote-not-there", "file-missing", "outside-project"],
)
async def test_an_unproven_conflict_does_not_deny(tmp_path: Path, invented: str) -> None:
    model = _Reviewer(f"VERDICT: ACCEPTED\n- {invented}\nFine.")

    result = await _review(_project(tmp_path, **{"welcome_spec.md": _WELCOME}), model)

    assert result.status == StepStatus.PASSED
    assert any("UNPROVEN" in m for m in _messages(result))


@pytest.mark.asyncio
async def test_a_contract_signature_clash_denies_on_its_own(tmp_path: Path) -> None:
    contract = "\n## 2. Contract\n\n```python\ndef greet(name: str) -> str:\n    ...\n```\n"
    other = "# Other\n\n## 2. Contract\n\n```python\ndef greet(name: str, loud: bool) -> str:\n    ...\n```\n"
    context = _project(tmp_path, **{"other_spec.md": other})
    context.spec_path.write_text(_GREET + contract, encoding="utf-8")

    result = await _review(context, _Reviewer("VERDICT: ACCEPTED\nFine."))

    assert result.output["verdict"] == "denied"
    clash = [m for m in _messages(result) if m.startswith("CONFLICT:")]
    assert clash and "greet" in clash[0] and "specs/other_spec.md" in clash[0]


@pytest.mark.asyncio
async def test_the_map_lists_spec_files_only_and_keeps_entries_short(tmp_path: Path) -> None:
    long_purpose = "# Long\n\n## 1. Purpose\n\n" + "word " * 2000 + "\n"
    context = _project(tmp_path, **{"long_spec.md": long_purpose, "notes.md": "x" * 40_000})
    model = _Reviewer("VERDICT: ACCEPTED\nFine.")

    await _review(context, model)

    other_specs = model.prompt.split("specs/long_spec.md", 1)[1].split("requirements:", 1)[0]
    assert len(other_specs) < 300
    assert "notes.md" not in model.prompt
