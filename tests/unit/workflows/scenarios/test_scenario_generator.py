# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for ScenarioGenerator — static helpers and LLM integration."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from specweaver.workflows.scenarios.scenario_generator import ScenarioGenerator


class TestExtractReqIds:
    """Tests for ScenarioGenerator._extract_req_ids."""

    def test_extracts_fr_ids(self) -> None:
        text = "This covers FR-1 and FR-2 requirements."
        result = ScenarioGenerator._extract_req_ids(text)
        assert "FR-1" in result
        assert "FR-2" in result

    def test_extracts_nfr_ids(self) -> None:
        text = "NFR-1 latency must be under 200ms. NFR-3 uptime."
        result = ScenarioGenerator._extract_req_ids(text)
        assert "NFR-1" in result
        assert "NFR-3" in result

    def test_extracts_mixed_ids(self) -> None:
        text = "FR-1 is critical. NFR-2 is also needed. FR-10 edge case."
        result = ScenarioGenerator._extract_req_ids(text)
        assert set(result) == {"FR-1", "NFR-2", "FR-10"}

    def test_returns_empty_when_no_ids(self) -> None:
        text = "This spec has no requirement tags at all."
        result = ScenarioGenerator._extract_req_ids(text)
        assert result == []

    def test_deduplicates(self) -> None:
        text = "FR-1 appears twice: FR-1 again."
        result = ScenarioGenerator._extract_req_ids(text)
        assert result.count("FR-1") == 1


class TestExtractSection:
    """Tests for ScenarioGenerator._extract_section."""

    def test_extracts_contract_section(self) -> None:
        text = "# Spec\n\n## Contract\n\nSome contract content.\n\n## Scenarios\n\nMore."
        result = ScenarioGenerator._extract_section(text, "Contract")
        assert result is not None
        assert "Some contract content." in result
        assert "More." not in result

    def test_extracts_functional_requirements(self) -> None:
        text = "## Functional Requirements\n\n| FR-1 | Login |\n\n## Non-Functional Requirements\n\nNFR stuff"
        result = ScenarioGenerator._extract_section(text, "Functional Requirements")
        assert result is not None
        assert "FR-1" in result
        assert "NFR stuff" not in result

    def test_extracts_nonfunctional_requirements(self) -> None:
        text = "## Non-Functional Requirements\n\nNFR-1 latency\n\n## External Dependencies\n\nDeps"
        result = ScenarioGenerator._extract_section(text, "Non-Functional Requirements")
        assert result is not None
        assert "NFR-1" in result
        assert "Deps" not in result

    def test_extracts_scenarios_section(self) -> None:
        text = "## Scenarios\n\n```yaml\n- name: test\n```\n\n## Other\n\nIgnore"
        result = ScenarioGenerator._extract_section(text, "Scenarios")
        assert result is not None
        assert "name: test" in result
        assert "Ignore" not in result

    def test_returns_none_when_missing(self) -> None:
        text = "## Contract\n\nContent."
        result = ScenarioGenerator._extract_section(text, "Scenarios")
        assert result is None

    def test_section_at_end_of_file(self) -> None:
        text = "## Contract\n\nContent.\n\n## Scenarios\n\nFinal content."
        result = ScenarioGenerator._extract_section(text, "Scenarios")
        assert result is not None
        assert "Final content." in result

    def test_numbered_heading(self) -> None:
        """Handles ## 3. Scenarios style headers."""
        text = "## 3. Scenarios\n\nNumbered content.\n\n## 4. Other\n\nIgnore"
        result = ScenarioGenerator._extract_section(text, "Scenarios")
        assert result is not None
        assert "Numbered content." in result


