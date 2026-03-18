# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Validation runner — loads rules, runs them, collects results."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.validation.models import RuleResult, Status

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.config.settings import ValidationSettings
    from specweaver.validation.models import Rule
    from specweaver.validation.spec_kind import SpecKind

logger = logging.getLogger(__name__)


# Mapping: rule_id → constructor kwarg names for threshold-bearing rules
_THRESHOLD_PARAMS: dict[str, dict[str, str]] = {
    "S01": {
        "warn_threshold": "warn_conjunctions",
        "fail_threshold": "fail_conjunctions",
        "extra:max_h2": "max_h2",
    },
    "S03": {"warn_threshold": "warn_threshold", "fail_threshold": "fail_threshold"},
    "S04": {"warn_threshold": "warn_threshold", "fail_threshold": "fail_threshold"},
    "S05": {"warn_threshold": "warn_threshold", "fail_threshold": "fail_threshold"},
    "S07": {"warn_threshold": "warn_score", "fail_threshold": "fail_score"},
    "S08": {"warn_threshold": "warn_threshold", "fail_threshold": "fail_threshold"},
    "S11": {"warn_threshold": "warn_threshold", "fail_threshold": "fail_threshold"},
    "C04": {"fail_threshold": "threshold"},
}


def _build_rule_kwargs(
    rule_id: str,
    settings: ValidationSettings | None,
) -> dict[str, float]:
    """Build constructor kwargs for a rule based on settings overrides.

    Handles three sources of overrides:
    - ``warn_threshold`` / ``fail_threshold`` from the standard fields
    - ``extra_params`` from ``RuleOverride.extra_params`` (e.g. ``max_h2``)
    """
    if settings is None:
        return {}

    override = settings.get_override(rule_id)
    if override is None:
        return {}

    param_map = _THRESHOLD_PARAMS.get(rule_id, {})
    kwargs: dict[str, float] = {}

    if override.warn_threshold is not None and "warn_threshold" in param_map:
        kwargs[param_map["warn_threshold"]] = override.warn_threshold
    if override.fail_threshold is not None and "fail_threshold" in param_map:
        kwargs[param_map["fail_threshold"]] = override.fail_threshold

    # Map extra_params via "extra:<key>" entries in _THRESHOLD_PARAMS
    for map_key, constructor_arg in param_map.items():
        if map_key.startswith("extra:"):
            extra_key = map_key.removeprefix("extra:")
            if extra_key in override.extra_params:
                kwargs[constructor_arg] = override.extra_params[extra_key]

    return kwargs


def get_spec_rules(
    *,
    include_llm: bool = False,
    settings: ValidationSettings | None = None,
    run_all: bool = False,
    kind: SpecKind | None = None,
) -> list[Rule]:
    """Get all registered spec validation rules.

    Args:
        include_llm: If False, skip rules that require an LLM adapter.
        settings: Per-project validation overrides (thresholds, enable/disable).
        run_all: If True, ignore the enabled flag in settings (run everything).
        kind: Spec kind (feature/component). If set, kind-specific presets
            are applied as a base layer below settings overrides.

    Returns:
        List of Rule instances, ordered by rule_id.
    """
    from specweaver.validation.rules.spec.s01_one_sentence import OneSentenceRule
    from specweaver.validation.rules.spec.s02_single_setup import SingleSetupRule
    from specweaver.validation.rules.spec.s03_stranger import StrangerTestRule
    from specweaver.validation.rules.spec.s04_dependency_dir import DependencyDirectionRule
    from specweaver.validation.rules.spec.s05_day_test import DayTestRule
    from specweaver.validation.rules.spec.s06_concrete_example import ConcreteExampleRule
    from specweaver.validation.rules.spec.s07_test_first import TestFirstRule
    from specweaver.validation.rules.spec.s08_ambiguity import AmbiguityRule
    from specweaver.validation.rules.spec.s09_error_path import ErrorPathRule
    from specweaver.validation.rules.spec.s10_done_definition import DoneDefinitionRule
    from specweaver.validation.rules.spec.s11_terminology import TerminologyRule

    rule_classes: list[tuple[str, type]] = [
        ("S01", OneSentenceRule),
        ("S02", SingleSetupRule),
        ("S03", StrangerTestRule),
        ("S04", DependencyDirectionRule),
        ("S05", DayTestRule),
        ("S06", ConcreteExampleRule),
        ("S07", TestFirstRule),
        ("S08", AmbiguityRule),
        ("S09", ErrorPathRule),
        ("S10", DoneDefinitionRule),
        ("S11", TerminologyRule),
    ]

    all_rules: list[Rule] = []
    skipped: list[str] = []
    for rule_id, cls in rule_classes:
        # Skip disabled rules (unless run_all)
        if not run_all and settings and not settings.is_enabled(rule_id):
            skipped.append(rule_id)
            continue
        kwargs = _build_rule_kwargs(rule_id, settings)
        # Merge kind presets (base layer) underneath settings overrides
        if kind is not None:
            from specweaver.validation.spec_kind import get_presets
            presets = get_presets(rule_id, kind)
            # Presets provide base; settings overrides already in kwargs win
            merged = {**presets, **kwargs}
        else:
            merged = kwargs
        all_rules.append(cls(**merged))

    if skipped:
        logger.debug("get_spec_rules: skipped disabled rules: %s", ', '.join(skipped))
    logger.debug("get_spec_rules: loaded %d spec rules (include_llm=%s)", len(all_rules), include_llm)

    if include_llm:
        return all_rules

    return [r for r in all_rules if not r.requires_llm]


