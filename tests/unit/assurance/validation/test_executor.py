# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the validation sub-pipeline executor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.executor import execute_validation_pipeline
from specweaver.assurance.validation.models import Rule, RuleResult, Status
from specweaver.assurance.validation.pipeline import ValidationPipeline, ValidationStep
from specweaver.assurance.validation.registry import RuleRegistry

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Test rules
# ---------------------------------------------------------------------------


class _AlwaysPassRule(Rule):
    @property
    def rule_id(self) -> str:
        return "T01"

    @property
    def name(self) -> str:
        return "Always Pass"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass(f"checked: {len(spec_text)} chars")


class _AlwaysFailRule(Rule):
    @property
    def rule_id(self) -> str:
        return "T02"

    @property
    def name(self) -> str:
        return "Always Fail"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._fail("nope")


class _ThresholdRule(Rule):
    """Rule with configurable threshold via constructor."""

    def __init__(self, threshold: int = 50) -> None:
        self._threshold = threshold

    @property
    def rule_id(self) -> str:
        return "T03"

    @property
    def name(self) -> str:
        return "Threshold Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if len(spec_text) < self._threshold:
            return self._fail(f"too short (< {self._threshold})")
        return self._pass(f"ok (>= {self._threshold})")


class _CrashRule(Rule):
    @property
    def rule_id(self) -> str:
        return "T04"

    @property
    def name(self) -> str:
        return "Crash Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        msg = "intentional crash"
        raise RuntimeError(msg)


class _ContextRule(Rule):
    @property
    def rule_id(self) -> str:
        return "T05"

    @property
    def name(self) -> str:
        return "Context Rule"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        if self.context.get("marker") == "found":
            return self._pass("found it in context")
        return self._fail("not found in context")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_registry():
    """Registry populated with test rules."""
    reg = RuleRegistry()
    reg.register("T01", _AlwaysPassRule, "spec")
    reg.register("T02", _AlwaysFailRule, "spec")
    reg.register("T03", _ThresholdRule, "spec")
    reg.register("T04", _CrashRule, "spec")
    reg.register("T05", _ContextRule, "spec")
    return reg


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------


class TestExecuteValidationPipeline:
    """Test execute_validation_pipeline()."""

    def test_single_passing_rule(self, test_registry):
        pipeline = ValidationPipeline(
            name="test",
            steps=[ValidationStep(name="t01", rule="T01")],
        )
        results = execute_validation_pipeline(pipeline, "hello world", registry=test_registry)
        assert len(results) == 1
        assert results[0].status == Status.PASS
        assert results[0].rule_id == "T01"

    def test_multiple_rules(self, test_registry):
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="t01", rule="T01"),
                ValidationStep(name="t02", rule="T02"),
            ],
        )
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert len(results) == 2
        assert results[0].status == Status.PASS
        assert results[1].status == Status.FAIL

    def test_params_passed_to_rule(self, test_registry):
        """Step params are forwarded as constructor kwargs."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="t03", rule="T03", params={"threshold": 5}),
            ],
        )
        # "hello" is 5 chars, threshold is 5, so it should pass
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert results[0].status == Status.PASS

    def test_params_threshold_fail(self, test_registry):
        """Step params cause rule to fail when threshold not met."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="t03", rule="T03", params={"threshold": 100}),
            ],
        )
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert results[0].status == Status.FAIL

    def test_crashing_rule_skipped(self, test_registry):
        """Crashing rule produces FAIL result, doesn't stop pipeline."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="t04", rule="T04"),
                ValidationStep(name="t01", rule="T01"),
            ],
        )
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert len(results) == 2
        assert results[0].status == Status.FAIL
        assert "crash" in results[0].message.lower()
        assert results[1].status == Status.PASS

    def test_unknown_rule_skipped(self, test_registry):
        """Unknown rule ID produces FAIL result, doesn't stop pipeline."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="unknown", rule="X99"),
                ValidationStep(name="t01", rule="T01"),
            ],
        )
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert len(results) == 2
        assert results[0].status == Status.FAIL
        assert "X99" in results[0].message
        assert results[1].status == Status.PASS

    def test_empty_pipeline(self, test_registry):
        """Empty pipeline returns empty results."""
        pipeline = ValidationPipeline(name="empty", steps=[])
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert results == []

    def test_execution_order_preserved(self, test_registry):
        """Results are in step order."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="t02", rule="T02"),
                ValidationStep(name="t01", rule="T01"),
            ],
        )
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert results[0].rule_id == "T02"
        assert results[1].rule_id == "T01"

    def test_invalid_constructor_params_handled(self, test_registry):
        """Invalid constructor kwargs produce FAIL result, don't stop pipeline."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                # T03 (_ThresholdRule) expects 'threshold', not 'bogus_param'
                ValidationStep(name="t03", rule="T03", params={"bogus_param": 42}),
                ValidationStep(name="t01", rule="T01"),
            ],
        )
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert len(results) == 2
        assert results[0].status == Status.FAIL
        assert "instantiate" in results[0].message.lower() or "T03" in results[0].message
        # Second rule still runs
        assert results[1].status == Status.PASS

    def test_ast_payload_assigned_to_context(self, test_registry):
        """ast_payload is popped from params and assigned to rule.context safely."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="t05", rule="T05", params={"ast_payload": {"marker": "found"}}),
            ],
        )
        results = execute_validation_pipeline(pipeline, "hello", registry=test_registry)
        assert len(results) == 1
        assert results[0].status == Status.PASS
        assert "found it in context" in results[0].message

    def test_execute_validation_pipeline_with_context(self, test_registry):
        """context kwargs are successfully merged into rule.context via DI."""
        pipeline = ValidationPipeline(
            name="test",
            steps=[
                ValidationStep(name="t05", rule="T05", params={"ast_payload": {"other": "value"}}),
            ],
        )
        context_di = {"marker": "found", "analyzer_factory": "mock_factory"}
        results = execute_validation_pipeline(
            pipeline, "hello", registry=test_registry, context=context_di
        )
        assert len(results) == 1
        assert results[0].status == Status.PASS
        assert "found it in context" in results[0].message
