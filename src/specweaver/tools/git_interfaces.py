# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

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

from specweaver.tools.git_atom import (
    AtomResult,
    GitAtom,
    whitelist_for_role,
)
from specweaver.tools.git_tool import GitTool

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Role-specific interfaces
# ---------------------------------------------------------------------------


class ImplementerGitInterface:
    """Git interface for the Implementer role.

    Allowed intents: commit, inspect_changes, discard,
                     uncommit, start_branch, switch_branch.
    """

    def __init__(self, atom: GitAtom) -> None:
        self._atom = atom

    def commit(self, message: str) -> AtomResult:
        """Stage all changes and commit with a conventional commit message."""
        return self._atom.commit(message)

    def inspect_changes(self) -> AtomResult:
        """Show current status and diff."""
        return self._atom.inspect_changes()

    def discard(self, file: str) -> AtomResult:
        """Discard working tree changes for a specific file."""
        return self._atom.discard(file)

    def uncommit(self) -> AtomResult:
        """Undo the last commit, keeping changes staged."""
        return self._atom.uncommit()

    def start_branch(self, name: str) -> AtomResult:
        """Create and switch to a new branch."""
        return self._atom.start_branch(name)

    def switch_branch(self, name: str) -> AtomResult:
        """Switch to an existing branch (auto-stashes changes)."""
        return self._atom.switch_branch(name)


class ReviewerGitInterface:
    """Git interface for the Reviewer role.

    Allowed intents: history, show_commit, blame, compare, list_branches.
    All read-only.
    """

    def __init__(self, atom: GitAtom) -> None:
        self._atom = atom

    def history(self, n: int = 10) -> AtomResult:
        """Show recent commit history."""
        return self._atom.history(n)

    def show_commit(self, commit_hash: str) -> AtomResult:
        """Show the contents of a specific commit."""
        return self._atom.show_commit(commit_hash)

    def blame(self, file: str) -> AtomResult:
        """Show line-by-line authorship of a file."""
        return self._atom.blame(file)

    def compare(self, base: str, head: str) -> AtomResult:
        """Compare two branches or commits."""
        return self._atom.compare(base, head)

    def list_branches(self) -> AtomResult:
        """List all branches."""
        return self._atom.list_branches()


class DebuggerGitInterface:
    """Git interface for the Debugger role.

    Allowed intents: history, file_history, show_old,
                     search_history, reflog, inspect_changes.
    """

    def __init__(self, atom: GitAtom) -> None:
        self._atom = atom

    def history(self, n: int = 10) -> AtomResult:
        """Show recent commit history."""
        return self._atom.history(n)

    def file_history(self, file: str, n: int = 5) -> AtomResult:
        """Show recent commits that touched a specific file."""
        return self._atom.file_history(file, n)

    def show_old(self, file: str, rev: str = "HEAD~1") -> AtomResult:
        """Show a previous version of a file."""
        return self._atom.show_old(file, rev)

    def search_history(self, text: str) -> AtomResult:
        """Find commits where a text string was added or removed."""
        return self._atom.search_history(text)

    def reflog(self, n: int = 10) -> AtomResult:
        """Show the reflog (recovery history)."""
        return self._atom.reflog(n)

    def inspect_changes(self) -> AtomResult:
        """Show current status and diff."""
        return self._atom.inspect_changes()


class DrafterGitInterface:
    """Git interface for the Drafter role.

    Allowed intents: commit, inspect_changes, discard.
    """

    def __init__(self, atom: GitAtom) -> None:
        self._atom = atom

    def commit(self, message: str) -> AtomResult:
        """Stage all changes and commit with a conventional commit message."""
        return self._atom.commit(message)

    def inspect_changes(self) -> AtomResult:
        """Show current status and diff."""
        return self._atom.inspect_changes()

    def discard(self, file: str) -> AtomResult:
        """Discard working tree changes for a specific file."""
        return self._atom.discard(file)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ROLE_INTERFACE_MAP = {
    "implementer": ImplementerGitInterface,
    "reviewer": ReviewerGitInterface,
    "debugger": DebuggerGitInterface,
    "drafter": DrafterGitInterface,
}

GitInterface = (
    ImplementerGitInterface
    | ReviewerGitInterface
    | DebuggerGitInterface
    | DrafterGitInterface
)


def create_git_interface(role: str, cwd: Path) -> GitInterface:
    """Create a role-specific git interface for the given project directory.

    The cwd is set by the project setup/config — the agent cannot change it.

    Args:
        role: The agent's role ("implementer", "reviewer", "debugger", "drafter").
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
    tool = GitTool(cwd=cwd, whitelist=whitelist)
    atom = GitAtom(tool=tool, role=role)

    interface_cls = _ROLE_INTERFACE_MAP[role]
    return interface_cls(atom)
