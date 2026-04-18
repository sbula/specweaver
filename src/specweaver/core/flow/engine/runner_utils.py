from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import logging

    from specweaver.core.flow.engine.models import PipelineDefinition, PipelineStep
    from specweaver.core.flow.engine.state import PipelineRun, StepResult
    from specweaver.core.flow.handlers import RunContext


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
