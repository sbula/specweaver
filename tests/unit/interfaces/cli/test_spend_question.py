# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The spend question: only "yes" spends, it never mixes into stdout, and Ctrl-D is a "no".

Proves: B-FLOW-05 FR-6

| Bucket | Case |
|---|---|
| Happy | "y" goes on |
| Boundary | an empty answer is a "no" |
| Degradation | end of input (Ctrl-D) is a "no", not an error |
| Hostile | the question goes to stderr, so `sw run --json` output stays parseable |
"""

from __future__ import annotations

import io

import pytest

from specweaver.interfaces.cli import _core


@pytest.mark.parametrize(("typed", "spends"), [("y\n", True), ("yes\n", True), ("\n", False)])
def test_only_yes_spends(monkeypatch, typed: str, spends: bool) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(typed))

    assert _core.ask_to_spend("crossed") is spends


def test_end_of_input_is_a_no(monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    assert _core.ask_to_spend("crossed") is False


def test_the_question_goes_to_stderr(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))

    _core.ask_to_spend("brake.tokens_per_run would be crossed")

    captured = capsys.readouterr()
    assert "brake.tokens_per_run" not in captured.out
    assert "brake.tokens_per_run" in captured.err
