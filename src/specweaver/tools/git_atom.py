# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""GitAtom — high-level intent-based git operations.

Translates LLM intents (commit, inspect, discard, ...) into sequences
of GitTool calls. Enforces conventional commits and branch naming.

The role determines which intents are available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.tools.git_tool import GitTool


# ---------------------------------------------------------------------------
# Validation patterns
# ---------------------------------------------------------------------------

_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|docs|test|chore|refactor|style|perf|ci|build)(\(.+\))?: .+$"
)

_BRANCH_NAME_RE = re.compile(
    r"^(feat|fix|docs|chore|refactor)/[a-z0-9][a-z0-9-]*$"
)


# ---------------------------------------------------------------------------
# Role → allowed intents
# ---------------------------------------------------------------------------

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset({
        "commit",
        "inspect_changes",
        "discard",
        "uncommit",
        "start_branch",
        "switch_branch",
    }),
    "reviewer": frozenset({
        "history",
        "show_commit",
        "blame",
        "compare",
        "list_branches",
    }),
    "debugger": frozenset({
        "history",
        "file_history",
        "show_old",
        "search_history",
        "reflog",
        "inspect_changes",
    }),
    "drafter": frozenset({
        "commit",
        "inspect_changes",
        "discard",
    }),
}

# Intent → required git subcommands (for building the GitTool whitelist)
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


# ---------------------------------------------------------------------------
# Atom result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AtomResult:
    """Result from a GitAtom intent execution."""

    status: str  # "success" or "error"
    message: str
    data: str = ""  # stdout or combined output


# ---------------------------------------------------------------------------
# GitAtom
# ---------------------------------------------------------------------------

class GitAtomError(Exception):
    """Raised when a GitAtom operation is blocked or invalid."""


