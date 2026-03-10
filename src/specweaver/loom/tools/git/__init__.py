# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Git tool — role-restricted git operations for LLM agents."""

from specweaver.loom.commons.git.engine_executor import EngineGitExecutor
from specweaver.loom.commons.git.executor import ExecutorResult, GitExecutor, GitExecutorError
from specweaver.loom.tools.git.interfaces import (
    ConflictResolverGitInterface,
    DebuggerGitInterface,
    DrafterGitInterface,
    ImplementerGitInterface,
    ReviewerGitInterface,
    create_git_interface,
)
from specweaver.loom.tools.git.tool import GitTool, GitToolError, ToolResult

__all__ = [
    "ConflictResolverGitInterface",
    "DebuggerGitInterface",
    "DrafterGitInterface",
    "EngineGitExecutor",
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
