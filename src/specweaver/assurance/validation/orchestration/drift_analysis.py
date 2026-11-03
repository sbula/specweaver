# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Asks the model why a file drifted from its plan."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.infrastructure.llm.budget import SpendLimitReachedError
from specweaver.infrastructure.llm.models import Message, Role

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


async def explain_drift(
    adapter: Any, config: Any, findings: Sequence[Any], file_path: str
) -> str | None:
    """The model's root cause for the drift findings; None when the spend brake stopped it."""
    prompt = (
        f"You are investigating architectural drift in {file_path}.\n"
        f"The AST Drift Engine found {len(findings)} violations:\n"
    )
    for f in findings:
        prompt += f"- {f.severity.name}: {' '.join(str(f.description).split())}\n"
    prompt += "\nExplain the root cause of these discrepancies concisely."

    messages = [
        Message(
            role=Role.SYSTEM, content="You are a code architecture expert diagnosing AST drift."
        ),
        Message(role=Role.USER, content=prompt),
    ]
    try:
        response = await adapter.generate(messages, config)
        return str(response.text)
    except SpendLimitReachedError:  # expected: the brake stopped the run, which reports it
        return None
    except Exception as exc:
        logger.exception("Drift root-cause analysis failed.")
        return f"LLM analysis failed: {exc}"
