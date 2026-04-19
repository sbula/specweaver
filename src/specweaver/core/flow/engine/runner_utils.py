from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

if TYPE_CHECKING:
    import logging

    from specweaver.core.flow.engine.models import PipelineDefinition, PipelineStep
    from specweaver.core.flow.engine.state import PipelineRun, StepResult
    from specweaver.core.flow.handlers.base import RunContext



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
    import os

    cache_dirs = [
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        ".gradle",
        "target",
        "build",
        ".venv",
        "venv",
    ]
    for cache in cache_dirs:
        src = context.project_path / cache
        if src.exists() and src.is_dir():
            dst = context.project_path / wt_dir / cache
            try:
                os.symlink(src, dst, target_is_directory=True)
            except OSError as e:
                logger.warning(f"Could not symlink {cache} into worktree: {e}")

async def execute_in_sandbox(runner: Any, handler: Any, step_def: Any, run: Any, logger: logging.Logger) -> StepResult:
    """Execute a handler step inside an isolated Git worktree."""
    import copy

    from specweaver.core.loom.atoms.base import AtomStatus
    from specweaver.core.loom.atoms.git.atom import GitAtom

    context = runner._context

    atom = GitAtom(cwd=context.project_path)
    clean_pipeline = (context.pipeline_name or "default_pipe").replace(" ", "_")
    task_id = getattr(context, "task_id", getattr(context, "run_id", "default"))
    branch = f"sf-{clean_pipeline}-{task_id}"
    wt_path = f".worktrees/{task_id}"

    # 1. Add worktree
    add_res = atom.run({"intent": "worktree_add", "path": wt_path, "branch": branch})
    if add_res.status != AtomStatus.SUCCESS:
        raise RuntimeError(f"Failed to create sandbox worktree: {add_res.message}")

    setup_sandbox_caches(context, wt_path, logger)

    isolated_context = copy.copy(context)
    isolated_context.output_dir = context.project_path / wt_path
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
        if TYPE_CHECKING:
            from specweaver.core.flow.engine.state import StepResult
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
