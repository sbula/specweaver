from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineDefinition, PipelineStep
    from specweaver.core.flow.engine.state import PipelineRun, StepResult
    from specweaver.core.flow.handlers.base import RunContext


def resolve_should_isolate(step_def: Any, context: Any) -> bool:
    """INT-US-09 tri-state worktree-isolation gate resolution.

    An explicit per-step ``use_worktree`` (``True``/``False``) wins; ``None`` — or a
    missing attribute — defers to the US-9 isolation policy (``context.enforce_isolation``,
    resolved at the composition root). Both reads are defensive (``getattr`` with a default)
    so a partially-populated step or context never crashes the runner, and the result is a
    strict ``bool``.
    """
    step_val = getattr(step_def, "use_worktree", None)
    if step_val is not None:
        return bool(step_val)
    return bool(getattr(context, "enforce_isolation", False))


def _derive_allowed_paths(spec_path: Path) -> list[str]:
    """C-EXEC-06 SF-03 (FR-5, AD-2): the reconcile allow-list from the spec stem.

    Mirrors the pipeline's generation targets so the single end-of-run strip-merge
    authorizes exactly the files the run actually generates. Inside a session,
    ``execute_run`` nulls ``output_dir``, so the generation handlers fall back to their
    defaults (``src/<stem>.py`` / ``tests/test_<stem>.py``) — hence the ``src/``/``tests/``
    prefixes here, not the composition-root ``output_dir``.

    The stem transform MUST stay byte-identical to the generation handlers
    (``generation.py``: ``spec_path.stem.replace("_spec", "")`` — note ``.replace``, NOT
    ``.removesuffix``: it removes every ``_spec`` substring). If it drifts, the derived
    allow-list stops matching the generated path and the real file gets stripped.

    Paths are repo-relative with forward slashes (git ``--name-only`` form on every
    platform, including Windows) — never ``os.sep``.
    """
    stem = spec_path.stem.replace("_spec", "")
    return [f"src/{stem}.py", f"tests/test_{stem}.py"]


def apply_session_policy(
    context: RunContext,
    settings: Any,
    logger: logging.Logger,
    *,
    dal_auto_escalate: bool = False,
) -> None:
    """C-EXEC-06 SF-03 (FR-5, FR-7): freeze per-run isolation policy onto the context.

    Called at the composition root (ADR-002). Reads the opt-in ``[sandbox]`` knobs and,
    **only when per-run isolation is on**, populates ``allowed_paths`` (the configured
    override, else the derived generation targets).

    ``dal_auto_escalate`` (INT-US-03 SF-03, AD-8): when True and the explicit
    ``enforce_session_isolation`` flag is off, the policy auto-enables session isolation if
    the touched code's resolved DAL is at/above the ``auto_isolate_min_dal`` threshold
    (default ``DAL_B``). This is **opt-in per caller** — ``sw implement`` passes True;
    ``sw run``/``sw resume`` leave it False, so their behavior is byte-identical (escalation
    never even resolves a DAL for them).

    NFR-2 guard: when the policy is OFF, ``allowed_paths`` is left EMPTY — the per-step
    INT-US-09 path (``execute_in_sandbox``) also reads ``allowed_paths``, so populating it
    here would silently change per-step ``strip_merge`` behavior.

    C2 (no half-apply): the allow-list is computed BEFORE either field is mutated, so a
    derivation failure leaves the context fully default (session off) rather than the
    dangerous "session on, empty allow-list" state that would drop all generated code.
    Best-effort: never raises (the composition root also wraps this call defensively).
    """
    try:
        sandbox = getattr(settings, "sandbox", None)
        session_on = bool(getattr(sandbox, "enforce_session_isolation", False))
        if not session_on and dal_auto_escalate:
            session_on = _dal_requires_isolation(context, sandbox, logger)
        if not session_on:
            context.session_isolation = False
            return
        override = list(getattr(sandbox, "session_allowed_paths", None) or [])
        allowed = override or _derive_allowed_paths(context.spec_path)
        context.session_isolation = True
        context.allowed_paths = allowed
    except Exception:  # best-effort — a policy-resolution failure must never crash a run
        logger.debug(
            "Could not apply per-run session-isolation policy; leaving it off.",
            exc_info=True,
        )


