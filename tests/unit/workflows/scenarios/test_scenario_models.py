# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for scenario models — ScenarioDefinition and ScenarioSet."""

from __future__ import annotations

import pytest

from specweaver.workflows.scenarios.scenario_models import ScenarioDefinition, ScenarioSet


class TestScenarioDefinition:
    """Tests for the ScenarioDefinition Pydantic model."""

    def test_required_fields(self) -> None:
        """All four required fields must be present."""
        scenario = ScenarioDefinition(
            name="happy_login",
            description="Test happy login path",
            function_under_test="login",
            req_id="FR-1",
        )
        assert scenario.name == "happy_login"
        assert scenario.description == "Test happy login path"
        assert scenario.function_under_test == "login"
        assert scenario.req_id == "FR-1"

    def test_missing_required_field_raises(self) -> None:
        """Missing a required field must raise ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):  # pydantic ValidationError
            ScenarioDefinition(
                name="test",
                description="desc",
                # missing function_under_test and req_id
            )

    def test_defaults(self) -> None:
        """Optional fields have correct defaults."""
        scenario = ScenarioDefinition(
            name="s1",
            description="d1",
            function_under_test="func",
            req_id="FR-2",
        )
        assert scenario.category == "happy"
        assert scenario.preconditions == []
        assert scenario.input_summary == ""
        assert scenario.inputs == {}
        assert scenario.expected_behavior == ""
        assert scenario.expected_output is None

    def test_all_fields_populated(self) -> None:
        """All fields can be set explicitly."""
        scenario = ScenarioDefinition(
            name="boundary_login",
            description="Test boundary case",
            function_under_test="login",
            req_id="NFR-3",
            category="boundary",
            preconditions=["user exists", "account active"],
            input_summary="empty password",
            inputs={"username": "admin", "password": ""},
            expected_behavior="raises AuthError",
            expected_output={"error": "invalid_password"},
        )
        assert scenario.category == "boundary"
        assert scenario.preconditions == ["user exists", "account active"]
        assert scenario.inputs == {"username": "admin", "password": ""}
        assert scenario.expected_output == {"error": "invalid_password"}

    def test_req_id_accepts_fr_format(self) -> None:
        """req_id accepts FR-N format."""
        s = ScenarioDefinition(name="t", description="d", function_under_test="f", req_id="FR-1")
        assert s.req_id == "FR-1"

    def test_req_id_accepts_nfr_format(self) -> None:
        """req_id accepts NFR-N format."""
        s = ScenarioDefinition(name="t", description="d", function_under_test="f", req_id="NFR-3")
        assert s.req_id == "NFR-3"

    def test_serialization_roundtrip(self) -> None:
        """model_dump → model_validate roundtrip preserves all fields."""
        original = ScenarioDefinition(
            name="roundtrip",
            description="RT test",
            function_under_test="process",
            req_id="FR-5",
            category="error",
            preconditions=["db connected"],
            input_summary="null input",
            inputs={"data": None},
            expected_behavior="raises ValueError",
            expected_output="error",
        )
        data = original.model_dump()
        restored = ScenarioDefinition.model_validate(data)
        assert restored == original

    def test_not_collected_by_pytest(self) -> None:
        """__test__ = False prevents pytest from collecting ScenarioDefinition."""
        assert ScenarioDefinition.__test__ is False


class TestScenarioSet:
    """Tests for the ScenarioSet Pydantic model."""

    def test_required_fields(self) -> None:
        """spec_path, contract_path, and scenarios are required."""
        ss = ScenarioSet(
            spec_path="specs/auth_spec.md",
            contract_path="contracts/auth_contract.py",
            scenarios=[
                ScenarioDefinition(
                    name="s1",
                    description="d1",
                    function_under_test="login",
                    req_id="FR-1",
                ),
            ],
        )
        assert ss.spec_path == "specs/auth_spec.md"
        assert ss.contract_path == "contracts/auth_contract.py"
        assert len(ss.scenarios) == 1

    def test_empty_scenarios_valid(self) -> None:
        """An empty scenarios list is valid."""
        ss = ScenarioSet(
            spec_path="specs/x.md",
            contract_path="contracts/x.py",
            scenarios=[],
        )
        assert ss.scenarios == []

    def test_reasoning_defaults_empty(self) -> None:
        """reasoning defaults to empty string."""
        ss = ScenarioSet(spec_path="s", contract_path="c", scenarios=[])
        assert ss.reasoning == ""

    def test_not_collected_by_pytest(self) -> None:
        """__test__ = False prevents pytest from collecting ScenarioSet."""
        assert ScenarioSet.__test__ is False

    def test_serialization_roundtrip(self) -> None:
        """model_dump → model_validate roundtrip."""
        original = ScenarioSet(
            spec_path="specs/a.md",
            contract_path="contracts/a.py",
            scenarios=[
                ScenarioDefinition(
                    name="s1",
                    description="d",
                    function_under_test="f",
                    req_id="FR-1",
                ),
            ],
            reasoning="chain of thought",
        )
        data = original.model_dump()
        restored = ScenarioSet.model_validate(data)
        assert restored == original
