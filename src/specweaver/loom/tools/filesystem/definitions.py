# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tool definitions for filesystem intents.

These describe the parameters for each intent using SpecWeaver's ToolParameter model.
"""

from __future__ import annotations

from specweaver.llm.models import ToolDefinition, ToolParameter

GREP = ToolDefinition(
    name="grep",
    description=(
        "Search for a text pattern in file contents within the workspace. "
        "Returns matching lines with context. Supports regex patterns."
    ),
    parameters=[
        ToolParameter(name="pattern", type="string", description="Search pattern (text or regex)"),
        ToolParameter(
            name="path",
            type="string",
            description="Relative path within workspace to search (default: workspace root)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="context_lines",
            type="integer",
            description="Number of context lines before/after each match",
            required=False,
            default=3,
        ),
        ToolParameter(
            name="case_sensitive",
            type="boolean",
            description="Whether to perform case-sensitive search",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maximum number of matches to return",
            required=False,
            default=20,
        ),
    ],
)

FIND_FILES = ToolDefinition(
    name="find_files",
    description=(
        "Find files and directories matching a glob pattern within the workspace. "
        "Returns file paths, types, and sizes."
    ),
    parameters=[
        ToolParameter(
            name="pattern", type="string", description="Glob pattern (e.g., '*.py', 'context.yaml')"
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Relative path within workspace to search (default: workspace root)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="type",
            type="string",
            description="Filter by type: 'file', 'directory', or 'any'",
            required=False,
            default="any",
            enum=["file", "directory", "any"],
        ),
        ToolParameter(
            name="max_results",
            type="integer",
            description="Maximum number of results to return",
            required=False,
            default=30,
        ),
    ],
)

READ_FILE = ToolDefinition(
    name="read_file",
    description=(
        "Read a file's content within the workspace. "
        "Capped at 200 lines per call. To read more, call again with "
        "different start_line/end_line."
    ),
    parameters=[
        ToolParameter(
            name="path", type="string", description="Relative path to the file within workspace"
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="1-indexed start line (optional, default: beginning of file)",
            required=False,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="1-indexed end line (optional, default: end of file or line cap)",
            required=False,
        ),
    ],
)

LIST_DIRECTORY = ToolDefinition(
    name="list_directory",
    description=(
        "List directory tree within the workspace. "
        "Returns paths, types, and nested children up to a given depth."
    ),
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Relative path within workspace (default: workspace root)",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="depth",
            type="integer",
            description="Maximum depth to descend into subdirectories",
            required=False,
            default=2,
        ),
        ToolParameter(
            name="max_entries",
            type="integer",
            description="Maximum total entries to return",
            required=False,
            default=50,
        ),
    ],
)

# Map raw intents to definitions
INTENT_DEFINITIONS: dict[str, ToolDefinition] = {
    "grep": GREP,
    "find_files": FIND_FILES,
    "read_file": READ_FILE,
    "list_directory": LIST_DIRECTORY,
}