def _dal_requires_isolation(context: RunContext, sandbox: Any, logger: logging.Logger) -> bool:
    """INT-US-03 SF-03 (AD-8): does the touched code's DAL meet the escalation threshold?

    Reads ``auto_isolate_min_dal`` (a ``DALLevel`` name, or ``"off"`` to disable). Resolves
    the run's DAL the same way ``PipelineRunner`` does (``spec_path`` if it exists, else
    ``project_path``), reusing ``context.dal_level`` when already set and caching the result
    back onto it so the runner does not re-resolve. Returns True iff the resolved DAL is at
    or above the threshold in strictness. Any failure ⇒ False (the caller stays on host).
    """
    from specweaver.commons.enums.dal import DALLevel
    from specweaver.core.config.dal_resolver import DALResolver

    threshold_raw = getattr(sandbox, "auto_isolate_min_dal", "DAL_B")
    if not threshold_raw or str(threshold_raw).lower() == "off":
        return False
    threshold = DALLevel(threshold_raw)

    dal = getattr(context, "dal_level", None)
    if dal is None:
        target = context.spec_path if context.spec_path.exists() else context.project_path
        dal = DALResolver(context.project_path).resolve(target)
        context.dal_level = dal  # cache — the runner skips its own resolution
    if dal is None or dal.rank < threshold.rank:
        return False

    # Q3: auto-escalation must NEVER break the command. If the project cannot host a git
    # worktree (not a git repo), degrade to host mode with a warning instead of failing.
    # (An explicit ``enforce_session_isolation`` still fails-closed at ``execute_run``.)
    if not (context.project_path / ".git").exists():
        logger.warning(
            "DAL %s meets the auto-isolation threshold %s but %s is not a git repository; "
            "running the loop on host (unsandboxed). `git init` to enable worktree isolation.",
            dal.value,
            threshold.value,
            context.project_path,
        )
        return False
    return True


async def execute_run(runner: Any, run: Any, logger: logging.Logger) -> PipelineRun:
    """C-EXEC-06: run the loop, wrapping it in ONE session worktree when session isolation is on.

    The whole run executes in a single ephemeral worktree (generated code persists across steps),
    reconciled once at the end (reconcile lands in SF-02) and torn down once (worktree + branch).
    Fail-closed: a non-git project raises. Default-off: the path is byte-identical to before.
    """
    context = runner._context
    if not getattr(context, "session_isolation", False):
        return cast("PipelineRun", await runner._execute_loop(run))

    import copy

    from specweaver.core.flow.engine.state import RunStatus
    from specweaver.sandbox.base import AtomStatus
    from specweaver.sandbox.git.core.atom import GitAtom

    original = context
    atom = GitAtom(cwd=original.project_path)
    wt_path = f".worktrees/session-{run.run_id}"
    branch = f"sf-session-{run.run_id}"

    # Idempotent create: prune a stale same-named worktree+branch left by a hard crash that
    # skipped a prior teardown, so worktree_add doesn't collide (Q3).
    atom.run({"intent": "worktree_teardown", "path": wt_path, "branch": branch})
    add_res = atom.run({"intent": "worktree_add", "path": wt_path, "branch": branch})
    if add_res.status != AtomStatus.SUCCESS:
        raise RuntimeError(
            f"C-EXEC-06 session isolation could not start ({add_res.message}). "
            f"Ensure {original.project_path} is a git repository, or disable session isolation."
        )
    setup_sandbox_caches(original, wt_path, logger)

    isolated = copy.copy(original)
    isolated.project_path = original.project_path / wt_path
    isolated.execution_root = isolated.project_path
    isolated.output_dir = None
    isolated.enforce_isolation = False  # no per-step isolation nested inside the session
    runner._context = isolated
    runner._session_active = True
    try:
        result = cast("PipelineRun", await runner._execute_loop(run))
        # AD-4 (v1): a park inside a session is unsupported — the worktree is torn down in
        # finally, so parked state cannot survive a resume. Fail clearly.
        if run.status == RunStatus.PARKED:
            raise RuntimeError(
                "C-EXEC-06 session isolation does not support HITL parking (v1): the ephemeral "
                "worktree cannot persist across resume. Disable session isolation for HITL pipelines."
            )
        # SF-02: reconcile ONLY on successful completion — never write back the generated
        # code of a failed/parked run. Commit the worktree, then a single authorized
        # strip-merge lands only allowed_paths in the real repo. Failures are surfaced.
        if run.status == RunStatus.COMPLETED:
            commit_res = atom.run({"intent": "worktree_commit", "path": wt_path})
            if commit_res.status != AtomStatus.SUCCESS:
                raise RuntimeError(
                    f"C-EXEC-06 reconcile: worktree commit failed: {commit_res.message}"
                )
            merge_res = atom.run(
                {"intent": "strip_merge", "branch": branch, "allowed_paths": original.allowed_paths}
            )
            if merge_res.status != AtomStatus.SUCCESS:
                raise RuntimeError(
                    f"C-EXEC-06 reconcile: authorized strip-merge failed: {merge_res.message}"
                )
        return result
    finally:
        runner._session_active = False
        runner._context = original
        atom.run({"intent": "worktree_teardown", "path": wt_path, "branch": branch})


