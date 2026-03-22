# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Handler base — RunContext, StepHandler protocol, and shared helpers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — Pydantic needs Path at runtime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.flow.models import PipelineStep
    from specweaver.validation.models import RuleResult  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RunContext — everything a handler needs
# ---------------------------------------------------------------------------


class RunContext(BaseModel):
    """Execution context passed to every step handler.

    Attributes:
        project_path: Root directory of the target project.
        spec_path: Path to the spec being processed.
        llm: LLM adapter (None for validate-only pipelines).
        context_provider: For HITL-interactive steps (draft).
        topology: Project graph topology context.
        settings: Per-project validation settings/overrides.
        output_dir: Output directory for generated code/tests.
        plan: Pre-loaded plan content (populated by runner post-step hook).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_path: Path
    spec_path: Path
    llm: Any = None  # LLMAdapter | None — Any to avoid import issues
    context_provider: Any = None  # ContextProvider | None
    topology: Any = None  # TopologyContext | None
    settings: Any = None  # ValidationSettings | None
    config: Any = None  # SpecWeaverSettings | None — LLM config for adapters
    output_dir: Path | None = None
    feedback: dict[str, Any] = Field(default_factory=dict)
    constitution: str | None = None  # Pre-loaded constitution content
    standards: str | None = None  # Pre-loaded project standards
    plan: str | None = None  # Pre-loaded plan content (set by runner hook)


# ---------------------------------------------------------------------------
# Handler protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StepHandler(Protocol):
    """Protocol for step execution handlers."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _error_result(message: str, started_at: str) -> StepResult:
    return StepResult(
        status=StepStatus.ERROR,
        error_message=message,
        started_at=started_at,
        completed_at=_now_iso(),
    )
