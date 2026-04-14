# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Scenario models — structured scenario definitions for independent verification.

These models define the machine-readable scenario artifacts that bridge
spec validation and scenario-based testing (Feature 3.28).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScenarioDefinition(BaseModel):
    """A structured test scenario derived from spec + API contract.

    Standalone model — does NOT subclass TestExpectation to avoid
    coupling the scenario pipeline to the planning module.

    Attributes:
        name: Unique scenario identifier.
        description: What this scenario verifies.
        function_under_test: Target function/method name.
        req_id: Requirement ID from the spec (e.g., "FR-1", "NFR-3").
        category: One of "happy", "error", "boundary".
        preconditions: Setup state descriptions.
        input_summary: Human-readable input description.
        inputs: Concrete input values for parametrize.
        expected_behavior: Human-readable expected outcome.
        expected_output: Concrete expected value for assertion.
    """

    __test__ = False  # Prevent pytest collection

    name: str
    description: str
    function_under_test: str
    req_id: str
    category: str = "happy"
    preconditions: list[str] = Field(default_factory=list)
    input_summary: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str = ""
    expected_output: Any = None


class ScenarioSet(BaseModel):
    """Collection of scenarios generated from a single spec.

    Attributes:
        spec_path: Path to the source spec.
        contract_path: Path to the API contract used.
        scenarios: List of generated scenario definitions.
        reasoning: LLM chain-of-thought (stored, not exposed).
    """

    __test__ = False

    spec_path: str
    contract_path: str
    scenarios: list[ScenarioDefinition]
    reasoning: str = ""
