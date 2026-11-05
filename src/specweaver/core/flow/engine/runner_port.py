# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the runner's helper functions use of the runner — the runner's side of the loop seam.

`step_execution`, `session`, `approval` and `sandboxed_execution` take the runner as their first
argument; this names every member they read or write, so none reaches into a private field.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from specweaver.core.flow.engine.gates import GateEvaluator
    from specweaver.core.flow.engine.handler_port import HandlerLookup
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.routers import RouterEvaluator
    from specweaver.core.flow.engine.state import PipelineRun
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.core.flow.run_state.run_context import RunContext


@runtime_checkable
class RunnerPort(Protocol):
    """The runner as its helpers see it."""

    #: Rebound by `session.execute_run` to the session worktree's context, and back.
    context: RunContext
    pipeline: PipelineDefinition
    registry: HandlerLookup
    store: StateStore | None
    gate_evaluator: GateEvaluator
    router_evaluator: RouterEvaluator
    #: True while `session.execute_run` runs the loop inside one session worktree.
    session_active: bool
    #: True once a failed snapshot or reconcile keeps the session worktree for the user.
    session_kept: bool

    def persist(self, run: PipelineRun) -> None: ...

    def log_event(self, run: PipelineRun, event: str, step_name: str | None = None) -> None: ...

    def emit(self, event: str, **kwargs: Any) -> None: ...

    async def execute_loop(
        self, run: PipelineRun, *, approve_parked: bool = False
    ) -> PipelineRun: ...
