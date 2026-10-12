# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Known secrets masked before anything is sent to a model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from specweaver.infrastructure.llm.models import Message

MASK = "***RESTRICTED***"

#: Shorter values (a port, a flag like "true") would match ordinary text everywhere.
_MIN_SECRET_LENGTH = 8


class Redactor:
    """Replaces every known secret with `MASK`, in text, messages and tool results."""

    def __init__(self, secrets: Iterable[str]) -> None:
        kept = {value.strip() for value in secrets if len(value.strip()) >= _MIN_SECRET_LENGTH}
        # Longest first, so a secret that contains another is masked whole.
        self._secrets = sorted(kept, key=len, reverse=True)

    def text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, MASK)
        return text

    def payload(self, payload: Any) -> Any:
        if isinstance(payload, str):
            return self.text(payload)
        if isinstance(payload, dict):
            return {key: self.payload(value) for key, value in payload.items()}
        if isinstance(payload, list):
            return [self.payload(item) for item in payload]
        return payload

    def messages(self, messages: list[Message]) -> list[Message]:
        if not self._secrets:
            return messages
        return [m.model_copy(update={"content": self.text(m.content)}) for m in messages]

    def tools(self, tool_executor: Any) -> Any:
        return _RedactingTools(tool_executor, self) if self._secrets else tool_executor

    def rounds(self, on_tool_round: Any) -> Any:
        """`on_tool_round`, with what it adds to the messages masked."""
        if on_tool_round is None or not self._secrets:
            return on_tool_round

        def masked(round_num: int, messages: list[Message]) -> None:
            before = len(messages)
            on_tool_round(round_num, messages)
            messages[before:] = self.messages(messages[before:])

        return masked


class _RedactingTools:
    """A tool executor whose results reach the model with secrets masked."""

    def __init__(self, inner: Any, redactor: Redactor) -> None:
        self._inner = inner
        self._redactor = redactor

    async def execute(self, name: str, args: dict[str, Any]) -> Any:
        return self._redactor.payload(await self._inner.execute(name, args))


def vault_values(project_root: Path | None) -> list[str]:
    """The values in the project's `.specweaver/vault.env`; none when there is no vault."""
    if project_root is None:
        return []
    vault = project_root / ".specweaver" / "vault.env"
    if not vault.is_file():
        return []
    values = []
    for line in vault.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        values.append(line.split("=", 1)[1].strip().strip("\"'"))
    return values
