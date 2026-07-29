# mypy: ignore-errors
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
        """@pytest.mark.parametrize appears for multiple SAME-category scenarios
        per function (INT-US-24 SF-03: groups are (function, category)-keyed —
        raise-asserting and equality-asserting rows cannot share one body)."""
        scenarios = [
            _make_scenario(name="happy_login", inputs={"u": "a"}),
            _make_scenario(name="happy_login_alt", inputs={"u": "b"}),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios))
        assert "@pytest.mark.parametrize" in result

    def test_mixed_categories_split_into_separate_groups(self) -> None:
        """A happy + error pair for one function yields two distinct tests."""
        scenarios = [
            _make_scenario(name="happy_login", inputs={"u": "a"}),
            _make_scenario(name="error_login", inputs={"u": ""}, category="error"),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios))
        assert "def test_login_happy" in result
        assert "def test_login_error" in result
        assert "pytest.raises(Exception)" in result

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


# ---------------------------------------------------------------------------
# INT-US-24 SF-03 T1 (inherited defect #6): the emitted tests are REAL —
# they import the target, call it with the scenario inputs, and assert the
# expected output. Stub bodies ("...") were the defect.
# ---------------------------------------------------------------------------


class TestRealTestBodies:
    def test_single_scenario_calls_target_and_asserts(self) -> None:
        # [Happy] real body: file-anchored loader + call + equality assert.
        result = ScenarioConverter.convert(_make_scenario_set(), stem="auth")
        assert "spec_from_file_location" in result
        assert "auth.py" in result
        assert "login(**" in result
        assert repr({"token": "abc"}) in result
        # No stub bodies left anywhere.
        assert "\n    ...\n" not in result

    def test_parametrized_group_consumes_inputs_expected(self) -> None:
        # [Happy] the parametrize data is no longer decorative.
        scenarios = [
            _make_scenario(name="a", inputs={"u": "x"}, expected_output=1),
            _make_scenario(name="b", inputs={"u": "y"}, expected_output=2),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios), stem="auth")
        assert "login(**inputs)" in result
        assert "== expected" in result
        assert "\n    ...\n" not in result

    def test_error_category_wraps_in_pytest_raises(self) -> None:
        # [Happy] error scenarios expect a raise (mechanical v1: Exception).
        scenario = _make_scenario(category="error", expected_output=None)
        result = ScenarioConverter.convert(_make_scenario_set([scenario]), stem="auth")
        assert "pytest.raises(Exception)" in result

    def test_expected_none_happy_is_smoke_call(self) -> None:
        # [Boundary] expected None + happy → call must not raise; no equality
        # assert against None, no pytest.raises.
        scenario = _make_scenario(expected_output=None)
        result = ScenarioConverter.convert(_make_scenario_set([scenario]), stem="auth")
        assert "login(**" in result
        assert "pytest.raises" not in result
        assert "== None" not in result

    def test_handler_stem_wins_over_spec_path(self) -> None:
        # [Boundary/R/B RED-2] the loader anchor comes from the HANDLER-known
        # stem, never from the LLM-authored spec_path.
        scenario_set = ScenarioSet(
            spec_path="specs/fake_spec.md", contract_path="c", scenarios=[_make_scenario()]
        )
        result = ScenarioConverter.convert(scenario_set, stem="real")
        assert "real.py" in result
        assert "fake.py" not in result

    def test_stem_fallback_derives_from_spec_path(self) -> None:
        # [Boundary] no stem given → validated fallback from spec_path.
        result = ScenarioConverter.convert(_make_scenario_set())
        assert "auth.py" in result

    def test_garbage_spec_path_without_stem_raises(self) -> None:
        # [Hostile] no stem AND unusable spec_path → loud ValueError, never a
        # broken loader.
        import pytest as _pytest

        scenario_set = ScenarioSet(spec_path="", contract_path="c", scenarios=[_make_scenario()])
        with _pytest.raises(ValueError, match="stem"):
            ScenarioConverter.convert(scenario_set)

    def test_non_identifier_function_rejected(self) -> None:
        # [Hostile] injection guard: emitted code calls the function by NAME —
        # a non-identifier (incl. dotted) must reject loud.
        import pytest as _pytest

        for hostile in ("os.system", "x; import os", "not-an-identifier!"):
            scenario = _make_scenario(function_under_test=hostile)
            with _pytest.raises(ValueError, match="identifier"):
                ScenarioConverter.convert(_make_scenario_set([scenario]), stem="auth")

    def test_hostile_scenario_name_cannot_break_emission(self) -> None:
        # [Hostile] a quote in the LLM-chosen name must not escape the emitted
        # param id string — file still compiles.
        scenarios = [
            _make_scenario(name='evil", "injected', inputs={"u": "x"}, expected_output=1),
            _make_scenario(name="ok", inputs={"u": "y"}, expected_output=2),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios), stem="auth")
        compile(result, "<scenario_test>", "exec")

    def test_parametrized_error_group_uses_raises_body(self) -> None:
        # [Boundary] G-a: >=2 error scenarios for one function share a
        # parametrized body that asserts a raise (never equality).
        scenarios = [
            _make_scenario(name="err_a", category="error", inputs={"u": ""}, expected_output=None),
            _make_scenario(
                name="err_b", category="error", inputs={"u": None}, expected_output=None
            ),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios), stem="auth")
        compile(result, "<scenario_test>", "exec")
        assert "def test_login_error_scenarios" in result
        assert "pytest.raises(Exception)" in result
        assert "== expected" not in result

    def test_underscore_spec_stem_fallback_rejected(self) -> None:
        # [Hostile] G-a: "specs/_spec.md" derives an EMPTY stem → loud ValueError.
        import pytest as _pytest

        scenario_set = ScenarioSet(
            spec_path="specs/_spec.md", contract_path="c", scenarios=[_make_scenario()]
        )
        with _pytest.raises(ValueError, match="stem"):
            ScenarioConverter.convert(scenario_set)

    def test_mixed_none_and_value_expected_rows_guarded(self) -> None:
        # [Boundary] G-b: a None-expected row in an equality group smoke-calls
        # via the emitted `if expected is not None` guard; file compiles.
        scenarios = [
            _make_scenario(name="a", inputs={"u": "x"}, expected_output=1),
            _make_scenario(name="b", inputs={"u": "y"}, expected_output=None),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios), stem="auth")
        compile(result, "<scenario_test>", "exec")
        assert "if expected is not None:" in result

    def test_real_bodies_still_compile_and_keep_traces(self) -> None:
        # [Boundary] the repair preserves the C09 @trace contract and yields
        # valid Python for the mixed single+parametrized shape.
        scenarios = [
            _make_scenario(name="a", inputs={"u": "x"}, expected_output=1),
            _make_scenario(name="b", inputs={"u": "y"}, expected_output=2),
            _make_scenario(
                name="solo", function_under_test="register", req_id="FR-2", expected_output=None
            ),
        ]
        result = ScenarioConverter.convert(_make_scenario_set(scenarios), stem="auth")
        compile(result, "<scenario_test>", "exec")
        assert "@trace(FR-1)" in result
        assert "@trace(FR-2)" in result
