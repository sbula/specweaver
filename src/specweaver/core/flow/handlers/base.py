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


class IsolationPolicy(BaseModel):
    """Whether and where this run executes inside a git worktree instead of the real repo.

    Resolved once at start-up and read by the engine's sandbox paths.

    **Frozen deliberately.** ``runner_utils`` isolates a step or a session with
    ``copy.copy(context)``, which is SHALLOW: the copy and the original then share this one
    instance. Setting a field on it would silently change the original run's isolation too.
    Frozen turns that mistake into an immediate error. To change anything here, build a new
    one and rebind the whole attribute::

        context.isolation = context.isolation.model_copy(update={...})

    Frozen stops the attribute being *replaced*, not the contents of a mutable value being
    edited — ``policy.allowed_paths.append(...)`` still works and would still leak across the
    shared copy. Nothing replaces that list piecemeal today; keep it that way.

    Attributes:
        enforce_isolation: Run each step in its own worktree.
        execution_root: Where untrusted processes bind cwd; None means the project root.
        session_isolation: Run the WHOLE run in one shared worktree instead of one per step.
        allowed_paths: The only paths the end-of-run merge is permitted to write back.
        dal_level: How strict the boundary rules are for the code being touched.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enforce_isolation: bool = False
    execution_root: Path | None = None
    session_isolation: bool = False
    allowed_paths: list[str] = Field(default_factory=list)
    dal_level: Any = None


class PlanContext(BaseModel):
    """The two plan documents a run produces, filled in by the runner as steps complete.

    These are two DIFFERENT things and must never be merged into one field. ``plan`` is the
    implementation plan — spec to file layout, written by the plan step. ``decomposition`` is
    the feature-to-components breakdown, as JSON, written by the decompose step. Code that
    wants one and reads the other will appear to work and be wrong.

    Frozen, so both are replaced together via ``model_copy``. A partial update must leave the
    other field alone: ``hydration.py`` clears exactly one of them when its own step fails,
    and clearing one must not wipe a plan the other step legitimately produced.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: str | None = None  # Implementation PlanArtifact content (set by runner hook)
    decomposition: str | None = None  # DecompositionPlan JSON (set by runner hook)


class ModelAccess(BaseModel):
    """How this run reaches a language model: the adapter, its settings, and the router.

    Everything is typed ``Any`` on purpose — importing the real types here would cross a module
    boundary this package is not allowed to cross.

    The attribute is called ``model`` on the context, which is safe: Pydantic reserves the
    ``model_`` prefix, not the bare word.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm: Any = None  # LLMAdapter | None
    config: Any = None  # SpecWeaverSettings | None — LLM config for adapters
    llm_router: Any = None  # ModelRouter | None — per-task routing (3.12b)


class RunHandle(BaseModel):
    """Who this run is: its id, the runner executing it, and the task it belongs to.

    The runner rewrites ``run_id`` on every step, so any partial update must preserve
    ``pipeline_runner`` — the fan-out in ``decompose.py`` and ``dual_pipeline.py`` reaches
    through it to spawn sub-pipelines, and dropping it breaks them with no obvious cause.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    pipeline_runner: Any = None  # PipelineRunner | None — for fan_out
    task_id: str | None = None  # Target Task ID for Handover Protocol


class AnalysisContext(BaseModel):
    """The code-analysis tools a run may use: a language-analyzer factory and AST parsers.

    ``parsers`` is filled in automatically when the caller does not supply it, and that load is
    best-effort — if it fails the field stays ``None`` rather than making the context
    impossible to build, because most steps never touch a parser.

    ``analyzer_factory`` is typed ``Any`` because its real type lives in a package this one is
    not permitted to import at runtime.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analyzer_factory: Any = None  # AnalyzerFactoryProtocol | None
    parsers: Any = None  # dict[tuple[str, ...], CodeStructureInterface] | None


class RunContext(BaseModel):
    """Everything a pipeline step needs, passed to every handler as one object.

    Related fields are grouped into small frozen sub-models rather than left loose here, so
    that adding a field means choosing which group it belongs to instead of making this class
    a little bigger every time.

    Attributes:
        project_path: Root directory of the target project.
        spec_path: The spec being processed.
        output_dir: Where generated code and tests are written.
        isolation: Whether and where this run is sandboxed in a worktree.
        plan_context: The implementation plan and the feature decomposition.
        model: The LLM adapter, its settings, and the per-task router.
        run: This run's id, its runner, and the task it belongs to.
        analysis: Analyzer factory and AST parsers, when a step needs them.
        context_provider: Asks a human for input, for interactive steps.
        topology: The project's dependency graph.
        settings: Per-project validation settings and overrides.
        feedback: Messages passed between steps, including loop-back findings.
        constitution: Pre-loaded project constitution text.
        standards: Pre-loaded coding standards text.
        db: Database handle, for telemetry and memory.
        project_metadata: Computed on construction; describes the project to prompts.

    Unknown keyword arguments are REJECTED, which is load-bearing rather than tidiness. The
    default Pydantic behaviour silently discards them, so a caller still passing a field that
    has since moved into one of the sub-models would build a context with that value quietly
    missing and no error anywhere. Rejecting them makes such a call fail at construction, the
    same way reading a moved field already fails at the attribute.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    project_path: Path
    spec_path: Path
    context_provider: Any = None  # ContextProvider | None
    topology: Any = None  # TopologyContext | None
    settings: Any = None  # ValidationSettings | None
    output_dir: Path | None = None
    isolation: IsolationPolicy = Field(default_factory=IsolationPolicy)
    plan_context: PlanContext = Field(default_factory=PlanContext)
    model: ModelAccess = Field(default_factory=ModelAccess)
    run: RunHandle = Field(default_factory=RunHandle)
    analysis: AnalysisContext = Field(default_factory=AnalysisContext)
    feedback: dict[str, Any] = Field(default_factory=dict)
    constitution: str | None = None  # Pre-loaded constitution content
    standards: str | None = None  # Pre-loaded project standards
    workspace_roots: list[str] | None = None  # Override boundary roots (set by decomposition)
    api_contract_paths: list[str] | None = None  # Neighboring API surfaces (read-only)
    db: Any = None  # Database | None — for telemetry flush (set by CLI/API)
    project_metadata: Any = None  # ProjectMetadata | None
    step_records: list[dict[str, Any]] | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    pipeline_name: str | None = None
    stale_nodes: set[str] | None = None

    def model_post_init(self, __context: Any) -> None:
        """Inject ProjectMetadata into context execution strictly securely."""
        if self.analysis.parsers is None:
            try:
                from specweaver.workspace.ast.parsers.factory import get_default_parsers

                self.analysis = self.analysis.model_copy(update={"parsers": get_default_parsers()})
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
        if (
            self.model.config
            and hasattr(self.model.config, "validation")
            and self.model.config.validation
        ):
            overrides = getattr(self.model.config.validation, "overrides", {})
            if isinstance(overrides, dict):
                rules = overrides

        try:
            provider = (
                str(self.model.llm.provider_name)
                if hasattr(self.model.llm, "provider_name")
                else "unknown"
            )
            model_str = str(self.model.llm.model) if hasattr(self.model.llm, "model") else "unknown"
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
