# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""JSON Schema Definitions for the CodeStructureTool to inject into LLM prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.llm.models import ToolDefinition, ToolParameter


READ_FILE_STRUCTURE_SCHEMA = ToolDefinition(
    name="read_file_structure",
    description="Returns the structural skeleton of a file (imports, signatures, docstrings) while systematically stripping execution bodies to save tokens.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the file to inspect.",
        )
    ],
)

READ_SYMBOL_SCHEMA = ToolDefinition(
    name="read_symbol",
    description="Returns the exact, full implementation logic block of a specified symbol (including its decorators, signature, and body).",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the target file.",
        ),
        ToolParameter(
            name="symbol_name",
            type="string",
            description="The target node class or function name to extract.",
        )
    ],
)

READ_SYMBOL_BODY_SCHEMA = ToolDefinition(
    name="read_symbol_body",
    description="Returns ONLY the internal `{ ... }` curly brace execution block of a symbol, completely omitting its decorators and original signature.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the target file.",
        ),
        ToolParameter(
            name="symbol_name",
            type="string",
            description="The target node class or function name to extract the body from.",
        )
    ],
)

LIST_SYMBOLS_SCHEMA = ToolDefinition(
    name="list_symbols",
    description="Returns a flat list of targetable symbol names dynamically found within a file without returning their bodies or contents.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the target file.",
        ),
        ToolParameter(
            name="visibility",
            type="string",
            description="Optional comma-separated list to filter extraction strictly by visibility boundaries (e.g. 'public').",
            required=False,
        )
    ],
)

def get_code_structure_schema() -> list[Any]:
    """Returns the JSON Schema tools injected into the Prompt."""
    return [
        READ_FILE_STRUCTURE_SCHEMA,
        READ_SYMBOL_SCHEMA,
        READ_SYMBOL_BODY_SCHEMA,
        LIST_SYMBOLS_SCHEMA
    ]
