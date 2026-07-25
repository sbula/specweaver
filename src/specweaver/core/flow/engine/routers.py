# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pipeline dynamic routing logic.

This module evaluates pipeline router rules against runtime step results.
It strictly avoids `eval()` and complex AST execution by relying purely on
declarative operators mapping to native Python comparative logic.
"""

import logging
from typing import Any

from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    RouterDefinition,
    RouterRule,
    RuleOperator,
)

logger = logging.getLogger(__name__)


class RouterEvaluator:
    """Evaluates RouterDefinitions against runtime step results to decide next targets."""

    def evaluate(self, router: RouterDefinition, result_data: dict[str, Any]) -> str:
        """Evaluate the rules against the data and return the target step name.

        The rules are evaluated in sequential order. The first rule to match
        dictates the target. If no rules match, the default_target is returned.

        Args:
            router: The router definition to evaluate.
            result_data: A dictionary containing the step's execution outputs.

        Returns:
            The string target name.
        """
        for rule in router.rules:
            if self._evaluate_rule(rule, result_data):
                return rule.target

        return router.default_target

    def _get_nested_field(self, field_path: str, data: dict[str, Any]) -> Any:
        """Resolve a dot-separated field path against a dictionary."""
        parts = field_path.split(".")
        current = data

        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]

        return current

    def _evaluate_rule(self, rule: RouterRule, data: dict[str, Any]) -> bool:
        """Evaluate a single rule against the data."""
        actual_value = self._get_nested_field(rule.field, data)
        target_value = rule.value
        op = rule.operator

        # IS_EMPTY / NOT_EMPTY are unary operators
        if op == RuleOperator.IS_EMPTY:
            return not bool(actual_value)

        if op == RuleOperator.NOT_EMPTY:
            return bool(actual_value)

        return self._evaluate_binary_rule(op, actual_value, target_value)

    def _evaluate_binary_rule(self, op: RuleOperator, actual: Any, target: Any) -> bool:
        """Evaluate binary comparison operators."""
        if op == RuleOperator.EQ:
            return bool(actual == target)

        if op == RuleOperator.NEQ:
            return bool(actual != target)

        if op == RuleOperator.IN:
            if not isinstance(target, list):
                return False
            return bool(actual in target)

        if op == RuleOperator.CONTAINS:
            if not isinstance(actual, (str, list, tuple)):
                return False
            return bool(target in actual)

        if op in (RuleOperator.LT, RuleOperator.GT):
            return self._evaluate_numeric_rule(op, actual, target)

        return False

    def _evaluate_numeric_rule(self, op: RuleOperator, actual: Any, target: Any) -> bool:
        """Evaluate numeric comparison operators."""
        if not (isinstance(actual, (int, float)) and isinstance(target, (int, float))):
            return False
        if op == RuleOperator.LT:
            return bool(actual < target)
        if op == RuleOperator.GT:
            return bool(actual > target)
        return False


def resolve_route_target(
    evaluator: RouterEvaluator,
    router: RouterDefinition,
    result_output: dict[str, Any],
    pipeline: PipelineDefinition,
    current_step: int,
    route_jumps: int,
) -> tuple[int | None, str | None, int]:
    """Resolve a router to a concrete step index, guarding unknown targets and route loops.

    Returns ``(target_idx, error_message, route_jumps)``. When ``error_message`` is not None
    the caller must fail the run; ``target_idx`` is then meaningless.

    Extracted from ``PipelineRunner._execute_loop`` so router resolution lives in the router
    module rather than the loop, and so the loop stays within the file-size budget.
    """
    target_step_name = evaluator.evaluate(router, result_output)
    target_idx = pipeline.get_step_index(target_step_name)

    if target_idx is None:
        # Defensive: invalid targets are normally trapped by PipelineDefinition.validate_flow().
        return None, f"Router resolved to unknown step '{target_step_name}'", route_jumps

    if target_idx <= current_step:
        route_jumps += 1
        if route_jumps > pipeline.max_total_loops:
            return (
                None,
                "Infinite routing loop detected: exceeded max_total_loops "
                f"({pipeline.max_total_loops})",
                route_jumps,
            )

    return target_idx, None, route_jumps
