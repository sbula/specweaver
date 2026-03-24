# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM data models — Message, GenerationConfig, TokenUsage, LLMResponse, Tool models.

Common across all providers. Designed based on convergence analysis
of Google Gemini, OpenAI, Anthropic, Mistral, Ollama, vLLM, and Qwen APIs.

Tool models (ToolParameter, ToolDefinition, ToolCall) are provider-agnostic.
Each adapter converts these to its provider's format internally.
"""

from __future__ import annotations

import enum
from typing import Any, Literal

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
    tools: list[ToolDefinition] | None = None  # Provider-agnostic tool definitions
    max_tool_rounds: int = 5  # Max agentic loop iterations
    # Future: top_p, stop_sequences, seed


class TokenUsage(BaseModel):
    """Token usage information from a generation."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Accumulate token usage across multiple LLM calls."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class LLMResponse(BaseModel):
    """Response from an LLM generation."""

    text: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str = "stop"  # "stop", "max_tokens", "error"
    tool_calls: list[ToolCall] = Field(default_factory=list)


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


# ---------------------------------------------------------------------------
# Tool models — provider-agnostic abstractions for LLM function calling
# ---------------------------------------------------------------------------


class ToolParameter(BaseModel):
    """A single parameter in a tool definition.

    Provider-agnostic: describes a parameter's name, type, and constraints.
    Each adapter converts to its provider's parameter format.
    """

    name: str
    type: Literal["string", "integer", "boolean", "number"]
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None  # Valid values


class ToolDefinition(BaseModel):
    """Provider-agnostic tool definition.

    Each adapter converts this to its provider's format:
    - Gemini -> types.FunctionDeclaration
    - OpenAI -> {"type": "function", "function": {...}}
    - Anthropic -> {"name": ..., "input_schema": {...}}
    """

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)

    def to_json_schema(self) -> dict[str, Any]:
        """Convert parameters to JSON Schema format.

        Useful for adapters that accept JSON Schema (OpenAI, Anthropic).
        """
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }


class ToolCall(BaseModel):
    """A tool invocation extracted from an LLM response.

    Provider-agnostic: each adapter converts its provider's
    response format into this model.
    """

    name: str
    args: dict[str, Any]
    call_id: str = ""  # Provider-specific correlation ID