class GitAtom:
    """High-level intent-based git operations.

    Args:
        tool: The GitTool instance (configured with cwd and whitelist).
        role: The agent's role (determines which intents are allowed).
    """

    def __init__(self, tool: GitTool, role: str) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._tool = tool
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

    def _require_intent(self, intent: str) -> None:
        """Raise if the current role doesn't have this intent."""
        if intent not in self._allowed:
            msg = (
                f"Intent '{intent}' is not allowed for role '{self._role}'. "
                f"Allowed: {sorted(self._allowed)}"
            )
            raise GitAtomError(msg)

    # -- Implementer / Drafter intents -----------------------------------

    def commit(self, message: str) -> AtomResult:
        """Stage all changes and commit with a conventional commit message."""
        self._require_intent("commit")

        if not _CONVENTIONAL_COMMIT_RE.match(message):
            return AtomResult(
                status="error",
                message=(
                    f"Invalid commit message format: {message!r}. "
                    "Expected: <type>(<scope>): <description> "
                    "(e.g., 'feat: add user login')"
                ),
            )

        # Stage all changes
        add_result = self._tool.run("add", "-A")
        if add_result.exit_code != 0:
            return AtomResult(
                status="error",
                message=f"git add failed: {add_result.stderr}",
            )

        # Check there's something to commit
        diff_result = self._tool.run("diff", "--staged", "--stat")
        if not diff_result.stdout.strip():
            return AtomResult(
                status="error",
                message="Nothing to commit (no staged changes).",
            )

        # Commit
        commit_result = self._tool.run("commit", "-m", message)
        if commit_result.exit_code != 0:
            return AtomResult(
                status="error",
                message=f"git commit failed: {commit_result.stderr}",
            )

        return AtomResult(
            status="success",
            message="Changes committed.",
            data=commit_result.stdout,
        )

    def inspect_changes(self) -> AtomResult:
        """Show current status and diff."""
        self._require_intent("inspect_changes")

        status_result = self._tool.run("status", "--short")
        diff_result = self._tool.run("diff")

        output = ""
        if status_result.stdout.strip():
            output += f"=== Status ===\n{status_result.stdout}\n"
        if diff_result.stdout.strip():
            output += f"=== Diff ===\n{diff_result.stdout}\n"

        if not output:
            return AtomResult(
                status="success",
                message="Working tree is clean.",
            )

        return AtomResult(
            status="success",
            message="Changes found.",
            data=output,
        )

    def discard(self, file: str) -> AtomResult:
        """Discard working tree changes for a specific file."""
        self._require_intent("discard")

        result = self._tool.run("restore", file)
        if result.exit_code != 0:
            return AtomResult(
                status="error",
                message=f"git restore failed: {result.stderr}",
            )

        return AtomResult(
            status="success",
            message=f"Discarded changes to {file}.",
        )

    def uncommit(self) -> AtomResult:
        """Undo the last commit, keeping changes staged."""
        self._require_intent("uncommit")

        result = self._tool.run("reset", "--soft", "HEAD~1")
        if result.exit_code != 0:
            return AtomResult(
                status="error",
                message=f"git reset failed: {result.stderr}",
            )

        return AtomResult(
            status="success",
            message="Last commit undone. Changes are still staged.",
        )

    def start_branch(self, name: str) -> AtomResult:
        """Create and switch to a new branch with enforced naming."""
        self._require_intent("start_branch")

        if not _BRANCH_NAME_RE.match(name):
            return AtomResult(
                status="error",
                message=(
                    f"Invalid branch name: {name!r}. "
                    "Expected: <type>/<kebab-case-name> "
                    "(e.g., 'feat/add-login', 'fix/null-pointer')"
                ),
            )

        result = self._tool.run("switch", "-c", name)
        if result.exit_code != 0:
            return AtomResult(
                status="error",
                message=f"git switch failed: {result.stderr}",
            )

        return AtomResult(
            status="success",
            message=f"Created and switched to branch '{name}'.",
        )

    def switch_branch(self, name: str) -> AtomResult:
        """Switch to an existing branch with auto-stash."""
        self._require_intent("switch_branch")

        # Auto-stash if there are changes
        status = self._tool.run("status", "--porcelain")
        has_changes = bool(status.stdout.strip())

        if has_changes:
            stash = self._tool.run("stash")
            if stash.exit_code != 0:
                return AtomResult(
                    status="error",
                    message=f"git stash failed: {stash.stderr}",
                )

        # Switch
        switch = self._tool.run("switch", name)
        if switch.exit_code != 0:
            # Restore stash if switch fails
            if has_changes:
                self._tool.run("stash", "pop")
            return AtomResult(
                status="error",
                message=f"git switch failed: {switch.stderr}",
            )

        # Pop stash on new branch
        if has_changes:
            pop = self._tool.run("stash", "pop")
            if pop.exit_code != 0:
                return AtomResult(
                    status="error",
                    message=f"Switched to '{name}' but stash pop failed: {pop.stderr}",
                )

        return AtomResult(
            status="success",
            message=f"Switched to branch '{name}'.",
        )

    # -- Reviewer intents ------------------------------------------------

    def history(self, n: int = 10) -> AtomResult:
        """Show recent commit history."""
        self._require_intent("history")

        result = self._tool.run("log", "--oneline", f"-n{n}")
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Last {n} commits." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def show_commit(self, commit_hash: str) -> AtomResult:
        """Show the contents of a specific commit."""
        self._require_intent("show_commit")

        result = self._tool.run("show", commit_hash)
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message="Commit details." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def blame(self, file: str) -> AtomResult:
        """Show line-by-line authorship of a file."""
        self._require_intent("blame")

        result = self._tool.run("blame", file)
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message="Blame output." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def compare(self, base: str, head: str) -> AtomResult:
        """Compare two branches or commits."""
        self._require_intent("compare")

        result = self._tool.run("diff", f"{base}..{head}")
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message="Branch comparison." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def list_branches(self) -> AtomResult:
        """List all branches."""
        self._require_intent("list_branches")

        result = self._tool.run("branch", "-a")
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message="Branch list." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    # -- Debugger intents ------------------------------------------------

    def file_history(self, file: str, n: int = 5) -> AtomResult:
        """Show recent commits that touched a specific file."""
        self._require_intent("file_history")

        result = self._tool.run("log", f"-n{n}", "--oneline", "--", file)
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Last {n} changes to {file}." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def show_old(self, file: str, rev: str = "HEAD~1") -> AtomResult:
        """Show a previous version of a file."""
        self._require_intent("show_old")

        result = self._tool.run("show", f"{rev}:{file}")
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"{file} at {rev}." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def search_history(self, text: str) -> AtomResult:
        """Find commits where a text string was added or removed."""
        self._require_intent("search_history")

        result = self._tool.run("log", f"-S{text}", "--oneline")
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Commits mentioning '{text}'." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )

    def reflog(self, n: int = 10) -> AtomResult:
        """Show the reflog (recovery history)."""
        self._require_intent("reflog")

        result = self._tool.run("reflog", f"-n{n}")
        return AtomResult(
            status="success" if result.exit_code == 0 else "error",
            message=f"Last {n} reflog entries." if result.exit_code == 0 else result.stderr,
            data=result.stdout,
        )
