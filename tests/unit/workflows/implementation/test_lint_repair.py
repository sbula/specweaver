# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The model fixes lint errors through the implementation workflow, not inside the flow handler.

Proves: TECH-082 FR-4

`repair_lint` takes the adapter, its config and plain values, and returns the fixed text: the same
prompt the handler built, the fence stripped, the lineage tag kept. The handler keeps the loop,
the file write and the lineage log.

| Bucket | Case |
|---|---|
| Happy | the fenced reply comes back unfenced; the prompt names the language and every error |
| Boundary | no errors still asks once; untagged code gets no keep-the-tag line and no tag |
| Degradation | an adapter error propagates, so the handler can report it |
| Hostile | the model drops the tag → it is put back; returns another tag → kept, not doubled; an error without fields still makes a line |
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.commons.lineage import extract_artifact_uuid
from specweaver.workflows.implementation.lint_repair import repair_lint

if TYPE_CHECKING:
    from pathlib import Path

_UUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_OTHER = "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
_ERROR = {"file": "src/a.py", "line": 3, "code": "E501", "message": "line too long"}


@dataclass
class _Reply:
    text: str


class _Adapter:
    def __init__(self, reply: str = "x = 1\n", error: Exception | None = None) -> None:
        self.reply, self.error = reply, error
        self.calls: list[tuple[list[Any], Any]] = []

    async def generate(self, messages: list[Any], config: Any) -> _Reply:
        self.calls.append((messages, config))
        if self.error is not None:
            raise self.error
        return _Reply(self.reply)


def _prompt(adapter: _Adapter) -> str:
    return adapter.calls[0][0][-1].content


async def test_the_fenced_reply_comes_back_unfenced(tmp_path: Path) -> None:
    adapter = _Adapter("```python\nx = 1\n```")

    fixed = await repair_lint(adapter, "cfg", "x=1\n", [_ERROR], "python", tmp_path)

    assert fixed.strip() == "x = 1"
    assert adapter.calls[0][1] == "cfg"


async def test_the_prompt_names_the_language_and_every_error(tmp_path: Path) -> None:
    adapter = _Adapter()
    second = {"file": "src/a.py", "line": 9, "code": "F401", "message": "unused import"}

    await repair_lint(adapter, "cfg", "x=1\n", [_ERROR, second], "python", tmp_path)

    prompt = _prompt(adapter)
    assert "Fix the following lint errors in this Python file." in prompt
    assert "- src/a.py:3 [E501] line too long" in prompt
    assert "- src/a.py:9 [F401] unused import" in prompt
    assert "```python\nx=1\n\n```" in prompt


async def test_no_errors_still_asks_once(tmp_path: Path) -> None:
    adapter = _Adapter()

    await repair_lint(adapter, "cfg", "x=1\n", [], "python", tmp_path)

    assert len(adapter.calls) == 1


async def test_untagged_code_gets_no_tag(tmp_path: Path) -> None:
    adapter = _Adapter("x = 1\n")

    fixed = await repair_lint(adapter, "cfg", "x=1\n", [_ERROR], "python", tmp_path)

    assert "sw-artifact" not in _prompt(adapter)
    assert extract_artifact_uuid(fixed) is None


async def test_an_adapter_error_propagates(tmp_path: Path) -> None:
    adapter = _Adapter(error=RuntimeError("LLM kaput"))

    with pytest.raises(RuntimeError, match="LLM kaput"):
        await repair_lint(adapter, "cfg", "x=1\n", [_ERROR], "python", tmp_path)


async def test_a_dropped_tag_is_put_back(tmp_path: Path) -> None:
    code = f"# sw-artifact: {_UUID}\nx=1\n"
    adapter = _Adapter("x = 1\n")

    fixed = await repair_lint(adapter, "cfg", code, [_ERROR], "python", tmp_path)

    assert f"# sw-artifact: {_UUID}" in _prompt(adapter)
    assert fixed.startswith(f"# sw-artifact: {_UUID}\n")


async def test_another_tag_from_the_model_is_kept_not_doubled(tmp_path: Path) -> None:
    code = f"# sw-artifact: {_UUID}\nx=1\n"
    adapter = _Adapter(f"# sw-artifact: {_OTHER}\nx = 1\n")

    fixed = await repair_lint(adapter, "cfg", code, [_ERROR], "python", tmp_path)

    assert fixed.count("sw-artifact") == 1
    assert extract_artifact_uuid(fixed) == _OTHER


async def test_an_error_without_fields_still_makes_a_line(tmp_path: Path) -> None:
    adapter = _Adapter()

    await repair_lint(adapter, "cfg", "x=1\n", [{}], "rust", tmp_path)

    prompt = _prompt(adapter)
    assert "- ?:? [?] " in prompt
    assert "in this Rust file" in prompt
