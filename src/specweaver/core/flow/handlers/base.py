# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Handler base — RunContext, StepHandler protocol, and shared helpers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — Pydantic needs Path at runtime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from specweaver.core.flow.engine.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.assurance.validation.models import RuleResult  # noqa: F401
    from specweaver.core.flow.engine.models import PipelineStep

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
    workspace_roots: list[str] | None = None  # Override boundary roots (set by decomposition)
    api_contract_paths: list[str] | None = None  # Neighboring API surfaces (read-only)
    db: Any = None  # Database | None — for telemetry flush (set by CLI/API)
    llm_router: Any = None  # ModelRouter | None — per-task routing (3.12b)
    project_metadata: Any = None  # ProjectMetadata | None
    pipeline_runner: Any = None  # PipelineRunner | None — for fan_out
    run_id: str | None = None
    step_records: list[dict[str, Any]] | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    pipeline_name: str | None = None
    stale_nodes: set[str] | None = None

    def model_post_init(self, __context: Any) -> None:
        """Inject ProjectMetadata into context execution strictly securely."""
        if self.project_metadata is not None:
            return

        import platform
        import sys

        from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig

        try:
            target = f"Python {sys.version.split()[0]} on {platform.platform()}"
        except Exception:
            # Handoff Directive 3
            target = "Unknown Environment"

        try:
            # Handoff Directive 2 fix (load_context_yaml does not exist)
            import ruamel.yaml

            ctx_path = self.project_path / "context.yaml"
            if ctx_path.exists():
                with ctx_path.open("r", encoding="utf-8") as f:
                    data = ruamel.yaml.YAML(typ="safe").load(f)
                archetype = (
                    data.get("archetype", "generic") if isinstance(data, dict) else "generic"
                )
            else:
                archetype = "generic"
        except Exception:
            archetype = "generic"

        rules = {}
        if self.config and hasattr(self.config, "validation") and self.config.validation:
            overrides = getattr(self.config.validation, "overrides", {})
            if isinstance(overrides, dict):
                rules = overrides

        try:
            provider = (
                str(self.llm.provider_name) if hasattr(self.llm, "provider_name") else "unknown"
            )
            model_str = str(self.llm.model) if hasattr(self.llm, "model") else "unknown"
        except Exception:
            provider = "unknown"
            model_str = "unknown"

        safe_config = PromptSafeConfig(
            llm_provider=provider,
            llm_model=model_str,
            validation_rules=rules,
        )

        self.project_metadata = ProjectMetadata(
            project_name=self.project_path.name,
            archetype=archetype,
            language_target=target,
            date_iso=_now_iso(),
            safe_config=safe_config,
        )


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
