# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""MCP-like role interfaces for git operations.

Each interface class exposes ONLY the intents allowed for its role.
The LLM agent receives one of these — it physically cannot call
methods that don't exist on its interface.

The working directory comes from project setup/config, not from the agent.

Usage:
    interface = create_git_interface("implementer", project_path)
    result = interface.commit("feat: add login endpoint")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.loom.commons.git.engine_executor import EngineGitExecutor
from specweaver.loom.commons.git.executor import GitExecutor
from specweaver.loom.tools.git.tool import (
    GitTool,
    ToolResult,
    whitelist_for_role,
)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.llm.models import ToolDefinition

# ---------------------------------------------------------------------------
# Role-specific interfaces
# ---------------------------------------------------------------------------


class ImplementerGitInterface:
    """Git interface for the Implementer role.

    Allowed intents: commit, inspect_changes, discard,
                     uncommit, start_branch, switch_branch.
    """

    def __init__(self, tool: GitTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def commit(self, message: str) -> ToolResult:
        """Stage all changes and commit with a conventional commit message."""
        return self._tool.commit(message)

    def inspect_changes(self) -> ToolResult:
        """Show current status and diff."""
        return self._tool.inspect_changes()

    def discard(self, file: str) -> ToolResult:
        """Discard working tree changes for a specific file."""
        return self._tool.discard(file)

    def uncommit(self) -> ToolResult:
        """Undo the last commit, keeping changes staged."""
        return self._tool.uncommit()

    def start_branch(self, name: str) -> ToolResult:
        """Create and switch to a new branch."""
        return self._tool.start_branch(name)

    def switch_branch(self, name: str) -> ToolResult:
        """Switch to an existing branch (auto-stashes changes)."""
        return self._tool.switch_branch(name)


class ReviewerGitInterface:
    """Git interface for the Reviewer role.

    Allowed intents: history, show_commit, blame, compare, list_branches.
    All read-only.
    """

    def __init__(self, tool: GitTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def history(self, n: int = 10) -> ToolResult:
        """Show recent commit history."""
        return self._tool.history(n)

    def show_commit(self, commit_hash: str) -> ToolResult:
        """Show the contents of a specific commit."""
        return self._tool.show_commit(commit_hash)

    def blame(self, file: str) -> ToolResult:
        """Show line-by-line authorship of a file."""
        return self._tool.blame(file)

    def compare(self, base: str, head: str) -> ToolResult:
        """Compare two branches or commits."""
        return self._tool.compare(base, head)

    def list_branches(self) -> ToolResult:
        """List all branches."""
        return self._tool.list_branches()


class DebuggerGitInterface:
    """Git interface for the Debugger role.

    Allowed intents: history, file_history, show_old,
                     search_history, reflog, inspect_changes.
    """

    def __init__(self, tool: GitTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def history(self, n: int = 10) -> ToolResult:
        """Show recent commit history."""
        return self._tool.history(n)

    def file_history(self, file: str, n: int = 5) -> ToolResult:
        """Show recent commits that touched a specific file."""
        return self._tool.file_history(file, n)

    def show_old(self, file: str, rev: str = "HEAD~1") -> ToolResult:
        """Show a previous version of a file."""
        return self._tool.show_old(file, rev)

    def search_history(self, text: str) -> ToolResult:
        """Find commits where a text string was added or removed."""
        return self._tool.search_history(text)

    def reflog(self, n: int = 10) -> ToolResult:
        """Show the reflog (recovery history)."""
        return self._tool.reflog(n)

    def inspect_changes(self) -> ToolResult:
        """Show current status and diff."""
        return self._tool.inspect_changes()


class DrafterGitInterface:
    """Git interface for the Drafter role.

    Allowed intents: commit, inspect_changes, discard.
    """

    def __init__(self, tool: GitTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def commit(self, message: str) -> ToolResult:
        """Stage all changes and commit with a conventional commit message."""
        return self._tool.commit(message)

    def inspect_changes(self) -> ToolResult:
        """Show current status and diff."""
        return self._tool.inspect_changes()

    def discard(self, file: str) -> ToolResult:
        """Discard working tree changes for a specific file."""
        return self._tool.discard(file)


class ConflictResolverGitInterface:
    """Git interface for conflict resolution.

    Hidden role — only the Engine can activate this.
    Allowed intents: list_conflicts, show_conflict, mark_resolved,
                     abort_merge, complete_merge.
    """

    def __init__(self, tool: GitTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def list_conflicts(self) -> ToolResult:
        """List files with merge conflicts."""
        return self._tool.list_conflicts()

    def show_conflict(self, file: str) -> ToolResult:
        """Show conflict markers for a specific file."""
        return self._tool.show_conflict(file)

    def mark_resolved(self, file: str) -> ToolResult:
        """Stage a resolved file during conflict resolution."""
        return self._tool.mark_resolved(file)

    def abort_merge(self) -> ToolResult:
        """Abort the current merge and restore clean state."""
        return self._tool.abort_merge()

    def complete_merge(self) -> ToolResult:
        """Complete the merge after all conflicts are resolved."""
        return self._tool.complete_merge()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ROLE_INTERFACE_MAP = {
    "implementer": ImplementerGitInterface,
    "reviewer": ReviewerGitInterface,
    "planner": ReviewerGitInterface,
    "debugger": DebuggerGitInterface,
    "drafter": DrafterGitInterface,
    "conflict_resolver": ConflictResolverGitInterface,
}

GitInterface = (
    ImplementerGitInterface
    | ReviewerGitInterface
    | DebuggerGitInterface
    | DrafterGitInterface
    | ConflictResolverGitInterface
)


def create_git_interface(role: str, cwd: Path) -> GitInterface:
    """Create a role-specific git interface for the given project directory.

    The cwd is set by the project setup/config — the agent cannot change it.

    Args:
        role: The agent's role ("implementer", "reviewer", "debugger",
              "drafter", or "conflict_resolver").
        cwd: The target project's working directory (from config, not agent).

    Returns:
        A role-specific interface with only the allowed methods.

    Raises:
        ValueError: If the role is unknown.
    """
    if role not in _ROLE_INTERFACE_MAP:
        msg = f"Unknown role: {role!r}. Known roles: {sorted(_ROLE_INTERFACE_MAP)}"
        raise ValueError(msg)

    whitelist = whitelist_for_role(role)

    # conflict_resolver needs EngineGitExecutor (merge is in its whitelist)
    if role == "conflict_resolver":
        executor: EngineGitExecutor | GitExecutor = EngineGitExecutor(cwd=cwd, whitelist=whitelist)
    else:
        executor = GitExecutor(cwd=cwd, whitelist=whitelist)

    tool = GitTool(executor=executor, role=role)

    interface_cls = _ROLE_INTERFACE_MAP[role]
    return interface_cls(tool)  # type: ignore[return-value]
