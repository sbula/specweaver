# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Handler base — RunContext, StepHandler protocol, and shared helpers."""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003 — Pydantic needs Path at runtime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

# Re-exports, NOT definitions. `TECH-015` moved these out; ~30 files import them from here and
# the split is meant to be mechanical, so the old names keep resolving. New code should import
# from the module that owns them. `_now_iso` was one of SIX identical definitions of
# `datetime.now(UTC).isoformat()` in this repo — this one delegates to the L0 commons leaf
# rather than being a seventh place to change.
from specweaver.commons.timestamps import now_iso as _now_iso
from specweaver.core.flow.handlers.prompting import _build_base_prompt
from specweaver.core.flow.handlers.results import _error_result

if TYPE_CHECKING:
    from specweaver.assurance.validation.models import RuleResult  # noqa: F401
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.engine.state import StepResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RunContext — everything a handler needs
# ---------------------------------------------------------------------------


class IsolationPolicy(BaseModel):
    """Whether and where this run executes in a git worktree instead of the real repo.

    Frozen because the engine isolates a step with ``copy.copy(context)``, leaving copy and
    original sharing this instance — setting a field here would change both. Replace the whole
    attribute instead. (A mutable field's *contents* can still be edited, so don't.)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enforce_isolation: bool = False
    execution_root: Path | None = None
    session_isolation: bool = False
    allowed_paths: list[str] = Field(default_factory=list)
    dal_level: Any = None


class PlanContext(BaseModel):
    """The two plan documents a run produces, filled in by the runner as steps complete.

    Two DIFFERENT things, never to be merged: ``plan`` is the implementation plan (spec to file
    layout); ``decomposition`` is the feature-to-components breakdown. Code that wants one and
    reads the other looks like it works and is wrong.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: str | None = None  # Implementation PlanArtifact content (set by hydrate_plan_context)
    decomposition: str | None = None  # DecompositionPlan JSON (set by hydrate_plan_context)


class ModelAccess(BaseModel):
    """How this run reaches a language model: adapter, settings, router.

    All ``Any``: importing the real types would cross a module boundary this package may not.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm: Any = None  # LLMAdapter | None
    config: Any = None  # SpecWeaverSettings | None — LLM config for adapters
    llm_router: Any = None  # ModelRouter | None — per-task routing (3.12b)


class RunHandle(BaseModel):
    """Who this run is, plus the results of the steps already done.

    ``step_records`` is how a step reads an earlier step's output. The runner rewrites it and
    ``run_id`` every step, so a partial update must keep ``pipeline_runner`` — the fan-out
    reaches through it to spawn sub-pipelines.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str | None = None
    pipeline_runner: Any = None  # PipelineRunner | None — for fan_out
    task_id: str | None = None  # Target Task ID for Handover Protocol
    step_records: list[dict[str, Any]] | None = None


class AnalysisContext(BaseModel):
    """Code-analysis tools a run may use: an analyzer factory and AST parsers.

    ``parsers`` is loaded automatically if not supplied, best-effort — most steps never touch
    one, so a failure leaves it ``None`` rather than making the context unbuildable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analyzer_factory: Any = None  # AnalyzerFactoryProtocol | None
    parsers: Any = None  # dict[tuple[str, ...], CodeStructureInterface] | None


class GraphContext(BaseModel):
    """What this run knows about the project's dependency graph.

    ``stale_nodes`` and ``workspace_roots`` are read by code but written by nothing, so they are
    always ``None`` in production — a half-built feature, not dead code.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    topology: Any = None
    stale_nodes: set[str] | None = None
    workspace_roots: list[str] | None = None
    api_contract_paths: list[str] | None = None


