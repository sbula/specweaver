# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Draft step handler — spec creation parking."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, _error_result, _now_iso

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep

logger = logging.getLogger(__name__)


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
            if context.context_provider is not None and context.llm is not None:
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
        if context.context_provider is not None and context.llm is not None:
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
        """Pop this step's loop_back feedback (reviewer findings) — consumed exactly once.

        Returns the findings dict, or None when feedback is absent or malformed (a
        malformed entry is still popped, then treated as absent — never crashes).
        """
        if hasattr(context, "feedback") and context.feedback:
            fb = context.feedback.pop(step.name, None)
            if isinstance(fb, dict):
                findings = fb.get("findings")
                if isinstance(findings, dict):
                    return findings
        return None

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
        if context.config and hasattr(context.config, "llm"):
            gen_config = GenerationConfig(
                model=context.config.llm.model,
                temperature=context.config.llm.temperature,
                max_output_tokens=context.config.llm.max_output_tokens,
                run_id=getattr(context, "run_id", "") or "",
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

            base_prompt.add_context(
                json.dumps(findings, ensure_ascii=False), "reviewer_findings"
            )

        drafter = Drafter(
            llm=context.llm,
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
                        run_id=getattr(context, "run_id", None) or "pipeline_run",
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
