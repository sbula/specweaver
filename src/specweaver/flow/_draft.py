# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Draft step handler — spec creation parking."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.flow._base import RunContext, _now_iso
from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.flow.models import PipelineStep

logger = logging.getLogger(__name__)


class DraftSpecHandler:
    """Handler for draft+spec — parks if spec doesn't exist yet."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()

        # If spec already exists, consider the draft step pre-completed
        if context.spec_path.exists():
            logger.debug(
                "DraftSpecHandler: spec already exists at '%s' — skipping", context.spec_path
            )
            return StepResult(
                status=StepStatus.PASSED,
                output={"message": f"Spec already exists: {context.spec_path}"},
                started_at=started,
                completed_at=_now_iso(),
            )

        # Spec doesn't exist — park and tell the user
        logger.info(
            "DraftSpecHandler: spec not found at '%s' — parking for user input", context.spec_path
        )
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={
                "message": (
                    f"Spec file not found: {context.spec_path}. "
                    "Please create it using 'sw draft' and then resume with 'sw run --resume'."
                ),
            },
            started_at=started,
            completed_at=_now_iso(),
        )
