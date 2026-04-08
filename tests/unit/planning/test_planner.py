# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Planner — LLM plan generation with reflection retry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from specweaver.planning.models import PlanArtifact
from specweaver.planning.planner import Planner

# ---------------------------------------------------------------------------
# Fake LLM adapter
# ---------------------------------------------------------------------------


@dataclass
class _FakeResponse:
    """Minimal response matching LLMAdapter's return type."""

    text: str


class FakeLLM:
    """Fake LLM adapter that returns pre-configured responses."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.messages_log: list[Any] = []

    async def generate(self, messages: Any, config: Any = None) -> _FakeResponse:
        self.messages_log.append(messages)
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return _FakeResponse(text=self._responses[idx])


# ---------------------------------------------------------------------------
# Sample plan JSON
# ---------------------------------------------------------------------------


def _valid_plan_json(
    *,
    spec_path: str = "specs/login_spec.md",
    spec_name: str = "Login",
    confidence: int = 80,
) -> str:
    return json.dumps(
        {
            "spec_path": spec_path,
            "spec_name": spec_name,
            "spec_hash": "ignored",  # Planner overwrites this
            "timestamp": "2026-03-22T10:00:00Z",
            "file_layout": [
                {"path": "src/login.py", "action": "create", "purpose": "Login handler"},
            ],
            "architecture": {
                "module_layout": "flat",
                "dependency_direction": "downward",
                "archetype": "adapter",
            },
            "reasoning": "Simple adapter pattern.",
            "confidence": confidence,
        }
    )


# ---------------------------------------------------------------------------
# Test: successful generation
# ---------------------------------------------------------------------------


class TestPlannerSuccess:
    """Planner successfully generates a plan on first attempt."""

    @pytest.mark.asyncio()
    async def test_generates_valid_plan(self) -> None:
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=3)

        plan = await planner.generate_plan(
            spec_content="# Login Spec\n\nHandle login.",
            spec_path="specs/login_spec.md",
            spec_name="Login",
        )

        assert isinstance(plan, PlanArtifact)
        assert plan.spec_path == "specs/login_spec.md"
        assert plan.spec_name == "Login"
        assert len(plan.file_layout) == 1
        assert plan.confidence == 80

    @pytest.mark.asyncio()
    async def test_overwrites_hash(self) -> None:
        """Planner always recomputes spec_hash from actual content."""
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)

        plan = await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
        )

        # Hash should be SHA-256 of "# Test", not "ignored"
        assert plan.spec_hash != "ignored"
        assert len(plan.spec_hash) == 64  # SHA-256 hex length

    @pytest.mark.asyncio()
    async def test_strips_markdown_fences(self) -> None:
        """Planner strips ```json fences from LLM response."""
        json_str = _valid_plan_json()
        wrapped = f"```json\n{json_str}\n```"
        llm = FakeLLM([wrapped])
        planner = Planner(llm, max_retries=1)

        plan = await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
        )
        assert isinstance(plan, PlanArtifact)


# ---------------------------------------------------------------------------
# Test: reflection retry
# ---------------------------------------------------------------------------


class TestPlannerRetry:
    """Planner retries when LLM returns invalid JSON."""

    @pytest.mark.asyncio()
    async def test_retries_on_invalid_json(self) -> None:
        """First response is garbage, second is valid → succeeds."""
        llm = FakeLLM(
            [
                "This is not JSON at all",
                _valid_plan_json(),
            ]
        )
        planner = Planner(llm, max_retries=3)

        plan = await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
        )
        assert isinstance(plan, PlanArtifact)
        # Should have been called twice
        assert llm._call_count == 2

    @pytest.mark.asyncio()
    async def test_retry_injects_error_message(self) -> None:
        """On failure, retry prompt includes the error message."""
        llm = FakeLLM(
            [
                "not json",
                _valid_plan_json(),
            ]
        )
        planner = Planner(llm, max_retries=3)

        await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
        )

        # Second call should have more messages (including retry prompt)
        assert len(llm.messages_log) == 2
        second_call_msgs = llm.messages_log[1]
        # Should have: system + user + model(bad) + user(retry)
        assert len(second_call_msgs) >= 4

    @pytest.mark.asyncio()
    async def test_all_retries_fail_raises(self) -> None:
        """All retries produce invalid JSON → ValueError."""
        llm = FakeLLM(
            [
                "bad 1",
                "bad 2",
                "bad 3",
            ]
        )
        planner = Planner(llm, max_retries=3)

        with pytest.raises(ValueError, match="failed after 3 attempts"):
            await planner.generate_plan(
                spec_content="# Test",
                spec_path="test.md",
                spec_name="Test",
            )


# ---------------------------------------------------------------------------
# Test: extra context
# ---------------------------------------------------------------------------


class TestPlannerContext:
    """Planner passes constitution and standards to prompt."""

    @pytest.mark.asyncio()
    async def test_constitution_injected(self) -> None:
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)

        await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
            constitution="No external APIs",
        )

        # The user prompt in the first call should contain constitution
        first_call_msgs = llm.messages_log[0]
        user_msg = first_call_msgs[-1]  # Last message is user prompt
        assert "No external APIs" in user_msg.content

    @pytest.mark.asyncio()
    async def test_standards_injected(self) -> None:
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)

        await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
            standards="PEP 8, type hints required",
        )

        first_call_msgs = llm.messages_log[0]
        user_msg = first_call_msgs[-1]
        assert "PEP 8" in user_msg.content

    @pytest.mark.asyncio()
    async def test_expected_signatures_in_prompt(self) -> None:
        """The LLM must be explicitly told to generate expected_signatures."""
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)

        await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
        )

        first_call_msgs = llm.messages_log[0]
        user_msg = first_call_msgs[-1]
        assert "expected_signatures" in user_msg.content
        assert "MethodSignature" in user_msg.content


# ---------------------------------------------------------------------------
# Test: _clean_json edge cases
# ---------------------------------------------------------------------------


class TestCleanJson:
    """Unit tests for Planner._clean_json static method."""

    def test_strips_plain_fences(self) -> None:
        """Plain ``` fences (no language tag) are stripped."""
        raw = '```\n{"key": "value"}\n```'
        assert Planner._clean_json(raw) == '{"key": "value"}'

    def test_clean_json_no_fences(self) -> None:
        """Clean JSON without fences passes through unchanged."""
        raw = '{"key": "value"}'
        assert Planner._clean_json(raw) == '{"key": "value"}'


# ---------------------------------------------------------------------------
# Test: edge cases in generate_plan
# ---------------------------------------------------------------------------


class TestPlannerEdgeCases:
    """Edge cases for generate_plan."""

    @pytest.mark.asyncio()
    async def test_empty_spec_content(self) -> None:
        """Empty spec content should still work (hash computed from empty string)."""
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)

        plan = await planner.generate_plan(
            spec_content="",
            spec_path="empty.md",
            spec_name="Empty",
        )
        assert isinstance(plan, PlanArtifact)
        assert len(plan.spec_hash) == 64  # SHA-256 of empty string

    @pytest.mark.asyncio()
    async def test_fills_missing_timestamp(self) -> None:
        """When LLM omits timestamp, planner fills it with now()."""
        # Build JSON without timestamp
        plan_data = {
            "spec_path": "t.md",
            "spec_name": "T",
            "spec_hash": "x",
            "file_layout": [
                {"path": "f.py", "action": "create", "purpose": "p"},
            ],
            "timestamp": "",  # empty → planner should fill
            "architecture": {
                "module_layout": "flat",
                "dependency_direction": "downward",
                "archetype": "adapter",
            },
            "reasoning": "ok",
            "confidence": 70,
        }
        llm = FakeLLM([json.dumps(plan_data)])
        planner = Planner(llm, max_retries=1)

        plan = await planner.generate_plan(
            spec_content="# Test",
            spec_path="t.md",
            spec_name="T",
        )
        # Timestamp should have been filled (non-empty)
        assert plan.timestamp
        assert "T" in plan.timestamp  # ISO format has 'T'

    @pytest.mark.asyncio()
    async def test_valid_json_invalid_pydantic_retries(self) -> None:
        """Valid JSON that fails Pydantic validation triggers a retry."""
        # Missing required 'file_layout' field
        bad_json = json.dumps({"spec_path": "t.md", "confidence": 50})
        llm = FakeLLM([bad_json, _valid_plan_json()])
        planner = Planner(llm, max_retries=3)

        plan = await planner.generate_plan(
            spec_content="# Test",
            spec_path="test.md",
            spec_name="Test",
        )
        assert isinstance(plan, PlanArtifact)
        assert llm._call_count == 2  # first failed Pydantic, second succeeded

    @pytest.mark.asyncio()
    async def test_max_retries_one_exhausted(self) -> None:
        """max_retries=1 means only one attempt — no retries on failure."""
        llm = FakeLLM(["not json"])
        planner = Planner(llm, max_retries=1)

        with pytest.raises(ValueError, match="failed after 1 attempts"):
            await planner.generate_plan(
                spec_content="# Test",
                spec_path="test.md",
                spec_name="Test",
            )
        assert llm._call_count == 1


# ---------------------------------------------------------------------------
# Test: Stitch Integration
# ---------------------------------------------------------------------------


class TestPlannerStitchIntegration:
    """Tests for Planner generating Stitch mockups."""

    @pytest.mark.asyncio()
    async def test_stitch_mode_off_does_not_extract(self, monkeypatch) -> None:
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)
        mock_extract_called = False

        def mock_extract(spec):
            nonlocal mock_extract_called
            mock_extract_called = True
            return None

        import specweaver.planning.ui_extractor

        monkeypatch.setattr(
            specweaver.planning.ui_extractor, "extract_ui_requirements", mock_extract, raising=False
        )

        plan = await planner.generate_plan(
            spec_content="## Protocol\n\nUI dashboard",
            spec_path="test.md",
            spec_name="Test",
            stitch_mode="off",
        )
        assert mock_extract_called is False
        assert not plan.mockups

    @pytest.mark.asyncio()
    async def test_stitch_mode_auto_no_ui_found(self, monkeypatch) -> None:
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)
        mock_stitch_called = False

        class MockStitchClient:
            def __init__(self, api_key):
                pass

            def generate_mockup(self, desc):
                nonlocal mock_stitch_called
                mock_stitch_called = True
                return []

        import specweaver.planning.planner

        monkeypatch.setattr(
            specweaver.planning.planner, "StitchClient", MockStitchClient, raising=False
        )

        # Content has no UI keywords
        plan = await planner.generate_plan(
            spec_content="## Protocol\n\nBackend stuff",
            spec_path="test.md",
            spec_name="Test",
            stitch_mode="auto",
        )
        assert mock_stitch_called is False
        assert not plan.mockups

    @pytest.mark.asyncio()
    async def test_stitch_returns_empty_mockups(self, monkeypatch) -> None:
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)

        class MockMockupResult:
            def __init__(self):
                self.references = []

        class MockStitchClient:
            def __init__(self, api_key):
                pass

            def generate_mockup(self, desc):
                return MockMockupResult()

        import specweaver.planning.planner

        monkeypatch.setattr(
            specweaver.planning.planner, "StitchClient", MockStitchClient, raising=False
        )

        plan = await planner.generate_plan(
            spec_content="## Protocol\n\nUI dashboard",
            spec_path="test.md",
            spec_name="Test",
            stitch_mode="auto",
        )
        assert not plan.mockups

    @pytest.mark.asyncio()
    async def test_stitch_mode_prompt_behaves_like_auto(self) -> None:
        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm, max_retries=1)

        plan = await planner.generate_plan(
            spec_content="## Protocol\n\nUI dashboard",
            spec_path="test.md",
            spec_name="Test",
            stitch_mode="prompt",
            stitch_api_key="fake-key",
        )
        assert plan.mockups
        assert len(plan.mockups) == 1
        assert "placeholder" in plan.mockups[0].preview_url


# ---------------------------------------------------------------------------
# Project Metadata injection
# ---------------------------------------------------------------------------


class TestPlannerProjectMetadata:
    """Planner injects project_metadata into the PromptBuilder."""

    @pytest.mark.asyncio()
    async def test_generate_plan_injects_metadata(self) -> None:
        from specweaver.llm.models import ProjectMetadata, PromptSafeConfig

        llm = FakeLLM([_valid_plan_json()])
        planner = Planner(llm=llm)
        metadata = ProjectMetadata(
            project_name="plan_test_meta",
            archetype="pure-logic",
            language_target="python",
            date_iso="now",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test"),
        )

        await planner.generate_plan(
            spec_content="# Test Spec",
            spec_path="test.md",
            spec_name="Test",
            project_metadata=metadata,
        )

        # llm.messages_log[0] is the first generate call's messages list
        # message 1 is the USER message containing the prompt
        user_prompt = llm.messages_log[0][1].content
        assert "<project_metadata>" in user_prompt
        assert '"project_name": "plan_test_meta"' in user_prompt
