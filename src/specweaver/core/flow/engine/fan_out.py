# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Spawning sub-runs, and giving each one its own identity.

Both members exist only because of fan-out: `run_fan_out` dispatches the sub-runners, and
`isolate_sub_run_context` is what stops them reading each other's `run_id`. They belong together —
the isolation is not a general context utility, it is the invariant fan-out depends on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.state import PipelineRun
    from specweaver.core.flow.handlers.run_context import RunContext


def isolate_sub_run_context(context: RunContext, parent_run_id: str | None) -> RunContext:
    """Give a sub-run its own `RunContext`, or hand a top-level run the one it was given.

    Fan-out hands the **same** `RunContext` object to every concurrent sub-runner — four sites
    across `handlers/decompose.py` and `handlers/dual_pipeline.py`, all reaching through
    `context.run.pipeline_runner._context` — while `_execute_loop` rebinds `context.run` on every
    step. Shared object + per-step rebind + real concurrency means a sub-run reads a sibling's
    `run_id`, so lineage and telemetry were attributed to the wrong sub-run. Measured as **every**
    step, not an occasional interleave.

    `parent_run_id is not None` is exactly "I am a sub-run": all four fan-out sites pass it, no
    top-level caller does. That keeps the fifteen top-level construction sites — the API and eight
    CLI entrypoints — on today's semantics, where the caller hands in a context and reads its own
    reference back. Nested fan-out re-copies at each level, which is correct.

    The copy is deliberately **shallow**: only `run` is rebound per step, so paths, providers and
    adapters stay shared by reference as the read-only infrastructure they are.

    Lives here rather than inline in `runner.py`, which sits against its 600-line RED threshold.
    """
    if parent_run_id is None:
        return context
    return context.model_copy()


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

    runners = [runner.spawn(pipe) for pipe in sub_pipelines]
    return list(await asyncio.gather(*[r.run(parent_run_id=parent_run_id) for r in runners]))