def get_code_rules(
    *,
    include_subprocess: bool = True,
    settings: ValidationSettings | None = None,
    run_all: bool = False,
) -> list[Rule]:
    """Get all registered code validation rules.

    Args:
        include_subprocess: If False, skip rules that run subprocesses
            (C03 Tests Pass, C04 Coverage). Useful for unit tests.
        settings: Per-project validation overrides (thresholds, enable/disable).
        run_all: If True, ignore the enabled flag in settings.

    Returns:
        List of Rule instances, ordered by rule_id.
    """
    from specweaver.validation.rules.code.c01_syntax_valid import SyntaxValidRule
    from specweaver.validation.rules.code.c02_tests_exist import TestsExistRule
    from specweaver.validation.rules.code.c03_tests_pass import TestsPassRule
    from specweaver.validation.rules.code.c04_coverage import CoverageRule
    from specweaver.validation.rules.code.c05_import_direction import ImportDirectionRule
    from specweaver.validation.rules.code.c06_no_bare_except import NoBareExceptRule
    from specweaver.validation.rules.code.c07_no_orphan_todo import NoOrphanTodoRule
    from specweaver.validation.rules.code.c08_type_hints import TypeHintsRule

    rule_classes: list[tuple[str, type]] = [
        ("C01", SyntaxValidRule),
        ("C02", TestsExistRule),
        ("C05", ImportDirectionRule),
        ("C06", NoBareExceptRule),
        ("C07", NoOrphanTodoRule),
        ("C08", TypeHintsRule),
    ]

    if include_subprocess:
        # Insert C03, C04 at position 2 (after C02)
        rule_classes[2:2] = [
            ("C03", TestsPassRule),
            ("C04", CoverageRule),
        ]

    all_rules: list[Rule] = []
    skipped: list[str] = []
    for rule_id, cls in rule_classes:
        if not run_all and settings and not settings.is_enabled(rule_id):
            skipped.append(rule_id)
            continue
        kwargs = _build_rule_kwargs(rule_id, settings)
        all_rules.append(cls(**kwargs))

    if skipped:
        logger.debug("get_code_rules: skipped disabled rules: %s", ', '.join(skipped))
    logger.debug("get_code_rules: loaded %d code rules (include_subprocess=%s)", len(all_rules), include_subprocess)

    return all_rules



def run_rules(
    rules: list[Rule],
    spec_text: str,
    spec_path: Path | None = None,
) -> list[RuleResult]:
    """Run a list of rules against spec content.

    Args:
        rules: Rules to execute.
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
        len(results), len(results) - failed, failed,
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
