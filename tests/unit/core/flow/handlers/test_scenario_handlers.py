# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for GenerateScenarioHandler and ConvertScenarioHandler."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.scenario import ConvertScenarioHandler, GenerateScenarioHandler

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus


def _make_context(tmp_path: Path, *, llm: object | None = None) -> RunContext:
    """Build a minimal RunContext for testing."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    spec_path = spec_dir / "auth_spec.md"
    spec_path.write_text(
        "# Auth\n\n"
        "## Functional Requirements\n\n| FR-1 | Login |\n\n"
        "## Non-Functional Requirements\n\nNFR-1 latency\n\n"
        "## Contract\n\ndef login(u, p): ...\n\n"
        "## Scenarios\n\n```yaml\n- name: happy_login\n```\n",
        encoding="utf-8",
    )

    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    contract_path = contracts_dir / "auth_contract.py"
    contract_path.write_text("class AuthProtocol: ...", encoding="utf-8")

    ctx = MagicMock(spec=RunContext)
    ctx.spec_path = spec_path
    ctx.project_path = tmp_path
    ctx.llm = llm
    ctx.api_contract_paths = [str(contract_path)]
    ctx.constitution = None
    ctx.project_metadata = None
    ctx.config = None

    # Mock _resolve_generation_routing needs
    ctx.llm_routing_enabled = False
    ctx.llm_router = None
    ctx.generation_config = None
    ctx.feedback = {}

    return ctx


def _make_step(action: str = "generate", target: str = "scenario") -> PipelineStep:
    """Build a minimal PipelineStep."""
    return PipelineStep(name="test_step", action=action, target=target)


# Valid scenario set response for mocking LLM
_VALID_RESPONSE = {
    "spec_path": "specs/auth_spec.md",
    "contract_path": "contracts/auth_contract.py",
    "scenarios": [
        {
            "name": "happy_login",
            "description": "Valid user",
            "function_under_test": "login",
            "req_id": "FR-1",
            "category": "happy",
            "input_summary": "valid",
            "inputs": {"u": "admin"},
            "expected_behavior": "token",
            "expected_output": {"token": "abc"},
        },
    ],
    "reasoning": "chain of thought",
}


class TestGenerateScenarioHandler:
    """Tests for GenerateScenarioHandler."""

    async def test_execute_creates_scenario_yaml(self, tmp_path: Path) -> None:
        """Handler writes YAML to scenarios/definitions/."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_RESPONSE)
        ctx = _make_context(tmp_path, llm=mock_llm)

        handler = GenerateScenarioHandler()
        step = _make_step()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.PASSED
        scenario_path = tmp_path / "scenarios" / "definitions" / "auth_scenarios.yaml"
        assert scenario_path.exists()
        assert result.output["scenario_count"] == 1

    async def test_execute_no_llm_errors(self, tmp_path: Path) -> None:
        """Returns error when llm is None."""
        ctx = _make_context(tmp_path, llm=None)

        handler = GenerateScenarioHandler()
        step = _make_step()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.ERROR
        assert "LLM adapter required" in (result.error_message or "")

    async def test_execute_reads_contract_from_context(self, tmp_path: Path) -> None:
        """Picks up api_contract_paths from context."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_RESPONSE)
        ctx = _make_context(tmp_path, llm=mock_llm)

        handler = GenerateScenarioHandler()
        await handler.execute(_make_step(), ctx)

        # Verify the LLM was called with contract content in prompt
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "AuthProtocol" in prompt

    def test_handler_registered(self) -> None:
        """(GENERATE, SCENARIO) is in registry."""
        registry = StepHandlerRegistry()
        handler = registry.get(StepAction.GENERATE, StepTarget.SCENARIO)
        assert handler is not None
        assert isinstance(handler, GenerateScenarioHandler)

    async def test_missing_spec_file(self, tmp_path: Path) -> None:
        """Handler returns StepStatus.ERROR if spec file is missing."""
        ctx = _make_context(tmp_path, llm=AsyncMock())
        ctx.spec_path.unlink()  # Remove the spec file

        handler = GenerateScenarioHandler()
        step = _make_step()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.ERROR
        assert "Spec file not found" in result.error_message


# ---------------------------------------------------------------------------
# INT-US-24 SF-02 T2 (FR-4): the handler consumes the arbiter's verdict
# feedback pop-once and threads it into the regeneration prompt.
# ---------------------------------------------------------------------------


def _feedback_step() -> PipelineStep:
    # The bundled scenario_validation.yaml step name — the key the arbiter writes.
    return PipelineStep(name="generate_scenarios", action="generate", target="scenario")


def _arbiter_feedback() -> dict:
    return {
        "from_step": "arbitrate_verdict",
        "findings": {
            "verdict": "scenario_error",
            "results": [
                {"status": "FAIL", "rule_id": "FR-1", "message": "asserts the wrong token shape"}
            ],
        },
    }


class TestGenerateScenarioFeedback:
    async def test_consumes_feedback_into_prompt_and_pops(self, tmp_path: Path, caplog) -> None:
        # [Happy] arbiter-shaped feedback → extracted "[FR-1] ..." text reaches
        # the regeneration prompt; key popped (consume-once); INFO logged.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_RESPONSE)
        ctx = _make_context(tmp_path, llm=mock_llm)
        ctx.feedback = {"generate_scenarios": _arbiter_feedback()}

        with caplog.at_level("INFO"):
            result = await GenerateScenarioHandler().execute(_feedback_step(), ctx)

        assert result.status == StepStatus.PASSED
        prompt = mock_llm.generate.call_args[0][0]
        assert "[FR-1] asserts the wrong token shape" in prompt
        assert "Prior Verdict Feedback" in prompt
        assert "generate_scenarios" not in ctx.feedback
        assert any("feedback" in r.message.lower() for r in caplog.records)

    async def test_no_feedback_byte_identical(self, tmp_path: Path) -> None:
        # [Boundary/backward-compat] no feedback → no verdict block, feedback
        # dict untouched.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_RESPONSE)
        ctx = _make_context(tmp_path, llm=mock_llm)

        result = await GenerateScenarioHandler().execute(_feedback_step(), ctx)

        assert result.status == StepStatus.PASSED
        assert "Prior Verdict Feedback" not in mock_llm.generate.call_args[0][0]
        assert ctx.feedback == {}

    async def test_unrelated_feedback_keys_survive(self, tmp_path: Path) -> None:
        # [Boundary] only the handler's own key is popped.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_RESPONSE)
        ctx = _make_context(tmp_path, llm=mock_llm)
        ctx.feedback = {
            "generate_scenarios": _arbiter_feedback(),
            "generate_code": {"findings": {"results": []}},
            "scenario_test_failures": {"total": 1, "failed": 1, "errors": 0, "failures": []},
        }

        await GenerateScenarioHandler().execute(_feedback_step(), ctx)

        assert "generate_scenarios" not in ctx.feedback
        assert "generate_code" in ctx.feedback
        assert "scenario_test_failures" in ctx.feedback

    async def test_dictator_shaped_feedback_tolerated_remarks_dropped(
        self, tmp_path: Path
    ) -> None:
        # [Boundary] G-b: HITL-reject-shaped feedback (remarks, no FAIL results)
        # is the Q2 "knowingly ignored" path — no crash, no verdict block, key
        # still consumed. If scenario steps ever gain HITL gates, this pin
        # trips instead of user remarks vanishing silently.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_RESPONSE)
        ctx = _make_context(tmp_path, llm=mock_llm)
        ctx.feedback = {
            "generate_scenarios": {
                "findings": {"hitl_verdict": "reject", "remarks": "please add boundary cases"}
            }
        }

        result = await GenerateScenarioHandler().execute(_feedback_step(), ctx)

        assert result.status == StepStatus.PASSED
        assert "Prior Verdict Feedback" not in mock_llm.generate.call_args[0][0]
        assert "generate_scenarios" not in ctx.feedback

    async def test_malformed_findings_treated_as_no_feedback(
        self, tmp_path: Path, caplog
    ) -> None:
        # [Graceful degradation] a malformed findings value must not crash the
        # regeneration — call-site guard treats it as no-feedback + WARNING.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(_VALID_RESPONSE)
        ctx = _make_context(tmp_path, llm=mock_llm)
        ctx.feedback = {"generate_scenarios": {"findings": "notadict"}}

        with caplog.at_level("WARNING"):
            result = await GenerateScenarioHandler().execute(_feedback_step(), ctx)

        assert result.status == StepStatus.PASSED
        assert "Prior Verdict Feedback" not in mock_llm.generate.call_args[0][0]
        assert any("feedback" in r.message.lower() for r in caplog.records)


class TestConvertScenarioHandler:
    """Tests for ConvertScenarioHandler."""

    async def test_execute_converts_yaml_to_pytest(self, tmp_path: Path) -> None:
        """Handler reads YAML and writes pytest."""
        # Setup: create scenario YAML
        scenarios_dir = tmp_path / "scenarios" / "definitions"
        scenarios_dir.mkdir(parents=True)

        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.default_flow_style = False
        scenario_yaml_path = scenarios_dir / "auth_scenarios.yaml"
        yaml.dump(_VALID_RESPONSE, scenario_yaml_path)

        ctx = _make_context(tmp_path)
        handler = ConvertScenarioHandler()
        step = _make_step(action="convert", target="scenario")
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.PASSED
        output_path = tmp_path / "scenarios" / "generated" / "test_auth_scenarios.py"
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "def test_" in content
        assert "@trace(FR-1)" in content

    async def test_execute_scenario_yaml_not_found(self, tmp_path: Path) -> None:
        """Returns error if YAML missing."""
        ctx = _make_context(tmp_path)
        handler = ConvertScenarioHandler()
        step = _make_step(action="convert", target="scenario")
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.ERROR
        assert "not found" in (result.error_message or "")

    def test_handler_registered(self) -> None:
        """(CONVERT, SCENARIO) is in registry."""
        registry = StepHandlerRegistry()
        handler = registry.get(StepAction.CONVERT, StepTarget.SCENARIO)
        assert handler is not None
        assert isinstance(handler, ConvertScenarioHandler)

    async def test_missing_scenario_yaml(self, tmp_path: Path) -> None:
        """Handler returns StepStatus.ERROR if scenario YAML is missing."""
        ctx = _make_context(tmp_path)
        # We don't write the YAML, so the file naturally won't exist.

        handler = ConvertScenarioHandler()
        step = _make_step("convert", "scenario")
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.ERROR
        assert "Scenario YAML not found" in result.error_message

    async def test_handler_sets_scenario_test_path_in_feedback(self, tmp_path: Path) -> None:
        """ConvertScenarioHandler must write scenario_test_path into context.feedback."""
        from ruamel.yaml import YAML

        scenarios_dir = tmp_path / "scenarios" / "definitions"
        scenarios_dir.mkdir(parents=True)
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.dump(_VALID_RESPONSE, scenarios_dir / "auth_scenarios.yaml")

        ctx = _make_context(tmp_path)
        handler = ConvertScenarioHandler()
        result = await handler.execute(_make_step("convert", "scenario"), ctx)

        assert result.status == StepStatus.PASSED
        assert "scenario_test_path" in ctx.feedback
        # For Python project (default), path must be in scenarios/generated/
        assert "scenarios" in ctx.feedback["scenario_test_path"]
        assert "generated" in ctx.feedback["scenario_test_path"]

    async def test_handler_uses_factory_output_path(self, tmp_path: Path) -> None:
        """ConvertScenarioHandler must use converter.output_path() — not a hardcoded path."""
        from ruamel.yaml import YAML

        scenarios_dir = tmp_path / "scenarios" / "definitions"
        scenarios_dir.mkdir(parents=True)
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.dump(_VALID_RESPONSE, scenarios_dir / "auth_scenarios.yaml")

        # Python project (default): output_path convention
        ctx = _make_context(tmp_path)
        handler = ConvertScenarioHandler()
        result = await handler.execute(_make_step("convert", "scenario"), ctx)

        assert result.status == StepStatus.PASSED
        expected_path = tmp_path / "scenarios" / "generated" / "test_auth_scenarios.py"
        assert expected_path.exists()
        # The result output must also report the path as a string
        assert "generated_path" in result.output
        assert "test_auth_scenarios.py" in result.output["generated_path"]