class TestCleanJson:
    """Tests for ScenarioGenerator._clean_json."""

    def test_strips_json_fences(self) -> None:
        text = '```json\n{"key": "value"}\n```'
        assert ScenarioGenerator._clean_json(text) == '{"key": "value"}'

    def test_strips_plain_fences(self) -> None:
        text = '```\n{"key": "value"}\n```'
        assert ScenarioGenerator._clean_json(text) == '{"key": "value"}'

    def test_no_fences_unchanged(self) -> None:
        text = '{"key": "value"}'
        assert ScenarioGenerator._clean_json(text) == '{"key": "value"}'

    def test_strips_surrounding_whitespace(self) -> None:
        text = '  ```json\n  {"key": "value"}\n  ```  '
        result = ScenarioGenerator._clean_json(text)
        assert '"key"' in result


# ---------------------------------------------------------------------------
# Helper to build a valid ScenarioSet JSON response
# ---------------------------------------------------------------------------

_VALID_SCENARIO_SET = {
    "spec_path": "specs/auth_spec.md",
    "contract_path": "contracts/auth_contract.py",
    "scenarios": [
        {
            "name": "happy_login",
            "description": "Valid user logs in",
            "function_under_test": "login",
            "req_id": "FR-1",
            "category": "happy",
            "preconditions": ["user exists"],
            "input_summary": "valid credentials",
            "inputs": {"username": "admin", "password": "pass"},
            "expected_behavior": "returns token",
            "expected_output": {"token": "abc"},
        },
    ],
    "reasoning": "Generated for FR-1",
}


class TestGenerateScenarios:
    """Tests for ScenarioGenerator.generate_scenarios (async, LLM-mocked)."""

    @pytest.fixture()
    def _spec_content(self) -> str:
        return (
            "# Auth Spec\n\n"
            "## Functional Requirements\n\n| FR-1 | Login |\n\n"
            "## Non-Functional Requirements\n\nNFR-1 latency\n\n"
            "## Contract\n\ndef login(u, p): ...\n\n"
            "## Scenarios\n\n```yaml\n- name: happy_login\n```\n"
        )

    async def test_happy_path(self, _spec_content: str) -> None:
        """Mock LLM returns valid JSON → ScenarioSet."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_SCENARIO_SET)

        gen = ScenarioGenerator(llm=mock_llm, max_retries=3)
        result = await gen.generate_scenarios(
            spec_content=_spec_content,
            contract_content="class AuthProtocol: ...",
            req_ids=["FR-1"],
        )
        assert len(result.scenarios) == 1
        assert result.scenarios[0].name == "happy_login"
        assert result.scenarios[0].req_id == "FR-1"
        assert mock_llm.generate.call_count == 1

    async def test_retry_on_invalid_json(self, _spec_content: str) -> None:
        """Invalid JSON on first attempt triggers retry."""
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = [
            "not valid json at all",
            json.dumps(_VALID_SCENARIO_SET),
        ]

        gen = ScenarioGenerator(llm=mock_llm, max_retries=3)
        result = await gen.generate_scenarios(
            spec_content=_spec_content,
            contract_content="class AuthProtocol: ...",
            req_ids=["FR-1"],
        )
        assert len(result.scenarios) == 1
        assert mock_llm.generate.call_count == 2

    async def test_retry_on_pydantic_validation_error(self, _spec_content: str) -> None:
        """Pydantic validation failure triggers retry."""
        invalid_set = {"spec_path": "s", "contract_path": "c", "scenarios": [{"name": "x"}]}
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = [
            json.dumps(invalid_set),
            json.dumps(_VALID_SCENARIO_SET),
        ]

        gen = ScenarioGenerator(llm=mock_llm, max_retries=3)
        result = await gen.generate_scenarios(
            spec_content=_spec_content,
            contract_content="",
            req_ids=["FR-1"],
        )
        assert len(result.scenarios) == 1
        assert mock_llm.generate.call_count == 2

    async def test_exhausts_retries(self, _spec_content: str) -> None:
        """Raises ValueError after max_retries."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "not json"

        gen = ScenarioGenerator(llm=mock_llm, max_retries=2)
        with pytest.raises(ValueError, match="failed after 2 retries"):
            await gen.generate_scenarios(
                spec_content=_spec_content,
                contract_content="",
                req_ids=[],
            )
        assert mock_llm.generate.call_count == 2