@runtime_checkable
class RunnerEventCallback(Protocol):
    """Protocol for runner event callbacks."""

    def __call__(
        self,
        event: str,
        *,
        step_idx: int | None = None,
        step_name: str | None = None,
        step_def: PipelineStep | None = None,
        total_steps: int | None = None,
        result: StepResult | None = None,
        run: PipelineRun | None = None,
        verdict: str | None = None,
        **kwargs: Any,
    ) -> None: ...


async def run_fan_out(
    runner: Any, sub_pipelines: list[PipelineDefinition], parent_run_id: str
) -> list[PipelineRun]:
    """Execute multiple sub-pipelines concurrently and await their completion.

    Args:
        runner: The parent PipelineRunner instance.
        sub_pipelines: List of PipelineDefinitions to run concurrently.
        parent_run_id: The run ID of the executing step's parent pipeline.

    Returns:
        A list of completed PipelineRun states, one for each sub-pipeline.
    """
    import asyncio

    # Needs to be imported inside or passed properly
    from specweaver.core.flow.engine.runner import PipelineRunner

    runners = [
        PipelineRunner(
            pipe,
            runner._context,
            registry=runner._registry,
            store=runner._store,
            on_event=runner._on_event,
        )
        for pipe in sub_pipelines
    ]
    return list(await asyncio.gather(*[r.run(parent_run_id=parent_run_id) for r in runners]))


def _now_iso() -> str:
    """Return the current time in ISO format."""
    return datetime.now(UTC).isoformat()


def flush_telemetry(context: RunContext, logger: logging.Logger) -> None:
    """Flush telemetry if context.llm is a TelemetryCollector."""
    from specweaver.infrastructure.llm.collector import TelemetryCollector

    llm = getattr(context, "llm", None)
    if not isinstance(llm, TelemetryCollector):
        return

    db = getattr(context, "db", None)
    if db is None:
        logger.warning("Cannot flush telemetry: no db on RunContext")
        return

    try:
        llm.flush(db)
    except Exception:
        logger.warning("Failed to flush telemetry", exc_info=True)


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


def verify_vault_security(context: RunContext) -> None:
    """Feature 3.32c SF-1: Safe Vault Binding Audit (Option D)."""
    vault_path = context.project_path / ".specweaver" / "vault.env"
    if vault_path.exists():
        from specweaver.sandbox.git.core.atom import GitAtom

        git_atom = GitAtom(cwd=context.project_path)
        # Check if tracked
        result = git_atom.run({"intent": "is_tracked", "path": ".specweaver/vault.env"})
        if getattr(result, "exports", {}).get("is_tracked", False):
            raise RuntimeError(
                "FATAL: vault.env is currently tracked by Git! Aborting execution to prevent credential leakage."
            )


async def execute_in_sandbox(
    runner: Any, handler: Any, step_def: Any, run: Any, logger: logging.Logger
) -> StepResult:
    """Execute a handler step inside an isolated Git worktree."""
    import copy

    from specweaver.sandbox.base import AtomStatus
    from specweaver.sandbox.git.core.atom import GitAtom

    context = runner._context

    atom = GitAtom(cwd=context.project_path)
    clean_pipeline = (context.pipeline_name or "default_pipe").replace(" ", "_")
    task_id = getattr(context, "task_id", getattr(context, "run_id", "default"))
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
    isolated_context.execution_root = context.project_path / wt_path
    isolated_context.env_vars = context.env_vars.copy()

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
                "allowed_paths": getattr(context, "allowed_paths", []),
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
