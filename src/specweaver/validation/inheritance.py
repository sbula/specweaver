# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Validation pipeline inheritance -- extends/override/remove/add.

Resolves a child ValidationPipeline against its base pipeline into a
flat, fully-resolved pipeline with no inheritance markers.

Resolution order:
    1. Load base pipeline via extends
    2. Apply 'remove' -- drop named steps
    3. Apply 'override' -- merge params into existing steps
    4. Apply 'add' -- insert new steps at specified positions
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any

from specweaver.validation.pipeline import ValidationPipeline, ValidationStep

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def resolve_pipeline(
    pipeline: ValidationPipeline,
    base_loader: Callable[[str], ValidationPipeline],
) -> ValidationPipeline:
    """Resolve a pipeline's inheritance into a flat step list.

    If the pipeline has no ``extends``, it is returned as-is.

    Args:
        pipeline: The pipeline to resolve (may have extends/override/remove/add).
        base_loader: Callable that loads a base pipeline by name.
            Raises FileNotFoundError if the base is not found.

    Returns:
        A new ValidationPipeline with all inheritance resolved --
        steps are fully materialized, no extends/override/remove/add fields.

    Raises:
        FileNotFoundError: If the base pipeline is not found.
        ValueError: If override/remove/add references a nonexistent step name.
    """
    if pipeline.extends is None:
        return pipeline

    base = base_loader(pipeline.extends)
    logger.debug(
        "Resolving pipeline '%s' from base '%s' (%d base steps)",
        pipeline.name, pipeline.extends, len(base.steps),
    )

    steps = copy.deepcopy(base.steps)
    steps = _apply_remove(steps, pipeline)
    _apply_overrides(steps, pipeline)
    _apply_adds(steps, pipeline)

    return ValidationPipeline(
        name=pipeline.name,
        description=pipeline.description or base.description,
        version=pipeline.version,
        steps=steps,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_remove(
    steps: list[ValidationStep],
    pipeline: ValidationPipeline,
) -> list[ValidationStep]:
    """Remove named steps, raising ValueError for unknown names."""
    if not pipeline.remove:
        return steps

    step_names = {s.name for s in steps}
    for name in pipeline.remove:
        if name not in step_names:
            msg = (
                f"Cannot remove step '{name}' from pipeline "
                f"'{pipeline.name}': not found in base '{pipeline.extends}'. "
                f"Available: {sorted(step_names)}"
            )
            raise ValueError(msg)

    remove_set = set(pipeline.remove)
    result = [s for s in steps if s.name not in remove_set]
    logger.debug("After remove: %d steps", len(result))
    return result


def _apply_overrides(
    steps: list[ValidationStep],
    pipeline: ValidationPipeline,
) -> None:
    """Merge override params into existing steps (mutates in place)."""
    if not pipeline.override:
        return

    step_names = {s.name for s in steps}
    for name, overrides in pipeline.override.items():
        if name not in step_names:
            msg = (
                f"Cannot override step '{name}' in pipeline "
                f"'{pipeline.name}': not found in base '{pipeline.extends}'. "
                f"Available: {sorted(step_names)}"
            )
            raise ValueError(msg)
        for step in steps:
            if step.name == name:
                _merge_params(step, overrides)
                break

    logger.debug("Applied %d overrides", len(pipeline.override))


def _apply_adds(
    steps: list[ValidationStep],
    pipeline: ValidationPipeline,
) -> None:
    """Insert new steps at specified positions (mutates in place)."""
    if not pipeline.add:
        return

    for add_spec in pipeline.add:
        new_step = ValidationStep(
            name=add_spec["name"],
            rule=add_spec["rule"],
            params=add_spec.get("params", {}),
            path=add_spec.get("path"),
        )
        after = add_spec.get("after")
        before = add_spec.get("before")

        if after:
            idx = _find_step_index(steps, after, pipeline.name)
            steps.insert(idx + 1, new_step)
        elif before:
            idx = _find_step_index(steps, before, pipeline.name)
            steps.insert(idx, new_step)
        else:
            steps.append(new_step)

    logger.debug("After add: %d steps", len(steps))


def _merge_params(step: ValidationStep, overrides: dict[str, Any]) -> None:
    """Merge override params into a step (mutates in place)."""
    if "params" in overrides:
        step.params = {**step.params, **overrides["params"]}


def _find_step_index(
    steps: list[ValidationStep],
    name: str,
    pipeline_name: str,
) -> int:
    """Find index of a step by name, raising ValueError if not found."""
    for i, s in enumerate(steps):
        if s.name == name:
            return i
    step_names = sorted(s.name for s in steps)
    msg = (
        f"Cannot find step '{name}' for add placement in pipeline "
        f"'{pipeline_name}'. Available: {step_names}"
    )
    raise ValueError(msg)
