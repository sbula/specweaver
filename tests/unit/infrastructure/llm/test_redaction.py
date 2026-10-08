# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The redactor masks known secrets, whole, and nothing else.

Proves: E-INTL-01 FR-3

| Bucket | Case |
|---|---|
| Happy | a secret in a message is masked |
| Boundary | a secret that contains another is masked whole; a short value is not a secret |
| Degradation | a vault line without `=` or a comment is skipped |
| Hostile | a secret inside a nested tool result is masked; a streamed prompt is masked too |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role
from specweaver.infrastructure.llm.redaction import MASK, Redactor, vault_values

if TYPE_CHECKING:
    from pathlib import Path


def test_a_secret_in_a_message_is_masked() -> None:
    redactor = Redactor(["abcdefgh1234"])

    [message] = redactor.messages([Message(role=Role.USER, content="key abcdefgh1234!")])

    assert message.content == f"key {MASK}!"


def test_a_secret_containing_another_is_masked_whole() -> None:
    redactor = Redactor(["token-12345678", "token-12345678-extended"])

    assert redactor.text("x token-12345678-extended y") == f"x {MASK} y"


def test_a_short_value_is_not_a_secret() -> None:
    assert Redactor(["5432", "true"]).text("port 5432 true") == "port 5432 true"


def test_a_nested_tool_result_is_masked() -> None:
    redactor = Redactor(["abcdefgh1234"])

    result = redactor.payload({"files": [{"content": "abcdefgh1234"}], "count": 1})

    assert result == {"files": [{"content": MASK}], "count": 1}


def test_vault_comments_and_odd_lines_are_skipped(tmp_path: Path) -> None:
    (tmp_path / ".specweaver").mkdir()
    (tmp_path / ".specweaver" / "vault.env").write_text(
        '# TOKEN=not-this-one\nnonsense\nTOKEN="quoted-secret-1"\n', encoding="utf-8"
    )

    assert vault_values(tmp_path) == ["quoted-secret-1"]


class _Streams:
    provider_name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_stream(self, messages, _config):
        self.prompts.extend(m.content for m in messages)
        yield "ok"


async def test_a_streamed_prompt_is_masked() -> None:
    adapter = _Streams()
    collector = TelemetryCollector(adapter, "p", redactor=Redactor(["abcdefgh1234"]))
    config = GenerationConfig(model="m", max_output_tokens=10)

    async for _chunk in collector.generate_stream(
        [Message(role=Role.USER, content="abcdefgh1234")], config
    ):
        pass

    assert adapter.prompts == [MASK]
