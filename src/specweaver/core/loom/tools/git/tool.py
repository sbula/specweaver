# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""GitTool — high-level intent-based git operations (capability provider).

Translates LLM intents (commit, inspect, discard, ...) into sequences
of GitExecutor calls. Enforces conventional commits and branch naming.

The role determines which intents are available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition
    from specweaver.core.loom.commons.git.executor import GitExecutor


# Validation patterns

_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|docs|test|chore|refactor|style|perf|ci|build)(\(.+\))?: .+$"
)

_BRANCH_NAME_RE = re.compile(r"^(feat|fix|docs|chore|refactor)/[a-z0-9][a-z0-9-]*$")


# Role → allowed intents

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset(
        {"commit", "inspect_changes", "discard", "uncommit", "start_branch", "switch_branch"}
    ),
    "reviewer": frozenset({"history", "show_commit", "blame", "compare", "list_branches"}),
    "planner": frozenset({"history", "show_commit", "blame", "compare", "list_branches"}),
    "debugger": frozenset(
        {"history", "file_history", "show_old", "search_history", "reflog", "inspect_changes"}
    ),
    "drafter": frozenset({"commit", "inspect_changes", "discard"}),
    # Hidden role — only the Engine can activate this for conflict resolution.
    # Never assigned directly to agents.
    "conflict_resolver": frozenset(
        {"list_conflicts", "show_conflict", "mark_resolved", "abort_merge", "complete_merge"}
    ),
}

# Intent → required git subcommands (for building the GitExecutor whitelist)
INTENT_COMMANDS: dict[str, frozenset[str]] = {
    "commit": frozenset({"add", "diff", "commit"}),
    "inspect_changes": frozenset({"status", "diff"}),
    "discard": frozenset({"restore"}),
    "uncommit": frozenset({"reset"}),
    "start_branch": frozenset({"switch"}),
    "switch_branch": frozenset({"stash", "switch"}),
    "history": frozenset({"log"}),
    "show_commit": frozenset({"show"}),
    "blame": frozenset({"blame"}),
    "compare": frozenset({"diff"}),
    "list_branches": frozenset({"branch"}),
    "file_history": frozenset({"log"}),
    "show_old": frozenset({"show"}),
    "search_history": frozenset({"log"}),
    "reflog": frozenset({"reflog"}),
    # Conflict resolution intents (hidden, engine-activated)
    "list_conflicts": frozenset({"diff"}),
    "show_conflict": frozenset({"diff"}),
    "mark_resolved": frozenset({"add"}),
    "abort_merge": frozenset({"merge"}),
    "complete_merge": frozenset({"commit"}),
}


def whitelist_for_role(role: str) -> set[str]:
    """Compute the git command whitelist needed for a given role."""
    intents = ROLE_INTENTS.get(role)
    if intents is None:
        msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
        raise ValueError(msg)
    commands: set[str] = set()
    for intent in intents:
        commands |= INTENT_COMMANDS[intent]
    return commands


@dataclass(frozen=True)
class ToolResult:
    """Result from a GitTool intent execution."""

    status: str  # "success" or "error"
    message: str
    data: str = ""  # stdout or combined output


class GitToolError(Exception):
    """Raised when a GitTool operation is blocked or invalid."""


