# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Validation runner — loads rules, runs them, collects results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.validation.models import RuleResult, Status

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.validation.models import Rule


def get_spec_rules(*, include_llm: bool = False) -> list[Rule]:
    """Get all registered spec validation rules.

    Args:
        include_llm: If False, skip rules that require an LLM adapter.

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

    all_rules: list[Rule] = [
        OneSentenceRule(),
        SingleSetupRule(),
        StrangerTestRule(),
        DependencyDirectionRule(),
        DayTestRule(),
        ConcreteExampleRule(),
        TestFirstRule(),
        AmbiguityRule(),
        ErrorPathRule(),
        DoneDefinitionRule(),
    ]

    if include_llm:
        return all_rules

    return [r for r in all_rules if not r.requires_llm]


def get_code_rules(*, include_subprocess: bool = True) -> list[Rule]:
    """Get all registered code validation rules.

    Args:
        include_subprocess: If False, skip rules that run subprocesses
            (C03 Tests Pass, C04 Coverage). Useful for unit tests.

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

    all_rules: list[Rule] = [
        SyntaxValidRule(),
        TestsExistRule(),
        ImportDirectionRule(),
        NoBareExceptRule(),
        NoOrphanTodoRule(),
        TypeHintsRule(),
    ]

    if include_subprocess:
        all_rules[2:2] = [TestsPassRule(), CoverageRule()]

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

    for rule in rules:
        try:
            result = rule.check(spec_text, spec_path)
        except Exception as exc:
            result = RuleResult(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                status=Status.FAIL,
                message=f"Rule crashed: {type(exc).__name__}: {exc}",
            )
        results.append(result)

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
