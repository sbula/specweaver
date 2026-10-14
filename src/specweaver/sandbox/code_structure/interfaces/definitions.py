# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""JSON Schema Definitions for the CodeStructureTool to inject into LLM prompts."""

from __future__ import annotations

import logging
from typing import Any

from specweaver.infrastructure.llm.models import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

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
        ),
    ],
)

READ_UNROLLED_SYMBOL_SCHEMA = ToolDefinition(
    name="read_unrolled_symbol",
    description="Returns the full source code block of a symbol, prepended with a commented explanation translating its macros/annotations directly into runtime behaviors using ecosystem knowledge.",
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
        ),
    ],
)

READ_SYMBOL_BODY_SCHEMA = ToolDefinition(
    name="read_symbol_body",
    description=(
        "Returns only the code inside a symbol's body, without its braces, decorators or "
        "signature, at column 0. Pass it, edited, to replace_symbol_body."
    ),
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
        ),
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
            description=(
                "Optional comma-separated visibilities to keep: public, protected, internal, "
                "private (Python: `_name` is internal, `__name` private, a dunder public)."
            ),
            required=False,
        ),
        ToolParameter(
            name="decorator_filter",
            type="string",
            description="Optionally filter symbols to only return those possessing a specific framework decorator/annotation (e.g., 'PreAuthorize', 'RestController').",
            required=False,
        ),
    ],
)

DELETE_SYMBOL_SCHEMA = ToolDefinition(
    name="delete_symbol",
    description="Surgically removes a symbol and its body entirely from the file without leaving stray characters or invalid AST states.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the target file.",
        ),
        ToolParameter(
            name="symbol_name",
            type="string",
            description="The target node class or function name to delete.",
        ),
    ],
)

RENAME_SYMBOL_SCHEMA = ToolDefinition(
    name="rename_symbol",
    description=(
        "Renames a function, method or class and every proven use of it in the project, in one "
        "change: all files or none. Refuses, and lists the lines, when any use is unsure (an "
        "unknown receiver, the name as a string). Names in comments and docs are reported, not "
        "changed. Python only."
    ),
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the file that defines the symbol.",
        ),
        ToolParameter(
            name="symbol_name",
            type="string",
            description="The symbol to rename: a function, a class, or a method as Class.method.",
        ),
        ToolParameter(
            name="new_name",
            type="string",
            description="The new name: a plain identifier, without the class.",
        ),
    ],
)

ADD_SYMBOL_SCHEMA = ToolDefinition(
    name="add_symbol",
    description="Injects a completely new symbol cleanly into a specified parent class or to the bottom of the file if target_parent is omitted.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the target file.",
        ),
        ToolParameter(
            name="target_parent",
            type="string",
            description="The class name to inject the new symbol into. If null or empty, injects to the bottom of the file.",
            required=False,
        ),
        ToolParameter(
            name="new_code",
            type="string",
            description="The full syntax logic of the new symbol to add.",
        ),
    ],
)

REPLACE_SYMBOL_BODY_SCHEMA = ToolDefinition(
    name="replace_symbol_body",
    description=(
        "Replaces only the code inside a symbol's body, keeping its braces, decorators and "
        "signature. Give the code as read_symbol_body returns it, at any indentation; it is put at "
        "the symbol's own. A body that would leave the file unparseable is refused."
    ),
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the target file.",
        ),
        ToolParameter(
            name="symbol_name",
            type="string",
            description="The target node class or function name whose body will be updated.",
        ),
        ToolParameter(
            name="new_code",
            type="string",
            description="The new replacement logic block.",
        ),
    ],
)

REPLACE_SYMBOL_SCHEMA = ToolDefinition(
    name="replace_symbol",
    description="Surgically overwrites the ENTIRE wrapper (decorators, signature, body) of a target symbol.",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="The exact relative path of the target file.",
        ),
        ToolParameter(
            name="symbol_name",
            type="string",
            description="The target node class or function name to replace.",
        ),
        ToolParameter(
            name="new_code",
            type="string",
            description="The new raw code payload that will replace the given symbol boundary entirely.",
        ),
    ],
)


def _filter_list_schema(list_schema: Any, supported_params: dict[str, set[str]] | None) -> Any:
    import copy

    if (
        supported_params is not None
        and "list_symbols" in supported_params
        and "decorator_filter" not in supported_params["list_symbols"]
    ):
        filtered = copy.deepcopy(list_schema)
        filtered.parameters = [p for p in filtered.parameters if p.name != "decorator_filter"]
        return filtered
    return list_schema


def get_code_structure_schema(
    supported_intents: set[str] | None = None,
    supported_params: dict[str, set[str]] | None = None,
) -> list[Any]:
    """Returns the JSON Schema tools injected into the Prompt."""
    schemas = []

    intent_map = {
        "skeleton": READ_FILE_STRUCTURE_SCHEMA,
        "symbol": READ_SYMBOL_SCHEMA,
        "symbol_body": READ_SYMBOL_BODY_SCHEMA,
        "framework_markers": READ_UNROLLED_SYMBOL_SCHEMA,
        "replace": REPLACE_SYMBOL_SCHEMA,
        "replace_body": REPLACE_SYMBOL_BODY_SCHEMA,
        "add": ADD_SYMBOL_SCHEMA,
        "delete": DELETE_SYMBOL_SCHEMA,
        "rename": RENAME_SYMBOL_SCHEMA,
    }

    for intent, schema in intent_map.items():
        if supported_intents is None or intent in supported_intents:
            schemas.append(schema)

    if supported_intents is None or "list" in supported_intents:
        schemas.append(_filter_list_schema(LIST_SYMBOLS_SCHEMA, supported_params))

    return schemas
