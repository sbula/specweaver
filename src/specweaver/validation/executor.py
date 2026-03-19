# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Validation sub-pipeline executor.

Runs a ValidationPipeline: iterates steps in order, looks up each rule
from the registry, instantiates with step.params, and collects results.

Does NOT use the orchestration PipelineRunner -- this is a simpler,
synchronous executor internal to validation handlers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.validation.models import RuleResult, Status

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.validation.pipeline import ValidationPipeline
    from specweaver.validation.registry import RuleRegistry

logger = logging.getLogger(__name__)


def execute_validation_pipeline(
    pipeline: ValidationPipeline,
    spec_text: str,
    spec_path: Path | None = None,
    *,
    registry: RuleRegistry | None = None,
) -> list[RuleResult]:
    """Execute a validation pipeline against spec/code content.

    For each step:
    1. Look up rule class from registry via step.rule
    2. Instantiate with step.params as constructor kwargs
    3. Call rule.check(spec_text, spec_path)
    4. Wrap in try/except (broken rule = FAIL result, logged, continue)

    Args:
        pipeline: Resolved validation pipeline (no inheritance markers).
        spec_text: Full text content to validate.
        spec_path: Optional path to the spec/code file.
        registry: Rule registry to look up rules. Uses global if not provided.

    Returns:
        List of RuleResult, one per step, in pipeline order.
    """
    if registry is None:
        from specweaver.validation.registry import get_registry
        registry = get_registry()

    results: list[RuleResult] = []
    logger.debug(
        "execute_validation_pipeline: running '%s' (%d steps)",
        pipeline.name, len(pipeline.steps),
    )

    for step in pipeline.steps:
        rule_cls = registry.get(step.rule)

        if rule_cls is None:
            logger.warning(
                "execute_validation_pipeline: unknown rule '%s' in step '%s', skipping",
                step.rule, step.name,
            )
            results.append(RuleResult(
                rule_id=step.rule,
                rule_name=step.name,
                status=Status.FAIL,
                message=f"Unknown rule '{step.rule}': not found in registry",
            ))
            continue

        try:
            rule = rule_cls(**step.params)
        except Exception as exc:
            logger.exception(
                "execute_validation_pipeline: failed to instantiate rule '%s' with params %s",
                step.rule, step.params,
            )
            results.append(RuleResult(
                rule_id=step.rule,
                rule_name=step.name,
                status=Status.FAIL,
                message=f"Failed to instantiate rule '{step.rule}': {exc}",
            ))
            continue

        try:
            result = rule.check(spec_text, spec_path)
        except Exception as exc:
            logger.exception(
                "execute_validation_pipeline: rule '%s' (%s) crashed",
                rule.rule_id, rule.name,
            )
            result = RuleResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                status=Status.FAIL,
                message=f"Rule crashed: {type(exc).__name__}: {exc}",
            )

        results.append(result)

    failed = sum(1 for r in results if r.status == Status.FAIL)
    logger.info(
        "execute_validation_pipeline: '%s' — %d rules, %d passed, %d failed",
        pipeline.name, len(results), len(results) - failed, failed,
    )
    return results


def apply_settings_to_pipeline(
    pipeline: ValidationPipeline,
    settings: object | None,
) -> ValidationPipeline:
    """Apply ValidationSettings overrides onto a pipeline.

    Bridges the old settings system (thresholds, enabled/disabled) with
    the validation sub-pipeline architecture.

    - Disabled rules: their steps are removed from the pipeline.
    - Threshold overrides: merged into step.params.

    Args:
        pipeline: A resolved ValidationPipeline.
        settings: A ValidationSettings instance or None.

    Returns:
        A new ValidationPipeline with settings applied.
    """
    if settings is None:
        return pipeline

    from specweaver.validation.pipeline import ValidationPipeline as _Pipeline
    from specweaver.validation.pipeline import ValidationStep
    from specweaver.validation.runner import _build_rule_kwargs

    new_steps: list[ValidationStep] = []
    for step in pipeline.steps:
        # Check if rule is disabled
        if not settings.is_enabled(step.rule):
            logger.debug(
                "apply_settings_to_pipeline: rule '%s' disabled by settings, removing",
                step.rule,
            )
            continue

        # Merge threshold/extra_params overrides into step.params
        kwargs = _build_rule_kwargs(step.rule, settings)
        if kwargs:
            merged = {**step.params, **kwargs}
            step = ValidationStep(
                name=step.name,
                rule=step.rule,
                params=merged,
                path=step.path,
            )

        new_steps.append(step)

    return _Pipeline(
        name=pipeline.name,
        description=pipeline.description,
        version=pipeline.version,
        steps=new_steps,
    )
