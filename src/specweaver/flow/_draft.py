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
            from specweaver.llm.lineage import extract_artifact_uuid
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

    async def _execute_drafting(
        self, step: PipelineStep, context: RunContext, started: str
    ) -> StepResult:
        """Execute the actual interactive Drafter."""
        from specweaver.drafting.drafter import Drafter
        from specweaver.llm.models import GenerationConfig

        gen_config = None
        if context.config and hasattr(context.config, "llm"):
            gen_config = GenerationConfig(
                model=context.config.llm.model,
                temperature=context.config.llm.temperature,
                max_output_tokens=context.config.llm.max_output_tokens,
                run_id=getattr(context, "run_id", "") or "",
            )

        drafter = Drafter(
            llm=context.llm,
            context_provider=context.context_provider,
            config=gen_config,
        )

        name = context.spec_path.stem.removesuffix("_spec")
        specs_dir = context.spec_path.parent

        topology_contexts = context.topology if isinstance(context.topology, list) else None

        try:
            result_path = await drafter.draft(name, specs_dir, topology_contexts=topology_contexts)

            import uuid

            from specweaver.llm.lineage import extract_artifact_uuid, wrap_artifact_tag

            artifact_uuid = None
            if result_path.exists():
                artifact_uuid = extract_artifact_uuid(result_path.read_text(encoding="utf-8"))
            if not artifact_uuid:
                artifact_uuid = str(uuid.uuid4())
                tag_str = wrap_artifact_tag(artifact_uuid, "markdown")
                if tag_str:
                    content = result_path.read_text(encoding="utf-8")
                    result_path.write_text(tag_str + "\n" + content, encoding="utf-8")

            if getattr(context, "db", None) and hasattr(context.db, "log_artifact_event"):
                context.db.log_artifact_event(
                    artifact_id=artifact_uuid,
                    parent_id=None,
                    run_id=getattr(context, "run_id", "") or "",
                    event_type="drafted_spec",
                )

            return StepResult(
                status=StepStatus.PASSED,
                output={"message": f"Spec drafted: {result_path}", "path": str(result_path)},
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            from specweaver.flow._base import _error_result

            return _error_result(f"Drafting failed: {exc}", started)
