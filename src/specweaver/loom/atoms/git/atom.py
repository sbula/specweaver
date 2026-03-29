# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""GitAtom — Flow-level git operations for the Engine.

The Engine uses GitAtom for state checkpointing, branch isolation,
publishing, and integration. These are orchestrator-driven operations
that never require agent judgment.

All commands run on the target project directory via EngineGitExecutor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.loom.atoms.base import Atom, AtomResult, AtomStatus
from specweaver.loom.commons.git.engine_executor import EngineGitExecutor

if TYPE_CHECKING:
    from pathlib import Path


class GitAtomError(Exception):
    """Raised when a GitAtom operation fails."""


class GitAtom(Atom):
    """Flow-level git operations for the Engine.

    Unlike GitTool (agent-facing, role-restricted), GitAtom is for the
    Engine only — it has access to push, merge, fetch, pull, and tag.

    Args:
        cwd: Working directory for git commands (the target project).
    """

    # All git commands that any GitAtom intent might need.
    _ENGINE_WHITELIST: frozenset[str] = frozenset(
        {
            "add",
            "commit",
            "diff",
            "status",  # checkpoint
            "switch",  # isolate / restore
            "restore",  # discard_all
            "reset",  # rollback
            "push",  # publish
            "checkout",
            "merge",  # integrate
            "fetch",
            "pull",  # sync
            "tag",  # tag
        }
    )

    def __init__(self, cwd: Path) -> None:
        self._executor = EngineGitExecutor(
            cwd=cwd,
            whitelist=set(self._ENGINE_WHITELIST),
        )
        self._cwd = cwd

    @property
    def cwd(self) -> Path:
        """The working directory for git commands (read-only)."""
        return self._cwd

    def run(self, context: dict[str, Any]) -> AtomResult:
        """Dispatch to the appropriate intent based on context.

        The Engine provides a context dict with at minimum:
            intent: str — which operation to perform.
            (plus intent-specific keys)

        This method is the Atom ABC entry point.
        """
        intent = context.get("intent")
        if intent is None:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'intent' in context.",
            )

        handler = getattr(self, f"_intent_{intent}", None)
        if handler is None:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Unknown intent: {intent!r}. Known: {sorted(self._known_intents())}",
            )

        return handler(context)  # type: ignore[no-any-return]

    def _known_intents(self) -> set[str]:
        """Return the set of known intent names."""
        prefix = "_intent_"
        return {name[len(prefix) :] for name in dir(self) if name.startswith(prefix)}

    # -- Intent implementations ----------------------------------------

    def _intent_checkpoint(self, context: dict[str, Any]) -> AtomResult:
        """Stage all and commit with the provided message.

        Context keys:
            message: str — commit message.
        """
        message = context.get("message", "checkpoint")

        # Stage all changes
        add_result = self._executor.run("add", "-A")
        if add_result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git add failed: {add_result.stderr}",
            )

        # Check if there's anything to commit
        diff_result = self._executor.run("diff", "--staged", "--quiet")
        if diff_result.exit_code == 0:
            # exit code 0 = no diff = nothing to commit
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message="No changes to commit (idempotent).",
            )

        # Commit
        commit_result = self._executor.run("commit", "-m", message)
        if commit_result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git commit failed: {commit_result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Checkpoint created: {message}",
            exports={"commit_output": commit_result.stdout.strip()},
        )

    def _intent_isolate(self, context: dict[str, Any]) -> AtomResult:
        """Create and switch to an isolation branch.

        Context keys:
            branch: str — branch name to create.
        """
        branch = context.get("branch")
        if not branch:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'branch' in context for isolate intent.",
            )

        result = self._executor.run("switch", "-c", branch)
        if result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git switch -c failed: {result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Isolated to branch: {branch}",
            exports={"branch": branch},
        )

    def _intent_restore(self, context: dict[str, Any]) -> AtomResult:
        """Switch back to the original branch.

        Context keys:
            branch: str — branch name to switch to.
        """
        branch = context.get("branch")
        if not branch:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'branch' in context for restore intent.",
            )

        result = self._executor.run("switch", branch)
        if result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git switch failed: {result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Restored to branch: {branch}",
        )

    def _intent_discard_all(self, _context: dict[str, Any]) -> AtomResult:
        """Discard all working tree changes."""
        result = self._executor.run("restore", ".")
        if result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git restore . failed: {result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="All working tree changes discarded.",
        )

    def _intent_rollback(self, _context: dict[str, Any]) -> AtomResult:
        """Undo the last commit (soft reset)."""
        result = self._executor.run("reset", "--soft", "HEAD~1")
        if result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git reset failed: {result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="Last commit rolled back. Changes remain staged.",
        )

    def _intent_publish(self, context: dict[str, Any]) -> AtomResult:
        """Push the current branch to remote.

        Context keys:
            remote: str — remote name (default: "origin").
            branch: str — branch to push (default: current HEAD).
        """
        remote = context.get("remote", "origin")
        branch = context.get("branch")

        args = [remote]
        if branch:
            args.append(branch)

        result = self._executor.run("push", *args)
        if result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git push failed: {result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Published to {remote}" + (f"/{branch}" if branch else ""),
        )

    def _intent_integrate(self, context: dict[str, Any]) -> AtomResult:
        """Merge source branch into target branch.

        Context keys:
            source: str — branch to merge from.
            target: str — branch to merge into.
            on_conflict: str — "fail" (default) or "resolve".

        On conflict with on_conflict="fail": aborts merge, returns FAILED.
        On conflict with on_conflict="resolve": aborts merge, returns RETRY
            with conflict info so the Engine can spawn a conflict resolver.
        """
        source = context.get("source")
        target = context.get("target")
        on_conflict = context.get("on_conflict", "fail")

        if not source or not target:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'source' and/or 'target' in context.",
            )

        # Checkout target branch
        checkout_result = self._executor.run("checkout", target)
        if checkout_result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git checkout {target} failed: {checkout_result.stderr}",
            )

        # Attempt merge
        merge_result = self._executor.run("merge", source)
        if merge_result.exit_code == 0:
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Merged {source} into {target}.",
                exports={"merge_output": merge_result.stdout.strip()},
            )

        # Merge conflict — get conflicting files before abort
        conflict_result = self._executor.run(
            "diff",
            "--name-only",
            "--diff-filter=U",
        )
        conflict_files = conflict_result.stdout.strip()

        # Abort the merge to restore clean state
        self._executor.run("merge", "--abort")

        if on_conflict == "resolve":
            return AtomResult(
                status=AtomStatus.RETRY,
                message=f"Merge conflict. {len(conflict_files.splitlines())} file(s).",
                exports={
                    "conflict_files": conflict_files.splitlines(),
                    "source": source,
                    "target": target,
                    "needs_conflict_resolver": True,
                },
            )

        return AtomResult(
            status=AtomStatus.FAILED,
            message=f"Merge conflict in {source} → {target}. Files: {conflict_files}",
            exports={"conflict_files": conflict_files.splitlines()},
        )

    def _intent_sync(self, context: dict[str, Any]) -> AtomResult:
        """Fetch and pull from remote.

        Context keys:
            remote: str — remote name (default: "origin").
            branch: str — branch to pull (default: current).
        """
        remote = context.get("remote", "origin")
        branch = context.get("branch")

        # Fetch first
        fetch_result = self._executor.run("fetch", remote)
        if fetch_result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git fetch failed: {fetch_result.stderr}",
            )

        # Pull
        pull_args = [remote]
        if branch:
            pull_args.append(branch)

        pull_result = self._executor.run("pull", *pull_args)
        if pull_result.exit_code != 0:
            # If pull fails due to conflict, abort
            self._executor.run("merge", "--abort")
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git pull failed: {pull_result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Synced from {remote}" + (f"/{branch}" if branch else ""),
        )

    def _intent_tag(self, context: dict[str, Any]) -> AtomResult:
        """Tag the current commit.

        Context keys:
            name: str — tag name.
        """
        name = context.get("name")
        if not name:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'name' in context for tag intent.",
            )

        result = self._executor.run("tag", name)
        if result.exit_code != 0:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"git tag failed: {result.stderr}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Tagged as: {name}",
            exports={"tag": name},
        )
