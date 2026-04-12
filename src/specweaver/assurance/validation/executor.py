# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation sub-pipeline executor.

Runs a ValidationPipeline: iterates steps in order, looks up each rule
from the registry, instantiates with step.params, and collects results.

Does NOT use the orchestration PipelineRunner -- this is a simpler,
synchronous executor internal to validation handlers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.assurance.validation.models import RuleResult, Status

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.settings import ValidationSettings
    from specweaver.assurance.validation.pipeline import ValidationPipeline
    from specweaver.assurance.validation.registry import RuleRegistry

logger = logging.getLogger(__name__)


def _get_rule_id_from_cls(rule_cls: type) -> str | None:
    """Cheaply resolve the rule_id from a rule class (no-arg instantiation)."""
    try:
        result = rule_cls().rule_id
        return str(result) if result is not None else None
    except Exception:
        return None


def _apply_extra_params(
    param_map: dict[str, str],
    extra_params: dict[str, float],
    kwargs: dict[str, float],
) -> None:
    """Populate kwargs from extra_params using ``extra:<key>`` PARAM_MAP entries."""
    for map_key, constructor_arg in param_map.items():
        if map_key.startswith("extra:"):
            extra_key = map_key.removeprefix("extra:")
            if extra_key in extra_params:
                kwargs[constructor_arg] = extra_params[extra_key]


def _build_rule_kwargs(
    rule_cls: type,
    settings: ValidationSettings | None,
) -> dict[str, float]:
    """Build constructor kwargs for a rule using its PARAM_MAP.

    Reads the rule's ``PARAM_MAP`` class attribute to translate DB-style
    field names (``warn_threshold``, ``fail_threshold``, ``extra:<key>``)
    into the actual constructor parameter names accepted by the rule class.

    Each rule self-declares its configurable parameters via ``PARAM_MAP``
    (defined in the ``Rule`` ABC, overridden per subclass).  Rules with no
    configurable thresholds leave ``PARAM_MAP = {}`` — this function returns
    ``{}`` for them without crashing.

    Args:
        rule_cls: The rule class (must subclass ``Rule`` with ``PARAM_MAP``).
        settings: A ``ValidationSettings`` instance or None.

    Returns:
        Dict mapping constructor kwarg names to float values (ready to
        unpack into rule_cls(**merged_params)).
    """
    if settings is None:
        return {}

    param_map: dict[str, str] = getattr(rule_cls, "PARAM_MAP", {})
    if not param_map:
        return {}

    rule_id = _get_rule_id_from_cls(rule_cls)
    if rule_id is None:
        return {}

    override = settings.get_override(rule_id)
    if override is None:
        return {}

    kwargs: dict[str, float] = {}

    if override.warn_threshold is not None and "warn_threshold" in param_map:
        kwargs[param_map["warn_threshold"]] = override.warn_threshold

    if override.fail_threshold is not None and "fail_threshold" in param_map:
        kwargs[param_map["fail_threshold"]] = override.fail_threshold

    _apply_extra_params(param_map, override.extra_params, kwargs)

    return kwargs


def _get_rule_cls_for_step(rule_id: str) -> type | None:
    """Look up the rule class for a given rule_id from the global registry."""
    try:
        from specweaver.assurance.validation.registry import get_registry

        return get_registry().get(rule_id)
    except Exception:
        return None


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
        from specweaver.assurance.validation.registry import get_registry

        registry = get_registry()

    results: list[RuleResult] = []
    logger.debug(
        "execute_validation_pipeline: running '%s' (%d steps)",
        pipeline.name,
        len(pipeline.steps),
    )

    for step in pipeline.steps:
        rule_cls = registry.get(step.rule)

        if rule_cls is None:
            logger.warning(
                "execute_validation_pipeline: unknown rule '%s' in step '%s', skipping",
                step.rule,
                step.name,
            )
            results.append(
                RuleResult(
                    rule_id=step.rule,
                    rule_name=step.name,
                    status=Status.FAIL,
                    message=f"Unknown rule '{step.rule}': not found in registry",
                )
            )
            continue

        try:
            rule = rule_cls(**step.params)
        except Exception as exc:
            logger.exception(
                "execute_validation_pipeline: failed to instantiate rule '%s' with params %s",
                step.rule,
                step.params,
            )
            results.append(
                RuleResult(
                    rule_id=step.rule,
                    rule_name=step.name,
                    status=Status.FAIL,
                    message=f"Failed to instantiate rule '{step.rule}': {exc}",
                )
            )
            continue

        try:
            result = rule.check(spec_text, spec_path)
        except Exception as exc:
            logger.exception(
                "execute_validation_pipeline: rule '%s' (%s) crashed",
                rule.rule_id,
                rule.name,
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
        pipeline.name,
        len(results),
        len(results) - failed,
        failed,
    )
    return results


def apply_settings_to_pipeline(
    pipeline: ValidationPipeline,
    settings: ValidationSettings | None,
) -> ValidationPipeline:
    """Apply ValidationSettings overrides onto a pipeline.

    Bridges the DB settings system (thresholds, enabled/disabled) with
    the validation sub-pipeline architecture.

    - Disabled rules: their steps are removed from the pipeline.
    - Threshold overrides: merged into step.params via the rule's PARAM_MAP.

    Args:
        pipeline: A resolved ValidationPipeline.
        settings: A ValidationSettings instance or None.

    Returns:
        A new ValidationPipeline with settings applied.
    """
    if settings is None:
        return pipeline

    from specweaver.assurance.validation.pipeline import ValidationPipeline as _Pipeline
    from specweaver.assurance.validation.pipeline import ValidationStep

    new_steps: list[ValidationStep] = []
    for step in pipeline.steps:
        # Check if rule is disabled
        if not settings.is_enabled(step.rule):
            logger.debug(
                "apply_settings_to_pipeline: rule '%s' disabled by settings, removing",
                step.rule,
            )
            continue

        # Merge threshold/extra_params overrides into step.params via PARAM_MAP
        rule_cls = _get_rule_cls_for_step(step.rule)
        kwargs = _build_rule_kwargs(rule_cls, settings) if rule_cls else {}
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
