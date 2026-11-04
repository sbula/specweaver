# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The arbitration workflow turns the failure evidence and a prompt into a verdict.

Proves: TECH-082 FR-5

`arbitrate` takes the adapter, its config and the prompt text, and returns an `ArbitrateResult`:
one user message, the JSON found in the reply, the raw reply kept. The handler keeps the prompt
build, the trace filter and the routing.

| Bucket | Case |
|---|---|
| Happy | a JSON reply gives its verdict and keeps the raw text; the prompt goes as one user message |
| Boundary | JSON inside prose is found; evidence with no failure text gives the errors-only line |
| Degradation | an adapter error propagates; a plain string reply is read |
| Hostile | a reply with no JSON raises `UnreadableVerdictError` naming it; an unknown verdict raises `ValidationError` |
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from specweaver.infrastructure.llm.models import Role
from specweaver.workflows.arbitration.verdict import (
    ArbitrateResult,
    ArbitrateVerdict,
    UnreadableVerdictError,
    arbitrate,
    evidence_text,
    guard_coding_feedback,
)


@dataclass
class _Reply:
    text: str


class _Adapter:
    def __init__(self, reply: Any = None, error: Exception | None = None) -> None:
        self.reply, self.error = reply, error
        self.calls: list[tuple[list[Any], Any]] = []

    async def generate(self, messages: list[Any], config: Any) -> Any:
        self.calls.append((messages, config))
        if self.error is not None:
            raise self.error
        return self.reply


async def test_a_json_reply_gives_its_verdict() -> None:
    raw = '{"verdict": "code_bug", "spec_clause": "FR-1", "coding_feedback": "fix it"}'
    adapter = _Adapter(_Reply(raw))

    result = await arbitrate(adapter, "cfg", "the prompt")

    assert result.verdict == ArbitrateVerdict.CODE_BUG
    assert result.spec_clause == "FR-1"
    assert result.raw_response == raw


async def test_the_prompt_goes_as_one_user_message() -> None:
    adapter = _Adapter(_Reply('{"verdict": "scenario_error"}'))

    await arbitrate(adapter, "cfg", "the prompt")

    messages, config = adapter.calls[0]
    assert [(m.role, m.content) for m in messages] == [(Role.USER, "the prompt")]
    assert config == "cfg"


async def test_json_inside_prose_is_found() -> None:
    adapter = _Adapter(
        _Reply('My verdict:\n{"verdict": "spec_ambiguity", "spec_clause": "FR-2"}\nDone.')
    )

    result = await arbitrate(adapter, "cfg", "p")

    assert result.verdict == ArbitrateVerdict.SPEC_AMBIGUITY
    assert result.raw_response.startswith("My verdict:")


def test_failures_become_evidence_lines() -> None:
    failures = [
        {"nodeid": "t.py::a", "message": "boom", "stacktrace": "frame-a"},
        {"nodeid": "t.py::b", "message": "bang", "stacktrace": ""},
    ]

    assert (
        evidence_text(failures, errors=0, total=2)
        == "t.py::a: boom\nframe-a\n\nt.py::b: bang\n\n\n"
    )


def test_no_failure_text_gives_the_errors_only_line() -> None:
    assert evidence_text([], errors=3, total=7) == (
        "3 collection/execution error(s) out of 7 scenario tests; "
        "no per-test failure details available."
    )


async def test_an_adapter_error_propagates() -> None:
    adapter = _Adapter(error=RuntimeError("model down"))

    with pytest.raises(RuntimeError, match="model down"):
        await arbitrate(adapter, "cfg", "p")


async def test_a_plain_string_reply_is_read() -> None:
    adapter = _Adapter('{"verdict": "code_bug"}')

    result = await arbitrate(adapter, "cfg", "p")

    assert result.verdict == ArbitrateVerdict.CODE_BUG


async def test_a_reply_with_no_json_raises_naming_it() -> None:
    adapter = _Adapter(_Reply("not json at all"))

    with pytest.raises(UnreadableVerdictError, match="not json at all") as caught:
        await arbitrate(adapter, "cfg", "p")

    assert caught.value.raw == "not json at all"
    assert isinstance(caught.value, ValueError)


async def test_an_unknown_verdict_raises() -> None:
    adapter = _Adapter(_Reply('{"verdict": "blame_the_moon"}'))

    with pytest.raises(ValidationError):
        await arbitrate(adapter, "cfg", "p")


class TestArbitrateVerdict:
    def test_all_verdict_values(self):
        vals = [v.value for v in ArbitrateVerdict]
        assert "code_bug" in vals
        assert "scenario_error" in vals
        assert "spec_ambiguity" in vals


class TestArbitrateResult:
    def test_model_validation(self):
        data = {
            "verdict": "code_bug",
            "reasoning": "Reason",
            "spec_clause": "FR-1",
            "coding_feedback": "Code invalid",
            "scenario_feedback": "Test invalid",
        }
        res = ArbitrateResult(**data)
        assert res.verdict == ArbitrateVerdict.CODE_BUG
        assert res.reasoning == "Reason"


class TestVocabularyGuard:
    def test_clean_feedback_unchanged(self):
        val = "Function x does not return integer."
        assert guard_coding_feedback(val) == val

    def test_leaked_scenario_term_triggers_fallback(self):
        val = "The scenario test failed"
        assert "behave according to the behavioral constraints" in guard_coding_feedback(val)

    def test_case_insensitive_detection(self):
        val = "Pytest parametrized variables are missing"
        assert "behave according to the behavioral constraints" in guard_coding_feedback(val)
