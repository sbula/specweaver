# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for LLM tool models — ToolParameter, ToolDefinition, ToolCall."""

from __future__ import annotations

import pytest

from specweaver.llm.models import (
    GenerationConfig,
    LLMResponse,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolParameter,
)


class TestToolParameter:
    """Tests for ToolParameter model."""

    def test_required_fields(self) -> None:
        param = ToolParameter(
            name="pattern",
            type="string",
            description="Search pattern",
        )
        assert param.name == "pattern"
        assert param.type == "string"
        assert param.description == "Search pattern"
        assert param.required is True
        assert param.default is None
        assert param.enum is None

    def test_optional_fields(self) -> None:
        param = ToolParameter(
            name="type",
            type="string",
            description="File type filter",
            required=False,
            default="file",
            enum=["file", "directory", "any"],
        )
        assert param.required is False
        assert param.default == "file"
        assert param.enum == ["file", "directory", "any"]

    def test_valid_types(self) -> None:
        for t in ("string", "integer", "boolean", "number"):
            param = ToolParameter(name="x", type=t, description="test")
            assert param.type == t

    def test_invalid_type_rejected(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 — Pydantic validation error
            ToolParameter(name="x", type="array", description="test")


class TestToolDefinition:
    """Tests for ToolDefinition model."""

    def test_minimal(self) -> None:
        tool = ToolDefinition(
            name="grep",
            description="Search for patterns in files",
        )
        assert tool.name == "grep"
        assert tool.description == "Search for patterns in files"
        assert tool.parameters == []

    def test_with_parameters(self) -> None:
        tool = ToolDefinition(
            name="grep",
            description="Search for patterns in files",
            parameters=[
                ToolParameter(name="pattern", type="string", description="Search pattern"),
                ToolParameter(
                    name="case_sensitive",
                    type="boolean",
                    description="Case sensitive search",
                    required=False,
                    default=False,
                ),
            ],
        )
        assert len(tool.parameters) == 2
        assert tool.parameters[0].name == "pattern"
        assert tool.parameters[1].required is False

    def test_to_json_schema(self) -> None:
        tool = ToolDefinition(
            name="read_file",
            description="Read a file",
            parameters=[
                ToolParameter(name="path", type="string", description="File path"),
                ToolParameter(
                    name="start_line",
                    type="integer",
                    description="Start line",
                    required=False,
                ),
            ],
        )
        schema = tool.to_json_schema()
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert schema["properties"]["path"]["type"] == "string"
        assert "path" in schema["required"]
        assert "start_line" not in schema["required"]


class TestToolCall:
    """Tests for ToolCall model."""

    def test_basic(self) -> None:
        call = ToolCall(
            name="grep",
            args={"pattern": "foo", "path": "src/"},
        )
        assert call.name == "grep"
        assert call.args == {"pattern": "foo", "path": "src/"}
        assert call.call_id == ""

    def test_with_call_id(self) -> None:
        call = ToolCall(
            name="read_file",
            args={"path": "README.md"},
            call_id="call_abc123",
        )
        assert call.call_id == "call_abc123"

    def test_empty_args(self) -> None:
        call = ToolCall(name="list_directory", args={})
        assert call.args == {}


class TestGenerationConfigTools:
    """Tests for tools field on GenerationConfig."""

    def test_default_no_tools(self) -> None:
        config = GenerationConfig(model="test-model")
        assert config.tools is None
        assert config.max_tool_rounds == 5

    def test_with_tools(self) -> None:
        tool = ToolDefinition(name="grep", description="search")
        config = GenerationConfig(
            model="test-model",
            tools=[tool],
            max_tool_rounds=3,
        )
        assert config.tools is not None
        assert len(config.tools) == 1
        assert config.max_tool_rounds == 3


class TestLLMResponseToolCalls:
    """Tests for tool_calls field on LLMResponse."""

    def test_default_empty(self) -> None:
        resp = LLMResponse(text="hello", model="test")
        assert resp.tool_calls == []

    def test_with_tool_calls(self) -> None:
        resp = LLMResponse(
            text="",
            model="test",
            tool_calls=[
                ToolCall(name="grep", args={"pattern": "foo"}),
                ToolCall(name="read_file", args={"path": "bar.py"}),
            ],
        )
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].name == "grep"


class TestTokenUsageAddition:
    """Tests for TokenUsage accumulation."""

    def test_add_usage(self) -> None:
        a = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        b = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)
        result = a + b
        assert result.prompt_tokens == 300
        assert result.completion_tokens == 150
        assert result.total_tokens == 450

    def test_add_preserves_originals(self) -> None:
        a = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        b = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)
        _ = a + b
        assert a.prompt_tokens == 100
        assert b.prompt_tokens == 200
