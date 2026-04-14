# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for ScenarioConverter — mechanical YAML to parametrized pytest."""

from __future__ import annotations

import re

from specweaver.workflows.scenarios.scenario_converter import ScenarioConverter
from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet


def _make_scenario(**overrides: object) -> ScenarioDefinition:
    """Helper to create a ScenarioDefinition with defaults."""
    defaults = {
        "name": "happy_login",
        "description": "Valid credentials return token",
        "function_under_test": "login",
        "req_id": "FR-1",
        "category": "happy",
        "preconditions": [],
        "input_summary": "valid creds",
        "inputs": {"username": "admin", "password": "pass"},
        "expected_behavior": "returns token",
        "expected_output": {"token": "abc"},
    }
    defaults.update(overrides)
    return ScenarioDefinition(**defaults)


def _make_scenario_set(scenarios: list[ScenarioDefinition] | None = None) -> ScenarioSet:
    """Helper to create a ScenarioSet."""
    return ScenarioSet(
        spec_path="specs/auth_spec.md",
        contract_path="contracts/auth_contract.py",
        scenarios=[_make_scenario()] if scenarios is None else scenarios,
    )


class TestScenarioConverter:
    """Tests for ScenarioConverter.convert."""

    def test_convert_single_scenario(self) -> None:
        """Produces valid pytest file string for a single scenario."""
        result = ScenarioConverter.convert(_make_scenario_set())
        assert "def test_" in result
        assert "import pytest" in result

    def test_convert_multiple_scenarios(self) -> None:
        """Handles multiple scenarios, groups by function_under_test."""
        scenarios = [
            _make_scenario(name="happy_login", req_id="FR-1"),
            _make_scenario(name="error_login", req_id="FR-1", category="error"),
            _make_scenario(
                name="happy_register",
                function_under_test="register",
                req_id="FR-2",
            ),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios))
        assert "def test_" in result
        # Should have test functions for both login and register
        assert "login" in result
        assert "register" in result

    def test_trace_tag_format(self) -> None:
        """Output contains # @trace(FR-X) in C09-compatible format."""
        result = ScenarioConverter.convert(_make_scenario_set())
        # C09 regex: r"@trace\((?:N)?FR-\d+\)"
        trace_matches = re.findall(r"@trace\((?:N)?FR-\d+\)", result)
        assert len(trace_matches) >= 1
        assert "@trace(FR-1)" in result

    def test_parametrize_decorator(self) -> None:
        """Output contains @pytest.mark.parametrize when multiple scenarios per function."""
        scenarios = [
            _make_scenario(name="happy_login", inputs={"u": "a"}),
            _make_scenario(name="error_login", inputs={"u": ""}, category="error"),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios))
        assert "@pytest.mark.parametrize" in result

    def test_empty_scenarios(self) -> None:
        """Produces valid but empty-ish test file for empty scenario list."""
        result = ScenarioConverter.convert(_make_scenario_set([]))
        assert "Auto-generated" in result
        # Should still have the import and docstring but no test functions
        assert "def test_" not in result

    def test_no_contract_import(self) -> None:
        """Output does NOT import from contracts/ at runtime (HITL decision)."""
        result = ScenarioConverter.convert(_make_scenario_set())
        assert "from contracts" not in result
        assert "import contracts" not in result

    def test_output_is_valid_python(self) -> None:
        """Generated output compiles as valid Python."""
        result = ScenarioConverter.convert(_make_scenario_set())
        compile(result, "<scenario_test>", "exec")  # Raises SyntaxError if invalid

    def test_nfr_trace_tag(self) -> None:
        """NFR tags produce valid trace comments."""
        scenario = _make_scenario(req_id="NFR-3")
        result = ScenarioConverter.convert(_make_scenario_set([scenario]))
        assert "@trace(NFR-3)" in result
