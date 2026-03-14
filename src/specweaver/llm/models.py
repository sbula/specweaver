# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM data models — Message, GenerationConfig, TokenUsage, LLMResponse.

Common across all providers. Designed based on convergence analysis
of Google Gemini, OpenAI, Anthropic, Mistral, Ollama, vLLM, and Qwen APIs.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, Field


class Role(enum.StrEnum):
    """Message role in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A single message in a conversation."""

    role: Role
    content: str


class GenerationConfig(BaseModel):
    """Configuration for LLM generation.

    Common parameters that all providers support (or can map to).
    """

    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096, gt=0)
    response_format: Literal["text", "json"] = "text"
    system_instruction: str | None = None
    # Future: top_p, stop_sequences, tools, seed


class TokenUsage(BaseModel):
    """Token usage information from a generation."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """Response from an LLM generation."""

    text: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str = "stop"  # "stop", "max_tokens", "error"


class TokenBudget(BaseModel):
    """Tracks token budget lifecycle for prompt assembly.

    Use ``add()`` to record consumed tokens and check ``exceeded``
    before sending to the LLM.
    """

    limit: int = Field(default=128_000, gt=0)
    used: int = Field(default=0, ge=0)

    @property
    def remaining(self) -> int:
        """Tokens still available within the budget."""
        return max(0, self.limit - self.used)

    @property
    def exceeded(self) -> bool:
        """True if used tokens exceed the budget limit."""
        return self.used > self.limit

    @property
    def usage_pct(self) -> float:
        """Budget usage as a percentage (0.0-100.0+)."""
        if self.limit == 0:
            return 100.0
        return (self.used / self.limit) * 100

    @property
    def warning(self) -> bool:
        """True if usage exceeds 80% of the budget."""
        return self.usage_pct > 80.0

    def add(self, tokens: int) -> None:
        """Record consumed tokens."""
        self.used += tokens

    def summary(self) -> str:
        """Human-readable budget summary for CLI display.

        Example: ``12,400 / 128,000 (9.7%)``
        """
        return f"{self.used:,} / {self.limit:,} ({self.usage_pct:.1f}%)"
