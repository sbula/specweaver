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
    from specweaver.infrastructure.llm._prompt_profiles import RenderProfile
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

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
        analyzer_factory: Optional DI injected AnalyzerFactoryProtocol instance.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_path: Path
    spec_path: Path
    llm: Any = None  # LLMAdapter | None — Any to avoid import issues
    context_provider: Any = None  # ContextProvider | None
    topology: Any = None  # TopologyContext | None
    settings: Any = None  # ValidationSettings | None
    config: Any = None  # SpecWeaverSettings | None — LLM config for adapters
    analyzer_factory: Any = None  # AnalyzerFactoryProtocol | None
    output_dir: Path | None = None
    enforce_isolation: bool = False  # INT-US-09: US-9 per-step worktree-isolation policy (composition root)
    execution_root: Path | None = None  # INT-US-09: where untrusted processes bind cwd (worktree); None -> project_path
    session_isolation: bool = False  # C-EXEC-06: per-run (session) worktree isolation — the whole run in ONE worktree
    allowed_paths: list[str] = Field(default_factory=list)  # C-EXEC-06: repo-relative paths the reconcile may write back
    feedback: dict[str, Any] = Field(default_factory=dict)
    constitution: str | None = None  # Pre-loaded constitution content
    standards: str | None = None  # Pre-loaded project standards
    plan: str | None = None  # Pre-loaded plan content (set by runner hook)
    workspace_roots: list[str] | None = None  # Override boundary roots (set by decomposition)
    api_contract_paths: list[str] | None = None  # Neighboring API surfaces (read-only)
    task_id: str | None = None  # Target Task ID for Handover Protocol
    db: Any = None  # Database | None — for telemetry flush (set by CLI/API)
    llm_router: Any = None  # ModelRouter | None — per-task routing (3.12b)
    project_metadata: Any = None  # ProjectMetadata | None
    pipeline_runner: Any = None  # PipelineRunner | None — for fan_out
    run_id: str | None = None
    step_records: list[dict[str, Any]] | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    pipeline_name: str | None = None
    dal_level: Any = None  # DALLevel | None — Enforced boundary strictness
    stale_nodes: set[str] | None = None
    parsers: Any = None  # dict[tuple[str, ...], CodeStructureInterface] | None

    def model_post_init(self, __context: Any) -> None:
        """Inject ProjectMetadata into context execution strictly securely."""
        if self.parsers is None:
            try:
                from specweaver.workspace.ast.parsers.factory import get_default_parsers

                self.parsers = get_default_parsers()
            except BaseException:
                pass

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


async def _build_base_prompt(
    context: RunContext,
    instructions: str,
    *,
    profile: RenderProfile | None = None,
    skeleton_files: dict[str, str] | None = None,
) -> PromptBuilder:
    """Build a PromptBuilder with base context (instructions, metadata, rules, memory).

    Args:
        context: The RunContext for this pipeline step.
        instructions: Module-specific instruction text.
        profile: The RenderProfile to use for rendering slots. Defaults to FULL.
        skeleton_files: Optional skeleton files for PromptBuilder constructor.

    Returns:
        A partially-built PromptBuilder ready for domain-specific additions.

    The memory hydration is fail-safe: any exception during hydration (db=None,
    DB failure, Pydantic error) is caught and logged at WARNING. The returned
    PromptBuilder simply lacks the agent_memory block.
    """
    from specweaver.core.flow.handlers._profiles import FULL
    from specweaver.infrastructure.llm._prompt_profiles import PromptSlot
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

    if profile is None:
        profile = FULL

    builder = PromptBuilder(profile=profile, skeleton_files=skeleton_files)
    builder.add_instructions(instructions)
    builder.add_project_metadata(context.project_metadata)

    if context.constitution:
        builder.add_constitution(context.constitution)
    if context.standards:
        builder.add_standards(context.standards)

    # Memory Hydration — fail-safe
    if (
        PromptSlot.AGENT_MEMORY in profile.active_slots
        and context.db is not None
        and context.project_path is not None
    ):
        try:
            from specweaver.workspace.memory.hydrator import MemoryHydrator

            async with context.db.async_session_scope() as session:
                hydrator = MemoryHydrator(session, context.project_path.name)
                result = await hydrator.hydrate()
                if result.task_count > 0:
                    block = result.format_prompt_block()
                    builder.add_context(
                        block, "agent_memory", priority=2, slot=PromptSlot.AGENT_MEMORY
                    )
                    logger.info(
                        "Hydration: %d tasks, %d tokens",
                        result.task_count,
                        result.token_estimate,
                    )
        except Exception:
            logger.warning(
                "Memory hydration failed — continuing without agent_memory",
                exc_info=True,
            )

    return builder
