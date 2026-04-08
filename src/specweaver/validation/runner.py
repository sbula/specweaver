# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation runner — runs rule lists and aggregates results.

Provides lightweight utility functions used by tests and the pipeline
executor to run lists of already-instantiated Rule objects.

NOTE ON DESIGN (Feature 3.5b):
  Rule instantiation with threshold overrides now happens via the pipeline
  executor (see specweaver.validation.executor).  This module retains only
  the stateless utility functions that operate on *already-constructed* rule
  instances: run_rules(), count_by_status(), all_passed().

  The ``get_spec_rules()`` and ``get_code_rules()`` helpers have been
  **removed**.  Tests and application code must use the pipeline executor
  path:

      from specweaver.validation.pipeline_loader import load_pipeline_yaml
      from specweaver.validation.executor import (
          apply_settings_to_pipeline,
          execute_validation_pipeline,
      )

      pipeline = load_pipeline_yaml("validation_spec_default")
      pipeline = apply_settings_to_pipeline(pipeline, settings)  # optional
      results  = execute_validation_pipeline(pipeline, spec_text)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.validation.models import RuleResult, Status

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.validation.models import Rule

logger = logging.getLogger(__name__)


def run_rules(
    rules: list[Rule],
    spec_text: str,
    spec_path: Path | None = None,
) -> list[RuleResult]:
    """Run a list of pre-instantiated rules against spec content.

    Args:
        rules: Rules to execute (already constructed with desired params).
        spec_text: Full text content of the spec file.
        spec_path: Optional path to the spec file.

    Returns:
        List of RuleResults, one per rule (in order).
        If a rule raises an exception, its result is FAIL with the error message.
    """
    results: list[RuleResult] = []
    logger.debug("run_rules: executing %d rules", len(rules))

    for rule in rules:
        try:
            result = rule.check(spec_text, spec_path)
        except Exception as exc:
            logger.exception("run_rules: rule '%s' (%s) crashed", rule.rule_id, rule.name)
            result = RuleResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                status=Status.FAIL,
                message=f"Rule crashed: {type(exc).__name__}: {exc}",
            )
        results.append(result)

    failed = sum(1 for r in results if r.status == Status.FAIL)
    logger.info(
        "run_rules: %d rules executed — %d passed, %d failed",
        len(results),
        len(results) - failed,
        failed,
    )
    return results


def count_by_status(results: list[RuleResult]) -> dict[Status, int]:
    """Count results by status."""
    counts: dict[Status, int] = {s: 0 for s in Status}
    for r in results:
        counts[r.status] += 1
    return counts


def all_passed(results: list[RuleResult]) -> bool:
    """Check if all results are PASS or SKIP (no FAIL or WARN)."""
    return all(r.status in (Status.PASS, Status.SKIP) for r in results)
