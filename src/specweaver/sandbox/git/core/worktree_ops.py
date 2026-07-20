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
        _delete_branch_if_present(executor, context)
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
    _delete_branch_if_present(executor, context)

    return AtomResult(
        status=AtomStatus.SUCCESS,
        message=f"Fallback: Removed worktree {path} via rmtree.",
    )


def _delete_branch_if_present(executor: "EngineGitExecutor", context: dict[str, Any]) -> None:
    """C-EXEC-06: delete the session branch after its worktree is removed.

    Best-effort — the per-run session owns a unique branch and must not leak it (fixing the
    INT-US-09 orphan-branch defect). No ``branch`` key → no-op (per-step teardown unchanged).
    """
    branch = context.get("branch")
    if not branch:
        return
    try:
        res = executor.run("branch", "-D", branch)
        if getattr(res, "exit_code", 0) != 0:
            logger.warning(
                "Could not delete session branch '%s': %s", branch, getattr(res, "stderr", "")
            )
    except Exception as exc:  # best-effort: never let branch cleanup break teardown
        logger.warning("Branch delete raised for '%s': %s", branch, exc)


def handle_worktree_commit(executor: "EngineGitExecutor") -> AtomResult:
    """C-EXEC-06: commit the session worktree's accumulated changes onto its branch.

    Runs INSIDE the worktree (``executor`` bound to the worktree path). Stages everything and
    commits so the reconcile (``strip_merge``) has committed changes to merge back (fixes the
    ``TECH-012`` Gap 1 where nothing was ever committed). A clean worktree is a no-op — no empty
    commit — after which ``strip_merge`` finds an empty diff and cleanly no-ops.
    """
    executor.run("add", "-A")
    diff = executor.run("diff", "--cached", "--quiet")
    if getattr(diff, "exit_code", 0) == 0:
        return AtomResult(
            status=AtomStatus.SUCCESS, message="Nothing to commit.", exports={"committed": False}
        )
    commit = executor.run("commit", "-m", "chore(sandbox): session snapshot")
    if getattr(commit, "exit_code", 0) != 0:
        return AtomResult(
            status=AtomStatus.FAILED,
            message=f"Session commit failed: {getattr(commit, 'stderr', '')}",
        )
    return AtomResult(
        status=AtomStatus.SUCCESS, message="Committed session snapshot.", exports={"committed": True}
    )


def _strip_forbidden_files(
    executor: "EngineGitExecutor", cwd: Path, changed_files: list[str], allowed_paths: list[str]
) -> list[str]:
    """Strip files not in ``allowed_paths`` (+ README/docs hard-block) from the staged merge.

    For an existing file, restore its HEAD version; for a newly-added file (no HEAD version),
    delete it from the working tree so a stripped file never reaches the real repo (C-EXEC-06).
    ``doc_updates.md`` is always allowed to survive.
    """
    stripped: list[str] = []
    for file in changed_files:
        if file.endswith("doc_updates.md"):
            continue
        if file == "README.md" or file.startswith("docs/") or file not in allowed_paths:
            stripped.append(file)
            executor.run("reset", "HEAD", file)
            checkout_res = executor.run("checkout", "--", file)
            if getattr(checkout_res, "exit_code", 0) != 0:
                fpath = cwd / file
                if fpath.exists():
                    fpath.unlink()
    return stripped


def handle_strip_merge(
    executor: "EngineGitExecutor", cwd: Path, context: dict[str, Any]
) -> AtomResult:
    """Merges a worktree branch mathematically stripping forbidden diff hunks."""
    branch = context.get("branch")
    allowed_paths = context.get("allowed_paths")

    if not branch or allowed_paths is None:
        return AtomResult(
            status=AtomStatus.FAILED,
            message="Missing 'branch' or 'allowed_paths' in context for strip_merge intent.",
        )

    # 1. Merge the branch but don't commit it yet.
    merge_res = executor.run("merge", "--no-commit", "--no-ff", branch, "-X", "ours")
    if getattr(merge_res, "exit_code", 0) != 0:
        # A dirty real working tree (uncommitted changes the merge would clobber) makes git
        # refuse. Abort so the repo is left clean; surface a clear, actionable failure (Q2/Q5).
        executor.run("merge", "--abort")
        return AtomResult(
            status=AtomStatus.FAILED,
            message=(
                "reconcile git merge failed (likely uncommitted changes in the real working "
                f"tree — commit or stash them first). Detail: {getattr(merge_res, 'stderr', '')}"
            ),
        )

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

    stripped_files = _strip_forbidden_files(executor, cwd, changed_files, allowed_paths)

    # 3. If stripping removed EVERYTHING, don't create a noise merge commit — abort cleanly.
    # (git would otherwise still complete the in-progress merge with an empty commit.)
    post_strip = executor.run("diff", "--cached", "--quiet")
    if getattr(post_strip, "exit_code", 0) == 0:
        executor.run("merge", "--abort")
        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="All changes were mathematically stripped. Nothing merged.",
            exports={"stripped_files": stripped_files},
        )

    # 4. Commit the surviving hunks
    commit_res = executor.run(
        "commit", "-m", f"chore(sandbox): mathematical diff strip merge from {branch}"
    )
    if commit_res.exit_code != 0:
        executor.run("merge", "--abort")
        return AtomResult(
            status=AtomStatus.FAILED,
            message=f"Failed to commit stripped merge: {commit_res.stderr}",
        )

    return AtomResult(
        status=AtomStatus.SUCCESS,
        message=f"Successfully merged cleanly, stripped {len(stripped_files)} files.",
        exports={"stripped_files": stripped_files},
    )
