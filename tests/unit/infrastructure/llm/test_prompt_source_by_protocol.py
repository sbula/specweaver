# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`add_context` knows a prompt source by its protocol, not by probing for attributes.

Proves: TECH-088 FR-10

| Bucket | Case |
|---|---|
| Happy | a `TopologyContext`, a `FilePromptAdapter` and a small class with both methods are added as sources |
| Boundary | a string still goes in as string context |
| Degradation | — the check reads no file and calls no service |
| Hostile | an object with only one of the two methods, `None`, a bare `MagicMock` and an object with both methods set on the instance, not its class, are refused with `TypeError` on every Python version; no `hasattr(` is left in `adders.py` |
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from specweaver.commons.topology_context import TopologyContext
from specweaver.infrastructure.llm.prompt.adapter import FilePromptAdapter
from specweaver.infrastructure.llm.prompt.builder import PromptBuilder

_ADDERS = Path(__file__).resolve().parents[4] / "src/specweaver/infrastructure/llm/prompt/adders.py"


class _BothMethods:
    def get_prompt_content(self, char_limit: int | None = None) -> str:
        return "<context>both</context>"

    def get_prompt_label(self) -> str:
        return "both"


class _ContentOnly:
    def get_prompt_content(self, char_limit: int | None = None) -> str:
        return "<context>half</context>"


class _LabelOnly:
    def get_prompt_label(self) -> str:
        return "half"


def _labels(builder: PromptBuilder) -> list[str]:
    return [block.label for block in builder._blocks]


def test_sources_that_meet_the_protocol_are_added(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("# spec\n", encoding="utf-8")
    builder = PromptBuilder()

    builder.add_context(TopologyContext("billing", "bills", "adapter", "direct dependency"))
    builder.add_context(FilePromptAdapter(spec, label="spec"))
    builder.add_context(_BothMethods())

    assert _labels(builder) == ["billing", "spec", "both"]


def test_a_string_is_still_string_context() -> None:
    builder = PromptBuilder().add_context("plain text", "note")

    assert _labels(builder) == ["note"]


def _methods_on_the_instance() -> object:
    source = SimpleNamespace()
    source.get_prompt_content = lambda char_limit=None: "<context>x</context>"
    source.get_prompt_label = lambda: "x"
    return source


# Python 3.11 checks a runtime Protocol with hasattr, so a MagicMock passed it there and not on 3.12+.
@pytest.mark.parametrize(
    "source", [_ContentOnly(), _LabelOnly(), None, MagicMock(), _methods_on_the_instance()]
)
def test_anything_else_is_refused(source: object) -> None:
    with pytest.raises(TypeError, match="PromptContentSource"):
        PromptBuilder().add_context(source)


def test_add_context_probes_no_attribute() -> None:
    tree = ast.parse(_ADDERS.read_text(encoding="utf-8"))
    probes = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "hasattr"
    ]

    assert probes == []
