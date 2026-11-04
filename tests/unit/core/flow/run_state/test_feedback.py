# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step's loop-back findings are sent and taken out through one pair of functions.

Proves: TECH-082 FR-12

| Bucket | Case |
|---|---|
| Happy | findings sent to a step are popped once, with who sent them; a second pop gives None |
| Boundary | an empty dict gives None; another step's entry is left alone; a context with no feedback gives None |
| Degradation | an entry with no `findings`, or with non-dict findings, is popped and gives None |
| Hostile | an entry that is not a dict is popped and gives None |
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from specweaver.core.flow.run_state.feedback import pop_findings, send_findings


def _context(feedback: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(feedback={} if feedback is None else feedback)


def test_sent_findings_are_popped_once() -> None:
    context = _context()

    send_findings(context, "draft", "review", {"verdict": "fix"})

    assert context.feedback == {"draft": {"from_step": "review", "findings": {"verdict": "fix"}}}
    assert pop_findings(context, "draft") == {"verdict": "fix"}
    assert pop_findings(context, "draft") is None
    assert context.feedback == {}


def test_a_new_send_replaces_the_old_entry() -> None:
    context = _context()

    send_findings(context, "draft", "review", {"round": 1})
    send_findings(context, "draft", "lint", {"round": 2})

    assert context.feedback["draft"] == {"from_step": "lint", "findings": {"round": 2}}


def test_an_empty_feedback_gives_none() -> None:
    assert pop_findings(_context(), "draft") is None


def test_another_steps_entry_is_left_alone() -> None:
    other = {"from_step": "review", "findings": {"a": 1}}
    context = _context({"other": other})

    assert pop_findings(context, "draft") is None
    assert context.feedback == {"other": other}


def test_a_context_without_feedback_gives_none() -> None:
    assert pop_findings(SimpleNamespace(), "draft") is None


@pytest.mark.parametrize(
    "entry",
    [{"from_step": "review"}, {"findings": ["not", "a", "dict"]}, {"findings": None}],
)
def test_an_entry_without_dict_findings_is_popped_and_gives_none(entry: dict) -> None:
    context = _context({"draft": entry})

    assert pop_findings(context, "draft") is None
    assert "draft" not in context.feedback


@pytest.mark.parametrize("entry", ["not-a-dict", ["findings"], 3, None])
def test_an_entry_that_is_not_a_dict_is_popped_and_gives_none(entry: object) -> None:
    context = _context({"draft": entry})

    assert pop_findings(context, "draft") is None
    assert "draft" not in context.feedback


def test_a_dropped_malformed_entry_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    context = _context({"draft": {"findings": "not-a-dict"}})

    with caplog.at_level("WARNING"):
        assert pop_findings(context, "draft") is None

    assert [r.getMessage() for r in caplog.records] == [
        "feedback for step 'draft' is malformed; it is dropped"
    ]


def test_no_entry_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        assert pop_findings(_context({"other": {"findings": {}}}), "draft") is None

    assert caplog.records == []
