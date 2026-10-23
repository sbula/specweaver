# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The session-worktree lifecycle around a whole run.

One ephemeral worktree for the entire run, reconciled once and torn down once — distinct from the
per-step isolation in `sandboxed_execution.py`, which
this deliberately suppresses while a session is active.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NoReturn, cast

from specweaver.core.flow.engine.sandboxed_execution import setup_sandbox_caches

if TYPE_CHECKING:
    from specweaver.core.flow.engine.state import PipelineRun

logger = logging.getLogger(__name__)


class SessionWorktreeError(RuntimeError):
    """The run's worktree could not start, or a resumed run's worktree is gone."""


async def execute_run(
    runner: Any,
    run: Any,
    logger: logging.Logger,
    *,
    approve_parked: bool = False,
) -> PipelineRun:
    """Run the loop, wrapping it in ONE session worktree when session isolation is on.

    ``approve_parked`` is forwarded to the loop: ``resume()`` passes True so a reviewed HITL
    gate-park advances instead of re-parking; ``run()`` never does, so the fresh-run path is
    unaffected.

    The whole run executes in a single ephemeral worktree (generated code persists across steps),
    reconciled once at the end and torn down once (worktree + branch). A parked run keeps its
    worktree when it has a store to resume from; the resume continues in it. Fail-closed: a
    non-git project, or a resume whose worktree is gone, raises.
    """
    context = runner._context
    if not context.isolation.session_isolation:
        return cast("PipelineRun", await runner._execute_loop(run, approve_parked=approve_parked))

    import copy

    from specweaver.core.flow.engine.state import RunStatus
    from specweaver.sandbox.base import AtomStatus
    from specweaver.sandbox.git.core.atom import GitAtom

    original = context
    atom = GitAtom(cwd=original.project_path)
    wt_path = f".worktrees/session-{run.run_id}"
    branch = f"sf-session-{run.run_id}"

    worktree = original.project_path / wt_path
    if approve_parked and run.current_step > 0:
        if not worktree.is_dir():
            raise SessionWorktreeError(
                f"Cannot resume: the run's worktree {wt_path} is gone, and with it the files of "
                "its earlier steps. Start the run again."
            )
    else:
        # Prune a stale same-named worktree and branch left by a crash, so the add cannot collide.
        atom.run({"intent": "worktree_teardown", "path": wt_path, "branch": branch})
        add_res = atom.run({"intent": "worktree_add", "path": wt_path, "branch": branch})
        if add_res.status != AtomStatus.SUCCESS:
            raise SessionWorktreeError(
                f"C-EXEC-06 session isolation could not start ({add_res.message}). "
                f"Ensure {original.project_path} is a git repository, or disable session isolation."
            )
        setup_sandbox_caches(original, wt_path, logger)

    isolated = copy.copy(original)
    isolated.project_path = original.project_path / wt_path
    isolated.output_dir = None
    # Shallow copy: rebind the whole attribute, don't edit the shared one. No per-step
    # isolation nested inside a session worktree.
    isolated.isolation = isolated.isolation.model_copy(
        update={"execution_root": isolated.project_path, "enforce_isolation": False}
    )
    runner._context = isolated
    runner._session_active = True
    try:
        result = cast("PipelineRun", await runner._execute_loop(run, approve_parked=approve_parked))
        # SF-02: reconcile ONLY on successful completion — never write back the generated
        # code of a failed/parked run. Commit the worktree, then a single authorized
        # strip-merge lands only allowed_paths in the real repo. Failures are surfaced.
        if run.status == RunStatus.COMPLETED:
            commit_res = atom.run({"intent": "worktree_commit", "path": wt_path})
            if commit_res.status != AtomStatus.SUCCESS:
                _reconcile_failed(
                    runner,
                    run,
                    f"C-EXEC-06 reconcile: worktree commit failed: {commit_res.message}",
                )
            merge_res = atom.run(
                {
                    "intent": "strip_merge",
                    "branch": branch,
                    "allowed_paths": original.isolation.allowed_paths,
                    "doc_policy": original.isolation.doc_policy,
                    # Each step's snapshot names it; the merge judges a file by those steps.
                    "steps_from_commits": True,
                }
            )
            if merge_res.status != AtomStatus.SUCCESS:
                _reconcile_failed(
                    runner,
                    run,
                    f"C-EXEC-06 reconcile: authorized strip-merge failed: {merge_res.message}",
                )
        return result
    finally:
        runner._session_active = False
        runner._context = original
        # A parked run keeps its worktree when it can be resumed.
        if not (run.status == RunStatus.PARKED and runner._store is not None):
            atom.run({"intent": "worktree_teardown", "path": wt_path, "branch": branch})


def _reconcile_failed(runner: Any, run: PipelineRun, message: str) -> NoReturn:
    """The run's work did not land: it is a failed run, in the store too, not a completed one."""
    from specweaver.core.flow.engine.state import RunStatus

    run.status = RunStatus.FAILED
    runner._persist(run)
    runner._emit("run_failed", run=run)
    raise RuntimeError(message)