class GuidanceContent(BaseModel):
    """The project's constitution and coding standards, pasted into prompts as-is.

    Together because every place that builds a context sets both; nothing sets one alone.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    constitution: str | None = None
    standards: str | None = None


class RunContext(BaseModel):
    """Everything a pipeline step needs, passed to every handler as one object.

    Related fields live in small frozen sub-models, so a new field has to join a group rather
    than making this class bigger. Unknown keyword arguments are rejected: the default would
    discard a since-moved field silently, leaving the value missing with no error anywhere.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    project_path: Path
    spec_path: Path
    context_provider: Any = None  # ContextProvider | None
    settings: Any = None  # ValidationSettings | None
    output_dir: Path | None = None
    isolation: IsolationPolicy = Field(default_factory=IsolationPolicy)
    plan_context: PlanContext = Field(default_factory=PlanContext)
    model: ModelAccess = Field(default_factory=ModelAccess)
    run: RunHandle = Field(default_factory=RunHandle)
    analysis: AnalysisContext = Field(default_factory=AnalysisContext)
    graph: GraphContext = Field(default_factory=GraphContext)
    guidance: GuidanceContent = Field(default_factory=GuidanceContent)
    feedback: dict[str, Any] = Field(default_factory=dict)
    db: Any = None  # Database | None — for telemetry flush (set by CLI/API)
    project_metadata: Any = None  # ProjectMetadata | None

    def model_post_init(self, __context: Any) -> None:
        """Fill in the two things a caller is not expected to supply by hand."""
        if self.analysis.parsers is None:
            self.analysis = self.analysis.model_copy(update={"parsers": self._default_parsers()})

        if self.project_metadata is None:
            self.project_metadata = self._build_project_metadata()

    @staticmethod
    def _default_parsers() -> Any:
        """Load the AST parsers, or return None if they cannot be loaded.

        Deliberately swallows everything, including BaseException: most steps never touch a
        parser, so a broken or missing parser package must not make every context in the
        process impossible to build.
        """
        try:
            from specweaver.workspace.ast.parsers.factory import get_default_parsers

            return get_default_parsers()
        except BaseException:
            return None

    def _build_project_metadata(self) -> Any:
        """Describe the project to prompts: its name, archetype, language and LLM in use.

        Every lookup here falls back rather than raising. This runs during construction of a
        context that most steps then never read metadata from, so an unreadable `context.yaml`
        or an odd platform must degrade to a sensible default instead of failing the run.
        """
        import platform
        import sys

        from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig

        try:
            target = f"Python {sys.version.split()[0]} on {platform.platform()}"
        except Exception:
            target = "Unknown Environment"

        archetype = self._read_archetype()

        rules = {}
        config = self.model.config
        if config and getattr(config, "validation", None):
            overrides = getattr(config.validation, "overrides", {})
            if isinstance(overrides, dict):
                rules = overrides

        try:
            llm = self.model.llm
            provider = str(llm.provider_name) if hasattr(llm, "provider_name") else "unknown"
            model_str = str(llm.model) if hasattr(llm, "model") else "unknown"
        except Exception:
            provider = "unknown"
            model_str = "unknown"

        return ProjectMetadata(
            project_name=self.project_path.name,
            archetype=archetype,
            language_target=target,
            date_iso=_now_iso(),
            safe_config=PromptSafeConfig(
                llm_provider=provider, llm_model=model_str, validation_rules=rules
            ),
        )

    def _read_archetype(self) -> str:
        """The project's archetype from its `context.yaml`, or "generic" if unavailable."""
        try:
            import ruamel.yaml

            ctx_path = self.project_path / "context.yaml"
            if not ctx_path.exists():
                return "generic"
            with ctx_path.open("r", encoding="utf-8") as f:
                data = ruamel.yaml.YAML(typ="safe").load(f)
            return data.get("archetype", "generic") if isinstance(data, dict) else "generic"
        except Exception:
            return "generic"


# ---------------------------------------------------------------------------
# Handler protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StepHandler(Protocol):
    """Protocol for step execution handlers."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult: ...


__all__ = [
    "AnalysisContext",
    "GraphContext",
    "GuidanceContent",
    "IsolationPolicy",
    "ModelAccess",
    "PlanContext",
    "RunContext",
    "RunHandle",
    "StepHandler",
    "_build_base_prompt",
    "_error_result",
    "_now_iso",
]
