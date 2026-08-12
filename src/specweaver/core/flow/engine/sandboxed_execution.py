# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Running ONE step inside its own ephemeral git worktree.

Split out of `runner_utils.py` by `TECH-015`. The per-step INT-US-09 path, as distinct from
`session.py`'s per-run C-EXEC-06 worktree — the two are mutually exclusive at runtime and were
easier to confuse while they shared a file that named neither.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from specweaver.core.flow.engine.state import StepResult
    from specweaver.core.flow.handlers.base import RunContext

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

    from specweaver.sandbox.base import AtomStatus
    from specweaver.sandbox.git.core.atom import GitAtom

    context = runner._context

    atom = GitAtom(cwd=context.project_path)
    # From the run: the old context field was never set, so every branch was "sf-default_pipe-".
    clean_pipeline = (run.pipeline_name or "default_pipe").replace(" ", "_")
    # May be None, giving a branch named "...-None". Pre-existing; left alone.
    task_id = context.run.task_id
    branch = f"sf-{clean_pipeline}-{task_id}"
    wt_path = f".worktrees/{task_id}"

    # 1. Add worktree
    add_res = atom.run({"intent": "worktree_add", "path": wt_path, "branch": branch})
    if add_res.status != AtomStatus.SUCCESS:
        # INT-US-09 fail-closed: isolation was requested (per-step or policy) but the
        # worktree could not be created. Surface GitAtom's ACTUAL failure (do not assume
        # the cause) plus an actionable hint — the most common cause is a non-git project.
        raise RuntimeError(
            f"US-9 worktree isolation could not start ({add_res.message}). "
            f"Ensure {context.project_path} is a git repository, or disable "
            f"[sandbox].enforce_worktree_isolation (and any per-step use_worktree)."
        )

    setup_sandbox_caches(context, wt_path, logger)

    isolated_context = copy.copy(context)
    isolated_context.output_dir = context.project_path / wt_path
    # INT-US-09: rebind the execution root to the worktree source tree so untrusted-
    # execution handlers (bash actions, run_tests) construct their SubprocessExecutor
    # cwd inside the worktree rather than against the real project root.
    # Shallow copy: rebind the whole attribute, don't edit the shared one.
    isolated_context.isolation = isolated_context.isolation.model_copy(
        update={"execution_root": context.project_path / wt_path}
    )

    try:
        # 2. Execute inner handler bounded to the isolated worktree context
        result = await handler.execute(step_def, isolated_context)

        # 3. Continuous Micro-Sync (FR-7)
        atom.run({"intent": "worktree_sync", "path": wt_path})

        # 4. Mathematical diff striping (FR-4, FR-5, NFR-4)
        strip_res = atom.run(
            {
                "intent": "strip_merge",
                "branch": branch,
                "allowed_paths": context.isolation.allowed_paths,
            }
        )
        if strip_res.status != AtomStatus.SUCCESS:
            logger.warning(f"Sandbox diff striping returned non-success: {strip_res.message}")
        return cast("StepResult", result)

    finally:
        # 5. Teardown resilience
        atom.run({"intent": "worktree_teardown", "path": wt_path})

        # 6. Database Cleanup Hooks bounds guarantee zombie block survival
        try:
            from specweaver.core.flow.engine.reservation import SQLiteReservationSystem

            db_path = context.project_path / ".specweaver" / "reservations.db"
            SQLiteReservationSystem(db_path).release(run.run_id)
        except Exception as e:
            logger.error("[run_id=%s] Sandbox DB teardown bounds panic: %s", run.run_id, e)
