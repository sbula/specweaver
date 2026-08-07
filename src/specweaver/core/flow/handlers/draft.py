# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Draft step handlers — spec and feature-spec creation parking."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, _error_result, _now_iso

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep

logger = logging.getLogger(__name__)

#: Filename suffix the feature-spec convention requires. ``FeatureDrafter`` derives its own
#: output path as ``<output_dir>/<name>_feature_spec.md``, so this is the only shape that can
#: round-trip back to ``context.spec_path`` (INT-US-21 FR-1).
FEATURE_SPEC_SUFFIX = "_feature_spec.md"


def _pop_step_feedback(step: PipelineStep, context: RunContext) -> dict[str, Any] | None:
    """Pop this step's loop_back feedback (reviewer findings) — consumed exactly once.

    Returns the findings dict, or None when feedback is absent or malformed (a
    malformed entry is still popped, then treated as absent — never crashes).

    Shared by both draft handlers so the pop-once contract has one implementation.
    """
    if hasattr(context, "feedback") and context.feedback:
        fb = context.feedback.pop(step.name, None)
        if isinstance(fb, dict):
            findings = fb.get("findings")
            if isinstance(findings, dict):
                return findings
    return None


class DraftSpecHandler:
    """Handler for draft+spec — parks if spec doesn't exist yet."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()

        # INT-US-02 SF-01 (AD-6a): consume loop_back reviewer feedback FIRST. Without this,
        # the exists-skip below fires on re-entry and the review rejection loop is dead
        # (validate→review→fail→skip→…). Mirrors generation.py's _extract_prompt_feedback:
        # popped exactly once so it never sticks across attempts.
        findings = self._pop_feedback(step, context)
        if findings is not None:
            if context.context_provider is not None and context.model.llm is not None:
                logger.info(
                    "DraftSpecHandler: reviewer feedback received — re-drafting '%s'",
                    context.spec_path,
                )
                return await self._execute_drafting(step, context, started, findings=findings)
            # Headless rejection: park, carrying the findings so the resuming human sees them.
            logger.info(
                "DraftSpecHandler: reviewer feedback received but no interactive provider — "
                "parking '%s' for user input",
                context.spec_path,
            )
            return StepResult(
                status=StepStatus.WAITING_FOR_INPUT,
                output={
                    "message": (
                        f"Spec review rejected: {context.spec_path}. Revise it (interactively "
                        "via 'sw draft' in a terminal, or by editing the file) and resume "
                        "with 'sw run --resume'."
                    ),
                    "reviewer_findings": findings,
                },
                started_at=started,
                completed_at=_now_iso(),
            )

        # If spec already exists, consider the draft step pre-completed
        if context.spec_path.exists():
            logger.debug(
                "DraftSpecHandler: spec already exists at '%s' — skipping", context.spec_path
            )
            from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

            artifact_uuid = extract_artifact_uuid(context.spec_path.read_text(encoding="utf-8"))
            return StepResult(
                status=StepStatus.PASSED,
                output={"message": f"Spec already exists: {context.spec_path}"},
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )

        # Spec doesn't exist. If we have a context provider (HITL), do the drafting.
        if context.context_provider is not None and context.model.llm is not None:
            return await self._execute_drafting(step, context, started)

        # Otherwise (e.g. headless autonomous run without provider), park and tell the user
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

    @staticmethod
    def _pop_feedback(step: PipelineStep, context: RunContext) -> dict[str, Any] | None:
        """Delegate to the shared helper (kept for callers that reference it directly)."""
        return _pop_step_feedback(step, context)

    async def _execute_drafting(
        self,
        step: PipelineStep,
        context: RunContext,
        started: str,
        *,
        findings: dict[str, Any] | None = None,
    ) -> StepResult:
        """Execute the actual interactive Drafter."""
        from specweaver.core.flow.handlers.base import _build_base_prompt
        from specweaver.infrastructure.llm.models import GenerationConfig
        from specweaver.workflows.drafting.drafter import Drafter

        gen_config = None
        if context.model.config and hasattr(context.model.config, "llm"):
            gen_config = GenerationConfig(
                model=context.model.config.llm.model,
                temperature=context.model.config.llm.temperature,
                max_output_tokens=context.model.config.llm.max_output_tokens,
                run_id=context.run.run_id or "",
            )

        from specweaver.core.flow.handlers._profiles import INTERACTIVE, resolve_profile

        try:
            profile = resolve_profile(step.params.get("render_profile"), default=INTERACTIVE)
        except ValueError as e:
            return _error_result(str(e), started)

        base_prompt = await _build_base_prompt(
            context=context,
            instructions="",
            profile=profile,
        )

        # INT-US-02 SF-01 (AD-6a): surface reviewer findings to the re-draft. Deliberately
        # minimal (one JSON context block) — the drafting engine is a D-INTL-07 supersession
        # target; do not invest in prompt shaping here.
        if findings is not None:
            import json

            base_prompt.add_context(json.dumps(findings, ensure_ascii=False), "reviewer_findings")

        drafter = Drafter(
            llm=context.model.llm,
            context_provider=context.context_provider,
            config=gen_config,
            base_prompt=base_prompt,
        )

        name = context.spec_path.stem.removesuffix("_spec")
        specs_dir = context.spec_path.parent

        topology_contexts = context.topology if isinstance(context.topology, list) else None

        try:
            result_path = await drafter.draft(name, specs_dir, topology_contexts=topology_contexts)

            import uuid

            from specweaver.infrastructure.llm.lineage import (
                extract_artifact_uuid,
                wrap_artifact_tag,
            )

            artifact_uuid = None
            if result_path.exists():
                artifact_uuid = extract_artifact_uuid(result_path.read_text(encoding="utf-8"))
            if not artifact_uuid:
                artifact_uuid = str(uuid.uuid4())
                tag_str = wrap_artifact_tag(artifact_uuid, "markdown")
                if tag_str:
                    content = result_path.read_text(encoding="utf-8")
                    result_path.write_text(tag_str + "\n" + content, encoding="utf-8")

            from specweaver.core.flow.store import FlowRepository

            if context.db:
                async with context.db.async_session_scope() as session:
                    repo = FlowRepository(session)
                    await repo.log_artifact_event(
                        artifact_id=artifact_uuid,
                        parent_id=None,
                        run_id=context.run.run_id or "pipeline_run",
                        event_type="drafted_spec",
                        model_id=gen_config.model if gen_config else "unknown",
                    )

            return StepResult(
                status=StepStatus.PASSED,
                output={"message": f"Spec drafted: {result_path}", "path": str(result_path)},
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            return _error_result(f"Drafting failed: {exc}", started)


class DraftFeatureHandler:
    """Handler for draft+feature — wraps ``FeatureDrafter`` with ``DraftSpecHandler`` parity.

    INT-US-21 FR-1. ``FeatureDrafter.draft()`` derives its own output path as
    ``<output_dir>/<name>_feature_spec.md`` while every downstream step reads
    ``context.spec_path``. The feature name is therefore derived so the drafter's output IS
    ``context.spec_path`` by construction, and the returned path is asserted against it.
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()

        # Consume loop_back reviewer feedback FIRST — before the exists-skip below, or the
        # review rejection loop is dead (same contract as DraftSpecHandler).
        findings = _pop_step_feedback(step, context)

        # An unusable spec path is fatal regardless of feedback, and must cost zero LLM calls.
        name = self._derive_feature_name(context.spec_path)
        if name is None:
            return _error_result(
                f"Feature spec path must be named '<feature>{FEATURE_SPEC_SUFFIX}' with a "
                f"non-empty feature name, got: {context.spec_path.name}",
                started,
            )

        if findings is not None:
            if context.context_provider is not None and context.model.llm is not None:
                logger.info(
                    "DraftFeatureHandler: reviewer feedback received — re-drafting '%s'",
                    context.spec_path,
                )
                return await self._execute_drafting(step, context, started, name, findings=findings)
            logger.info(
                "DraftFeatureHandler: reviewer feedback received but no interactive provider — "
                "parking '%s' for user input",
                context.spec_path,
            )
            return StepResult(
                status=StepStatus.WAITING_FOR_INPUT,
                output={
                    "message": (
                        f"Feature spec review rejected: {context.spec_path}. Revise it and "
                        "resume with 'sw resume'."
                    ),
                    "reviewer_findings": findings,
                },
                started_at=started,
                completed_at=_now_iso(),
            )

        # A directory (or any non-file) at the spec path would otherwise be read_text()'d on
        # the skip path or silently drafted over — fail loudly instead.
        if context.spec_path.exists() and not context.spec_path.is_file():
            return _error_result(
                f"Feature spec path exists but is not a file: {context.spec_path}",
                started,
            )

        if context.spec_path.is_file():
            logger.debug(
                "DraftFeatureHandler: feature spec already exists at '%s' — skipping",
                context.spec_path,
            )
            from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

            artifact_uuid = extract_artifact_uuid(context.spec_path.read_text(encoding="utf-8"))
            return StepResult(
                status=StepStatus.PASSED,
                output={"message": f"Feature spec already exists: {context.spec_path}"},
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )

        if context.context_provider is not None and context.model.llm is not None:
            return await self._execute_drafting(step, context, started, name)

        logger.info(
            "DraftFeatureHandler: feature spec not found at '%s' — parking for user input",
            context.spec_path,
        )
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={
                "message": (
                    f"Feature spec file not found: {context.spec_path}. "
                    "Create it (interactively in a terminal, or by editing the file) and "
                    "resume with 'sw resume'."
                ),
            },
            started_at=started,
            completed_at=_now_iso(),
        )

    @staticmethod
    def _derive_feature_name(spec_path: Path) -> str | None:
        """Derive the drafter's ``name`` so its output round-trips to ``spec_path``.

        Returns None when the path cannot round-trip. ``str.removesuffix`` is deliberately
        NOT used: it is a silent no-op when the suffix is absent, which would yield a name
        that writes to a different file than the one every downstream step reads.
        """
        filename = spec_path.name
        if not filename.endswith(FEATURE_SPEC_SUFFIX):
            return None
        name = filename[: -len(FEATURE_SPEC_SUFFIX)]
        return name or None

    async def _execute_drafting(
        self,
        step: PipelineStep,
        context: RunContext,
        started: str,
        name: str,
        *,
        findings: dict[str, Any] | None = None,
    ) -> StepResult:
        """Run the interactive FeatureDrafter and reconcile its output path."""
        from specweaver.core.flow.handlers._profiles import INTERACTIVE, resolve_profile
        from specweaver.core.flow.handlers.base import _build_base_prompt
        from specweaver.infrastructure.llm.models import GenerationConfig
        from specweaver.workflows.drafting.feature_drafter import FeatureDrafter

        try:
            profile = resolve_profile(step.params.get("render_profile"), default=INTERACTIVE)
        except ValueError as e:
            return _error_result(str(e), started)

        gen_config = None
        if context.model.config and hasattr(context.model.config, "llm"):
            gen_config = GenerationConfig(
                model=context.model.config.llm.model,
                temperature=context.model.config.llm.temperature,
                max_output_tokens=context.model.config.llm.max_output_tokens,
                run_id=context.run.run_id or "",
            )

        base_prompt = await _build_base_prompt(
            context=context,
            instructions="",
            profile=profile,
        )

        if findings is not None:
            import json

            base_prompt.add_context(json.dumps(findings, ensure_ascii=False), "reviewer_findings")

        # Keyword args only: FeatureDrafter's positional order differs from Drafter's.
        drafter = FeatureDrafter(
            base_prompt=base_prompt,
            llm=context.model.llm,
            context_provider=context.context_provider,
            config=gen_config,
        )

        topology_contexts = context.topology if isinstance(context.topology, list) else None

        try:
            result_path = await drafter.draft(
                name,
                context.spec_path.parent,
                topology_contexts=topology_contexts,
                project_metadata=context.project_metadata,
            )

            # The contract that makes FR-1 structural: what the drafter wrote must be the file
            # validate+decompose will read. If FeatureDrafter's naming ever drifts, fail loudly
            # rather than leaving an orphaned spec nobody downstream opens.
            if result_path != context.spec_path:
                return _error_result(
                    f"FeatureDrafter wrote '{result_path}' but the pipeline expects "
                    f"'{context.spec_path}' — feature spec naming contract broken",
                    started,
                )

            # Right path, but nothing on disk: every guard below is existence-checked, so this
            # would otherwise return PASSED for a spec that isn't there and surface as a
            # "spec file not found" error two steps later, in a different handler.
            if not result_path.exists():
                return _error_result(
                    f"FeatureDrafter reported success but no file exists at '{result_path}'",
                    started,
                )

            artifact_uuid = self._ensure_artifact_tag(result_path)
            await self._log_lineage(context, artifact_uuid, gen_config)

            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "message": f"Feature spec drafted: {result_path}",
                    "path": str(result_path),
                },
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            return _error_result(f"Feature drafting failed: {exc}", started)

    @staticmethod
    def _ensure_artifact_tag(result_path: Path) -> str:
        """Return the spec's lineage UUID, injecting a tag when it has none yet."""
        import uuid

        from specweaver.infrastructure.llm.lineage import (
            extract_artifact_uuid,
            wrap_artifact_tag,
        )

        content = result_path.read_text(encoding="utf-8")
        existing = extract_artifact_uuid(content)
        if existing:
            return existing

        artifact_uuid = str(uuid.uuid4())
        tag_str = wrap_artifact_tag(artifact_uuid, "markdown")
        if tag_str:
            result_path.write_text(tag_str + "\n" + content, encoding="utf-8")
        return artifact_uuid

    @staticmethod
    async def _log_lineage(context: RunContext, artifact_uuid: str, gen_config: Any) -> None:
        """Record the drafted-feature-spec lineage event when a telemetry DB is configured."""
        if not context.db:
            return

        from specweaver.core.flow.store import FlowRepository

        async with context.db.async_session_scope() as session:
            repo = FlowRepository(session)
            await repo.log_artifact_event(
                artifact_id=artifact_uuid,
                parent_id=None,
                run_id=context.run.run_id or "pipeline_run",
                event_type="drafted_feature_spec",
                model_id=gen_config.model if gen_config else "unknown",
            )
