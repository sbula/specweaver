# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Standards enrichment step handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.flow._base import RunContext, _error_result, _now_iso
from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.flow.models import PipelineStep

logger = logging.getLogger(__name__)


class EnrichStandardsHandler:
    """Handler for enrich+standards."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()

        scope_files = step.params.get("scope_files", [])
        half_life_days = float(step.params.get("half_life_days", 90.0))
        compare = bool(step.params.get("compare", False))

        from specweaver.standards.enricher import StandardsEnricher
        from specweaver.standards.scanner import StandardsScanner

        scanner = StandardsScanner()
        raw_results = scanner.scan(scope_files, half_life_days)
        results = [r for r in raw_results if r.confidence >= 0.3]

        if not results:
            return StepResult(
                status=StepStatus.PASSED,
                output={"results": []},
                started_at=started,
                completed_at=_now_iso(),
            )

        if not context.llm:
            return _error_result("No LLM adapter provided for standards enrichment", started)

        from specweaver.llm.models import GenerationConfig

        gen_config = None
        if context.config and hasattr(context.config, "llm"):
            gen_config = GenerationConfig(
                model=context.config.llm.model,
                temperature=context.config.llm.temperature,
                max_output_tokens=context.config.llm.max_output_tokens,
            )

        enricher = StandardsEnricher(context.llm, config=gen_config)

        try:
            await enricher.enrich(results, language="auto", force_compare=compare)
        except Exception as exc:
            return _error_result(f"Standards enrichment failed: {exc}", started)

        return StepResult(
            status=StepStatus.PASSED,
            output={"results": results},
            started_at=started,
            completed_at=_now_iso(),
        )