class GitTool:
    """High-level intent-based git operations (capability provider).

    Args:
        executor: The GitExecutor instance (configured with cwd and whitelist).
        role: The agent's role (determines which intents are allowed).
    """

    def __init__(self, executor: GitExecutor, role: str) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._executor = executor
        self._role = role
        self._allowed = ROLE_INTENTS[role]

    @property
    def role(self) -> str:
        """The agent's role."""
        return self._role

    @property
    def allowed_intents(self) -> frozenset[str]:
        """Intents available for this role."""
        return self._allowed

    def definitions(self) -> list[ToolDefinition]:
        from specweaver.core.loom.tools.git.definitions import INTENT_DEFINITIONS
        from specweaver.core.loom.tools.git.tool import ROLE_INTENTS

        return [d for name, d in INTENT_DEFINITIONS.items() if name in ROLE_INTENTS[self._role]]

    def _require_intent(self, intent: str) -> None:
        """Raise if the current role doesn't have this intent."""
        if intent not in self._allowed:
            msg = (
                f"Intent '{intent}' is not allowed for role '{self._role}'. "
                f"Allowed: {sorted(self._allowed)}"
            )
            raise GitToolError(msg)

    # -- Implementer / Drafter intents -----------------------------------

    def commit(self, message: str) -> ToolResult:
        """Stage all changes and commit with a conventional commit message."""
        self._require_intent("commit")

        if not _CONVENTIONAL_COMMIT_RE.match(message):
            return ToolResult(
                status="error",
                message=(
                    f"Invalid commit message format: {message!r}. "
                    "Expected: <type>(<scope>): <description> "
                    "(e.g., 'feat: add user login')"
                ),
            )

        # Stage all changes
        add_result = self._executor.run("add", "-A")
        if add_result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git add failed: {add_result.stderr}",
            )

        # Check there's something to commit
        diff_result = self._executor.run("diff", "--staged", "--stat")
        if not diff_result.stdout.strip():
            return ToolResult(
                status="error",
                message="Nothing to commit (no staged changes).",
            )

        # Commit
        commit_result = self._executor.run("commit", "-m", message)
        if commit_result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git commit failed: {commit_result.stderr}",
            )

        return ToolResult(
            status="success",
            message="Changes committed.",
            data=commit_result.stdout,
        )

    def inspect_changes(self) -> ToolResult:
        """Show current status and diff."""
        self._require_intent("inspect_changes")

        status_result = self._executor.run("status", "--short")
        diff_result = self._executor.run("diff")

        output = ""
        if status_result.stdout.strip():
            output += f"=== Status ===\n{status_result.stdout}\n"
        if diff_result.stdout.strip():
            output += f"=== Diff ===\n{diff_result.stdout}\n"

        if not output:
            return ToolResult(
                status="success",
                message="Working tree is clean.",
            )

        return ToolResult(
            status="success",
            message="Changes found.",
            data=output,
        )

    def discard(self, file: str) -> ToolResult:
        """Discard working tree changes for a specific file."""
        self._require_intent("discard")

        result = self._executor.run("restore", file)
        if result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git restore failed: {result.stderr}",
            )

        return ToolResult(
            status="success",
            message=f"Discarded changes to {file}.",
        )

    def uncommit(self) -> ToolResult:
        """Undo the last commit, keeping changes staged."""
        self._require_intent("uncommit")

        result = self._executor.run("reset", "--soft", "HEAD~1")
        if result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git reset failed: {result.stderr}",
            )

        return ToolResult(
            status="success",
            message="Last commit undone. Changes are still staged.",
        )

    def start_branch(self, name: str) -> ToolResult:
        """Create and switch to a new branch with enforced naming."""
        self._require_intent("start_branch")

        if not _BRANCH_NAME_RE.match(name):
            return ToolResult(
                status="error",
                message=(
                    f"Invalid branch name: {name!r}. "
                    "Expected: <type>/<kebab-case-name> "
                    "(e.g., 'feat/add-login', 'fix/null-pointer')"
                ),
            )

        result = self._executor.run("switch", "-c", name)
        if result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git switch failed: {result.stderr}",
            )

        return ToolResult(
            status="success",
            message=f"Created and switched to branch '{name}'.",
        )

    def switch_branch(self, name: str) -> ToolResult:
        """Switch to an existing branch with auto-stash."""
        self._require_intent("switch_branch")

        # Auto-stash if there are changes
        status = self._executor.run("status", "--porcelain")
        has_changes = bool(status.stdout.strip())

        if has_changes:
            stash = self._executor.run("stash")
            if stash.exit_code != 0:
                return ToolResult(
                    status="error",
                    message=f"git stash failed: {stash.stderr}",
                )

        # Switch
        switch = self._executor.run("switch", name)
        if switch.exit_code != 0:
            # Restore stash if switch fails
            if has_changes:
                self._executor.run("stash", "pop")
            return ToolResult(
                status="error",
                message=f"git switch failed: {switch.stderr}",
            )

        # Pop stash on new branch
        if has_changes:
            pop = self._executor.run("stash", "pop")
            if pop.exit_code != 0:
                return ToolResult(
                    status="error",
                    message=f"Switched to '{name}' but stash pop failed: {pop.stderr}",
                )

        return ToolResult(
            status="success",
            message=f"Switched to branch '{name}'.",
        )

    # -- Reviewer intents ------------------------------------------------

    def history(self, n: int = 10) -> ToolResult:
        """Show recent commit history."""
        self._require_intent("history")

        result = self._executor.run("log", "--oneline", f"-n{n}")
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Last {n} commits." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def show_commit(self, commit_hash: str) -> ToolResult:
        """Show the contents of a specific commit."""
        self._require_intent("show_commit")

        result = self._executor.run("show", commit_hash)
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message="Commit details." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def blame(self, file: str) -> ToolResult:
        """Show line-by-line authorship of a file."""
        self._require_intent("blame")

        result = self._executor.run("blame", file)
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message="Blame output." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def compare(self, base: str, head: str) -> ToolResult:
        """Compare two branches or commits."""
        self._require_intent("compare")

        result = self._executor.run("diff", f"{base}..{head}")
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message="Branch comparison." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def list_branches(self) -> ToolResult:
        """List all branches."""
        self._require_intent("list_branches")

        result = self._executor.run("branch", "-a")
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message="Branch list." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    # -- Debugger intents ------------------------------------------------

    def file_history(self, file: str, n: int = 5) -> ToolResult:
        """Show recent commits that touched a specific file."""
        self._require_intent("file_history")

        result = self._executor.run("log", f"-n{n}", "--oneline", "--", file)
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Last {n} changes to {file}." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def show_old(self, file: str, rev: str = "HEAD~1") -> ToolResult:
        """Show a previous version of a file."""
        self._require_intent("show_old")

        result = self._executor.run("show", f"{rev}:{file}")
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"{file} at {rev}." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def search_history(self, text: str) -> ToolResult:
        """Find commits where a text string was added or removed."""
        self._require_intent("search_history")

        result = self._executor.run("log", f"-S{text}", "--oneline")
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Commits mentioning '{text}'." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def reflog(self, n: int = 10) -> ToolResult:
        """Show the reflog (recovery history)."""
        self._require_intent("reflog")

        result = self._executor.run("reflog", f"-n{n}")
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Last {n} reflog entries." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    # -- Conflict resolution intents (hidden, engine-activated) ----------

    def list_conflicts(self) -> ToolResult:
        """List files with merge conflicts."""
        self._require_intent("list_conflicts")

        result = self._executor.run("diff", "--name-only", "--diff-filter=U")
        if result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git diff failed: {result.stderr}",
            )

        files = result.stdout.strip()
        if not files:
            return ToolResult(
                status="success",
                message="No conflicts found.",
            )

        return ToolResult(
            status="success",
            message=f"{len(files.splitlines())} file(s) with conflicts.",
            data=files,
        )

    def show_conflict(self, file: str) -> ToolResult:
        """Show conflict markers for a specific file."""
        self._require_intent("show_conflict")

        result = self._executor.run("diff", file)
        return ToolResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Conflict in {file}." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def mark_resolved(self, file: str) -> ToolResult:
        """Stage a resolved file during conflict resolution."""
        self._require_intent("mark_resolved")

        result = self._executor.run("add", file)
        if result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git add failed: {result.stderr}",
            )

        return ToolResult(
            status="success",
            message=f"Marked {file} as resolved.",
        )

    def abort_merge(self) -> ToolResult:
        """Abort the current merge and restore clean state."""
        self._require_intent("abort_merge")

        result = self._executor.run("merge", "--abort")
        if result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git merge --abort failed: {result.stderr}",
            )

        return ToolResult(
            status="success",
            message="Merge aborted. Working tree restored.",
        )

    def complete_merge(self) -> ToolResult:
        """Complete the merge after all conflicts are resolved."""
        self._require_intent("complete_merge")

        result = self._executor.run("commit", "--no-edit")
        if result.exit_code != 0:
            return ToolResult(
                status="error",
                message=f"git commit failed: {result.stderr}",
            )

        return ToolResult(
            status="success",
            message="Merge completed.",
            data=result.stdout,
        )
