# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Gate evaluation logic for pipeline steps.

Extracted from the pipeline runner to allow independent testing and
future extension (e.g., JOIN gates for parallel pipelines).

A gate evaluates the result of a pipeline step and decides the next
action: advance, stop, retry, loop back, or park for human approval.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.models import GateCondition, GateType, OnFailAction
from specweaver.core.flow.state import StepStatus

if TYPE_CHECKING:
    from specweaver.core.flow.models import GateDefinition, PipelineDefinition, PipelineStep
    from specweaver.core.flow.state import PipelineRun, StepResult

logger = logging.getLogger(__name__)


class GateEvaluator:
    """Evaluates gate conditions and decides the next pipeline action.

    Args:
        pipeline: The pipeline definition (for step name lookups).
    """

    def __init__(self, pipeline: PipelineDefinition) -> None:
        self._pipeline = pipeline

    def evaluate(
        self,
        gate: GateDefinition,
        result: StepResult,
        step_def: PipelineStep,
        run: PipelineRun,
        attempts: dict[int, int],
    ) -> str:
        """Evaluate a gate and return an action string.

        Returns one of: 'advance', 'stop', 'retry', 'loop_back', 'park'.
        """
        # HITL gate: always park for human approval
        if gate.type == GateType.HITL:
            logger.info("Gate on step '%s': HITL — parking for human review", step_def.name)
            run.park_current_step(result)
            return "park"

        # AUTO gate: check condition
        if self.passes(gate, result):
            logger.debug(
                "Gate on step '%s': condition %s PASSED", step_def.name, gate.condition.value
            )
            return "advance"

        # Gate failed — apply on_fail action
        logger.debug(
            "Gate on step '%s': condition %s FAILED (result_status=%s, on_fail=%s)",
            step_def.name,
            gate.condition.value,
            result.status.value,
            gate.on_fail.value,
        )
        if gate.on_fail == OnFailAction.ABORT:
            run.fail_current_step(result)
            return "stop"

        if gate.on_fail == OnFailAction.RETRY:
            return self._handle_retry(gate, result, run, attempts)

        if gate.on_fail == OnFailAction.LOOP_BACK:
            return self._handle_loop_back(gate, result, run, attempts)

        if gate.on_fail == OnFailAction.CONTINUE:
            logger.debug(
                "Gate on step '%s': on_fail=CONTINUE — advancing despite failure", step_def.name
            )
            return "advance"

        return "advance"

    def passes(self, gate: GateDefinition, result: StepResult) -> bool:
        """Check if the gate condition is met."""
        if gate.condition == GateCondition.ALL_PASSED:
            return result.status == StepStatus.PASSED
        if gate.condition == GateCondition.ACCEPTED:
            return result.output.get("verdict") == "accepted"
        if gate.condition == GateCondition.COMPLETED:
            return result.status not in (StepStatus.FAILED, StepStatus.ERROR)
        return True

    def find_step_index(self, step_name: str) -> int | None:
        """Find the index of a step by name."""
        for i, step in enumerate(self._pipeline.steps):
            if step.name == step_name:
                return i
        return None

    @staticmethod
    def inject_feedback(
        context: Any,
        from_step: str,
        to_step: str,
        result: StepResult,
    ) -> None:
        """Inject step result as feedback into RunContext."""
        if not hasattr(context, "feedback"):
            context.feedback = {}
        context.feedback[to_step] = {
            "from_step": from_step,
            "findings": result.output,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_retry(
        self,
        gate: GateDefinition,
        result: StepResult,
        run: PipelineRun,
        attempts: dict[int, int],
    ) -> str:
        """Handle RETRY on_fail action."""
        step_idx = run.current_step
        attempts[step_idx] = attempts.get(step_idx, 0) + 1
        if attempts[step_idx] <= gate.max_retries:
            logger.info(
                "Gate retry: step %d attempt %d/%d",
                step_idx,
                attempts[step_idx],
                gate.max_retries,
            )
            record = run.current_step_record()
            if record is not None:
                record.status = StepStatus.PENDING
                record.attempt = attempts[step_idx] + 1
            return "retry"
        # Retries exhausted
        logger.warning(
            "Gate retry exhausted: step %d used %d/%d attempts",
            step_idx,
            attempts[step_idx],
            gate.max_retries,
        )
        run.fail_current_step(result)
        return "stop"

    def _handle_loop_back(
        self,
        gate: GateDefinition,
        result: StepResult,
        run: PipelineRun,
        attempts: dict[int, int],
    ) -> str:
        """Handle LOOP_BACK on_fail action."""
        step_idx = run.current_step
        attempts[step_idx] = attempts.get(step_idx, 0) + 1
        if attempts[step_idx] <= gate.max_retries:
            target_idx = self.find_step_index(gate.loop_target or "")
            if target_idx is not None:
                logger.info(
                    "Gate loop-back: step %d → target step %d ('%s'), attempt %d/%d",
                    step_idx,
                    target_idx,
                    gate.loop_target,
                    attempts[step_idx],
                    gate.max_retries,
                )
                # Reset target step to PENDING
                run.step_records[target_idx].status = StepStatus.PENDING
                run.step_records[target_idx].result = None
                run.current_step = target_idx
                return "loop_back"
            logger.warning(
                "Gate loop-back: target step '%s' not found in pipeline", gate.loop_target
            )
        # Loop back exhausted
        logger.warning(
            "Gate loop-back exhausted: step %d used %d/%d attempts",
            step_idx,
            attempts[step_idx],
            gate.max_retries,
        )
        run.fail_current_step(result)
        return "stop"
