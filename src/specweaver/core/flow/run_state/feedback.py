# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What one step hands another through `RunContext.feedback`: each key, and its value's type.

A step's own name keys the findings sent to it (`StepFindings`); the other keys are fixed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, TypedDict

if TYPE_CHECKING:
    from specweaver.core.flow.run_state.run_context import RunContext

logger = logging.getLogger(__name__)

#: The QA runner's exports for the scenario tests (`dict[str, Any]`), read by the arbiter.
SCENARIO_EVIDENCE: Final = "scenario_test_failures"
#: The mentions the review step resolved (`list[ResolvedMention]`), kept for its next round.
RESOLVED_MENTIONS: Final = "mention_scanner:resolved"


class StepFindings(TypedDict):
    """Findings sent back to a step, keyed by that step's name."""

    from_step: str
    findings: dict[str, Any]


def send_findings(
    context: RunContext, to_step: str, from_step: str, findings: dict[str, Any]
) -> None:
    """Hand `findings` to `to_step`; a later send replaces an unread one."""
    context.feedback[to_step] = StepFindings(from_step=from_step, findings=findings)


def pop_findings(context: RunContext, step_name: str) -> dict[str, Any] | None:
    """The findings sent to `step_name`, taken out so a retry does not apply them again.

    None when there are none; a malformed entry is taken out too, logged, then treated as absent.
    """
    if not (hasattr(context, "feedback") and context.feedback):
        return None
    entry = context.feedback.pop(step_name, None)
    findings = entry.get("findings") if isinstance(entry, dict) else None
    if isinstance(findings, dict):
        return findings
    if entry is not None:
        logger.warning("feedback for step '%s' is malformed; it is dropped", step_name)
    return None
