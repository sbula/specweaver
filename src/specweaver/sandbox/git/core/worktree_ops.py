# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Helper intent implementations for GitAtom to manage worktrees and merges."""

import logging
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from specweaver.sandbox.git.core.engine_executor import EngineGitExecutor

logger = logging.getLogger(__name__)


def handle_worktree_teardown(
    executor: "EngineGitExecutor", cwd: Path, context: dict[str, Any]
) -> AtomResult:
    """Resiliently removes a Git worktree."""
    path = context.get("path")
    if not path:
        return AtomResult(
            status=AtomStatus.FAILED,
            message="Missing 'path' in context for worktree_teardown intent.",
        )

    # Primary vector
    result = executor.run("worktree", "remove", "--force", str(path))
    if result.exit_code == 0:
        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Removed worktree cleanly: {path}",
        )

    # Windows file locking fallback
    wt_path = cwd / path
    logger.warning("Git worktree remove failed: %s. Engaging shutil fallback.", result.stderr)

    if wt_path.exists():
        # NFR-1 / NFR-3: 5 iteration progressive backoff under 2s total
        delays = [0.05, 0.1, 0.2, 0.4, 0.75]
        for attempt, delay in enumerate(delays):
            try:
                shutil.rmtree(wt_path, ignore_errors=False)
                break
            except Exception as e:
                if attempt == len(delays) - 1:
                    return AtomResult(
                        status=AtomStatus.FAILED,
                        message=f"Fallback rmtree failed: {e!s}",
                    )
                time.sleep(delay)

    # Cleanup Git index
    executor.run("worktree", "prune")

    return AtomResult(
        status=AtomStatus.SUCCESS,
        message=f"Fallback: Removed worktree {path} via rmtree.",
    )


def handle_strip_merge(executor: "EngineGitExecutor", context: dict[str, Any]) -> AtomResult:
    """Merges a worktree branch mathematically stripping forbidden diff hunks."""
    branch = context.get("branch")
    allowed_paths = context.get("allowed_paths")

    if not branch or allowed_paths is None:
        return AtomResult(
            status=AtomStatus.FAILED,
            message="Missing 'branch' or 'allowed_paths' in context for strip_merge intent.",
        )

    # 1. Merge the branch but don't commit it yet
    executor.run("merge", "--no-commit", "--no-ff", branch, "-X", "ours")

    # 2. Extract changed files from the pending index
    diff_res = executor.run("diff", "--name-only", "--cached")
    if diff_res.exit_code != 0:
        # Clean up state on crash
        executor.run("merge", "--abort")
        return AtomResult(
            status=AtomStatus.FAILED,
            message=f"Failed to read index: {diff_res.stderr}",
        )

    changed_files = [f.strip() for f in diff_res.stdout.split("\n") if f.strip()]
    if not changed_files:
        # Nothing changed
        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="No changes to strip and merge.",
            exports={"stripped_files": []},
        )

    stripped_files = []
    for file in changed_files:
        # FR-8 explicitly allows isolated documentation claims to survive
        if file.endswith("doc_updates.md"):
            continue

        # Check NFR-4 Blocklist and FR-4 Allowlist
        if file == "README.md" or file.startswith("docs/") or file not in allowed_paths:
            stripped_files.append(file)
            # Revert this file's staged changes back to HEAD
            executor.run("reset", "HEAD", file)
            executor.run("checkout", "--", file)

    # 3. Commit the surviving hunks
    commit_res = executor.run(
        "commit", "-m", f"chore(sandbox): mathematical diff strip merge from {branch}"
    )
    if commit_res.exit_code != 0:
        # It's possible that stripping removed ALL changes, so commit fails.
        executor.run("merge", "--abort")
        if len(stripped_files) == len(changed_files):
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message="All changes were mathematically stripped. Nothing merged.",
                exports={"stripped_files": stripped_files},
            )
        return AtomResult(
            status=AtomStatus.FAILED,
            message=f"Failed to commit stripped merge: {commit_res.stderr}",
        )

    return AtomResult(
        status=AtomStatus.SUCCESS,
        message=f"Successfully merged cleanly, stripped {len(stripped_files)} files.",
        exports={"stripped_files": stripped_files},
    )
