# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Private data models for prompt content blocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.prompt.interfaces import PromptContentSource


@dataclass
class _ContentBlock:
    """A single block of content to include in the prompt."""

    text: str
    priority: int  # 0 = instructions (never truncated), lower = higher priority
    label: str = ""
    kind: str = (
        "context"  # "instructions", "file", "context", "topology", "standards", "plan", "reminder"
    )
    language: str = "text"
    file_path: str = ""
    role: str = ""  # trust signal: "reference" | "target" | ""
    tokens: int = 0
    truncated: bool = False
    escaping: str = "raw"
    source: PromptContentSource | None = None  # Track the adapter source for safe truncation
