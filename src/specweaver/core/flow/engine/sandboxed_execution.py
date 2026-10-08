# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Running ONE step inside its own ephemeral git worktree.

The per-step path, as distinct from `session.py`'s per-run worktree. The two are mutually exclusive
at runtime, so they live in files that name which is which.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from specweaver.infrastructure.llm.budget import step_refusal

if TYPE_CHECKING:
    from specweaver.core.flow.engine.state import StepResult
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def setup_sandbox_caches(context: RunContext, wt_dir: str, logger: logging.Logger) -> None:
    """Symlink heavy project caches into the worktree to save disk space (FR-2)."""
    from specweaver.sandbox.base import AtomStatus
    from specweaver.sandbox.filesystem.core.atom import FileSystemAtom

    cache_dirs = [
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        ".gradle",
        "target",
        "build",
        ".venv",
        "venv",
        ".specweaver",
    ]
    atom = FileSystemAtom(cwd=context.project_path)
    for cache in cache_dirs:
        src = context.project_path / cache
        if src.exists() and src.is_dir():
            link_name = f"{wt_dir}/{cache}"
            res = atom.run(
                {
                    "intent": "symlink",
                    "target": cache,
                    "link_name": link_name,
                }
            )
            if res.status != AtomStatus.SUCCESS:
                logger.warning(f"Could not symlink {cache} into worktree: {res.message}")


async def execute_in_sandbox(
    runner: Any, handler: Any, step_def: Any, run: Any, logger: logging.Logger
) -> StepResult:
    """Execute a handler step inside an isolated Git worktree."""
    import copy

    from specweaver.core.flow.engine.isolation import derive_allowed_paths
    from specweaver.core.flow.engine.state import StepStatus
    from specweaver.sandbox.base import AtomStatus
    from specweaver.sandbox.git.core.atom import GitAtom

    context = runner._context

    atom = GitAtom(cwd=context.project_path)
    clean_pipeline = (run.pipeline_name or "default_pipe").replace(" ", "_")
    task_id = context.run.task_id or run.run_id
    branch = f"sf-{clean_pipeline}-{task_id}"
    wt_path = f".worktrees/{task_id}"

    # Prune a stale same-named worktree and branch left by a crash, so the add cannot collide.
    atom.run({"intent": "worktree_teardown", "path": wt_path, "branch": branch})
    add_res = atom.run({"intent": "worktree_add", "path": wt_path, "branch": branch})
    if add_res.status != AtomStatus.SUCCESS:
        # Fail closed: isolation was requested but the worktree could not be created.
        raise RuntimeError(
            f"US-9 worktree isolation could not start ({add_res.message}). "
            f"Ensure {context.project_path} is a git repository, or disable "
            f"[sandbox].enforce_worktree_isolation (and any per-step use_worktree)."
        )

    setup_sandbox_caches(context, wt_path, logger)

    # The step sees the worktree as its project, as a session step does.
    worktree = context.project_path / wt_path
    isolated_context = copy.copy(context)
    isolated_context.project_path = worktree
    isolated_context.output_dir = None
    isolated_context.isolation = isolated_context.isolation.model_copy(
        update={"execution_root": worktree}
    )

    try:
        result = cast("StepResult", await handler.execute(step_def, isolated_context))
        if step_refusal() is not None or result.status != StepStatus.PASSED:
            return result  # a stopped or failed step lands nothing

        commit_res = atom.run({"intent": "worktree_commit", "path": wt_path})
        if commit_res.status != AtomStatus.SUCCESS:
            raise RuntimeError(f"worktree commit failed: {commit_res.message}")
        merge_res = atom.run(
            {
                "intent": "strip_merge",
                "branch": branch,
                "allowed_paths": context.isolation.allowed_paths
                or derive_allowed_paths(context.spec_path),
            }
        )
        if merge_res.status != AtomStatus.SUCCESS:
            raise RuntimeError(f"authorized strip-merge failed: {merge_res.message}")
        return result

    finally:
        atom.run({"intent": "worktree_teardown", "path": wt_path, "branch": branch})

        try:
            from specweaver.core.flow.engine.reservation import SQLiteReservationSystem

            db_path = context.project_path / ".specweaver" / "reservations.db"
            SQLiteReservationSystem(db_path).release(run.run_id)
        except Exception as e:
            logger.error("[run_id=%s] Sandbox DB teardown bounds panic: %s", run.run_id, e)
