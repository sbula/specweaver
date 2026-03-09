# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Git tool — role-restricted git operations for LLM agents."""

from specweaver.tools.git.executor import ExecutorResult, GitExecutor, GitExecutorError
from specweaver.tools.git.interfaces import (
    DebuggerGitInterface,
    DrafterGitInterface,
    ImplementerGitInterface,
    ReviewerGitInterface,
    create_git_interface,
)
from specweaver.tools.git.tool import GitTool, GitToolError, ToolResult

__all__ = [
    "DebuggerGitInterface",
    "DrafterGitInterface",
    "ExecutorResult",
    "GitExecutor",
    "GitExecutorError",
    "GitTool",
    "GitToolError",
    "ImplementerGitInterface",
    "ReviewerGitInterface",
    "ToolResult",
    "create_git_interface",
]
