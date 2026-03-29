# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""TDD tests for Step 9c: topology context injection into LLM modules.

Tests verify that:
1. Reviewer, Generator, Drafter accept optional topology_contexts
2. Topology contexts are included in the assembled prompt
3. Trust signals (role= attribute) render correctly
4. Modules work correctly without topology (backward compat)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.graph.topology import TopologyContext
from specweaver.llm.models import LLMResponse

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm(response_text: str = "VERDICT: ACCEPTED\n- looks good") -> MagicMock:
    """Create a mock LLM that captures the prompt sent to it."""
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=LLMResponse(text=response_text, model="test-model"),
    )
    mock.available.return_value = True
    mock.estimate_tokens = MagicMock(side_effect=lambda t: len(t) // 4)
    return mock


def _sample_topology() -> list[TopologyContext]:
    """Sample topology contexts for testing."""
    return [
        TopologyContext(
            name="auth_service",
            purpose="JWT token validation.",
            archetype="adapter",
            relationship="direct dependency",
            constraints=["stateless", "no-blocking"],
        ),
        TopologyContext(
            name="user_store",
            purpose="User CRUD operations.",
            archetype="repository",
            relationship="transitive neighbour",
            constraints=["idempotent"],
        ),
    ]


def _make_spec(
    tmp_path: Path, content: str = "# Greet Service\n\n## 1. Purpose\n\nGreets users."
) -> Path:
    spec_file = tmp_path / "greet_service_spec.md"
    spec_file.write_text(content, encoding="utf-8")
    return spec_file


def _make_code(
    tmp_path: Path, content: str = "def greet(name: str) -> str:\n    return f'Hello {name}'"
) -> Path:
    code_file = tmp_path / "greet_service.py"
    code_file.write_text(content, encoding="utf-8")
    return code_file


# ---------------------------------------------------------------------------
# Reviewer: topology injection
# ---------------------------------------------------------------------------


class TestReviewerTopologyInjection:
    """Reviewer.review_spec/review_code accept topology_contexts."""

    @pytest.mark.asyncio
    async def test_review_spec_without_topology_still_works(self, tmp_path: Path) -> None:
        """Backward compat: review_spec works without topology."""
        from specweaver.review.reviewer import Reviewer, ReviewVerdict

        spec = _make_spec(tmp_path)
        mock_llm = _make_mock_llm()
        reviewer = Reviewer(llm=mock_llm)

        result = await reviewer.review_spec(spec)

        assert result.verdict == ReviewVerdict.ACCEPTED
        mock_llm.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_review_spec_with_topology_includes_context(self, tmp_path: Path) -> None:
        """When topology is provided, prompt includes topology XML."""
        from specweaver.review.reviewer import Reviewer

        spec = _make_spec(tmp_path)
        mock_llm = _make_mock_llm()
        reviewer = Reviewer(llm=mock_llm)
        contexts = _sample_topology()

        await reviewer.review_spec(spec, topology_contexts=contexts)

        # Verify the prompt sent to LLM contains topology info
        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content  # last message = user prompt
        assert "auth_service" in prompt_text
        assert "user_store" in prompt_text
        assert "<topology>" in prompt_text

    @pytest.mark.asyncio
    async def test_review_spec_marks_spec_as_target(self, tmp_path: Path) -> None:
        """review_spec should mark the spec file as role=target."""
        from specweaver.review.reviewer import Reviewer

        spec = _make_spec(tmp_path)
        mock_llm = _make_mock_llm()
        reviewer = Reviewer(llm=mock_llm)

        await reviewer.review_spec(spec)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content
        assert 'role="target"' in prompt_text

    @pytest.mark.asyncio
    async def test_review_code_with_topology(self, tmp_path: Path) -> None:
        """review_code passes topology down to prompt."""
        from specweaver.review.reviewer import Reviewer

        spec = _make_spec(tmp_path)
        code = _make_code(tmp_path)
        mock_llm = _make_mock_llm()
        reviewer = Reviewer(llm=mock_llm)
        contexts = _sample_topology()

        await reviewer.review_code(code, spec, topology_contexts=contexts)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content
        assert "auth_service" in prompt_text
        assert "<topology>" in prompt_text

    @pytest.mark.asyncio
    async def test_review_code_trust_signals(self, tmp_path: Path) -> None:
        """review_code: spec=reference, code=target."""
        from specweaver.review.reviewer import Reviewer

        spec = _make_spec(tmp_path)
        code = _make_code(tmp_path)
        mock_llm = _make_mock_llm()
        reviewer = Reviewer(llm=mock_llm)

        await reviewer.review_code(code, spec)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content
        assert 'role="reference"' in prompt_text
        assert 'role="target"' in prompt_text


# ---------------------------------------------------------------------------
# Generator: topology injection
# ---------------------------------------------------------------------------


class TestGeneratorTopologyInjection:
    """Generator.generate_code/generate_tests accept topology_contexts."""

    @pytest.mark.asyncio
    async def test_generate_code_without_topology(self, tmp_path: Path) -> None:
        """Backward compat: generate_code works without topology."""
        from specweaver.implementation.generator import Generator

        spec = _make_spec(tmp_path)
        out = tmp_path / "src" / "greet_service.py"
        mock_llm = _make_mock_llm("def greet(name):\n    return f'Hello {name}'")
        gen = Generator(llm=mock_llm)

        result = await gen.generate_code(spec, out)

        assert result == out
        assert out.exists()

    @pytest.mark.asyncio
    async def test_generate_code_with_topology(self, tmp_path: Path) -> None:
        """When topology provided, prompt includes topology context."""
        from specweaver.implementation.generator import Generator

        spec = _make_spec(tmp_path)
        out = tmp_path / "src" / "greet_service.py"
        mock_llm = _make_mock_llm("def greet(name):\n    return f'Hello {name}'")
        gen = Generator(llm=mock_llm)
        contexts = _sample_topology()

        await gen.generate_code(spec, out, topology_contexts=contexts)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content
        assert "auth_service" in prompt_text
        assert "<topology>" in prompt_text

    @pytest.mark.asyncio
    async def test_generate_code_spec_is_reference(self, tmp_path: Path) -> None:
        """generate_code marks spec as role=reference."""
        from specweaver.implementation.generator import Generator

        spec = _make_spec(tmp_path)
        out = tmp_path / "src" / "greet_service.py"
        mock_llm = _make_mock_llm("def greet(name):\n    return f'Hello {name}'")
        gen = Generator(llm=mock_llm)

        await gen.generate_code(spec, out)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content
        assert 'role="reference"' in prompt_text

    @pytest.mark.asyncio
    async def test_generate_tests_with_topology(self, tmp_path: Path) -> None:
        """generate_tests passes topology down to prompt."""
        from specweaver.implementation.generator import Generator

        spec = _make_spec(tmp_path)
        out = tmp_path / "tests" / "test_greet_service.py"
        mock_llm = _make_mock_llm("def test_greet():\n    assert True")
        gen = Generator(llm=mock_llm)
        contexts = _sample_topology()

        await gen.generate_tests(spec, out, topology_contexts=contexts)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content
        assert "auth_service" in prompt_text

    @pytest.mark.asyncio
    async def test_generate_tests_spec_is_reference(self, tmp_path: Path) -> None:
        """generate_tests marks spec as role=reference."""
        from specweaver.implementation.generator import Generator

        spec = _make_spec(tmp_path)
        out = tmp_path / "tests" / "test_greet_service.py"
        mock_llm = _make_mock_llm("def test_greet():\n    assert True")
        gen = Generator(llm=mock_llm)

        await gen.generate_tests(spec, out)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[-1].content
        assert 'role="reference"' in prompt_text


# ---------------------------------------------------------------------------
# Drafter: topology injection
# ---------------------------------------------------------------------------


class TestDrafterTopologyInjection:
    """Drafter.draft accepts topology_contexts for relevant sections."""

    @pytest.mark.asyncio
    async def test_draft_without_topology_still_works(self, tmp_path: Path) -> None:
        """Backward compat: draft works without topology."""
        from specweaver.context.provider import ContextProvider
        from specweaver.drafting.drafter import Drafter

        class QuickProvider(ContextProvider):
            @property
            def name(self) -> str:
                return "quick"

            async def ask(self, question: str, *, section: str = "") -> str:
                return "test answer"

        mock_llm = _make_mock_llm("Generated section content")
        drafter = Drafter(llm=mock_llm, context_provider=QuickProvider())
        specs_dir = tmp_path / "specs"

        result = await drafter.draft("greet_service", specs_dir)

        assert result.exists()
        assert result.name == "greet_service_spec.md"

    @pytest.mark.asyncio
    async def test_draft_with_topology_injects_in_boundaries(self, tmp_path: Path) -> None:
        """When topology provided, Boundaries section prompt includes module context."""
        from specweaver.context.provider import ContextProvider
        from specweaver.drafting.drafter import Drafter

        class QuickProvider(ContextProvider):
            @property
            def name(self) -> str:
                return "quick"

            async def ask(self, question: str, *, section: str = "") -> str:
                return "test answer"

        mock_llm = _make_mock_llm("Generated content")
        drafter = Drafter(llm=mock_llm, context_provider=QuickProvider())
        specs_dir = tmp_path / "specs"
        contexts = _sample_topology()

        await drafter.draft("greet_service", specs_dir, topology_contexts=contexts)

        # At least one LLM call should include topology
        found_topology = False
        for call in mock_llm.generate.call_args_list:
            messages = call[0][0]
            prompt_text = messages[-1].content
            if "auth_service" in prompt_text:
                found_topology = True
                break
        assert found_topology, "Topology should be injected in at least one section prompt"

    @pytest.mark.asyncio
    async def test_draft_topology_in_contract_section(self, tmp_path: Path) -> None:
        """Topology should also be injected in Contract section (interfaces from neighbours)."""
        from specweaver.context.provider import ContextProvider
        from specweaver.drafting.drafter import Drafter

        call_order: list[str] = []

        class TrackingProvider(ContextProvider):
            @property
            def name(self) -> str:
                return "tracking"

            async def ask(self, question: str, *, section: str = "") -> str:
                call_order.append(section)
                return "test answer"

        mock_llm = _make_mock_llm("Generated content")
        drafter = Drafter(llm=mock_llm, context_provider=TrackingProvider())
        specs_dir = tmp_path / "specs"
        contexts = _sample_topology()

        await drafter.draft("greet_service", specs_dir, topology_contexts=contexts)

        # Check that topology appears in the Contract section's LLM call (index 1, 0-indexed)
        # Contract is section index 1, Boundaries is index 4
        contract_call = mock_llm.generate.call_args_list[1]  # 2nd LLM call = Contract
        contract_prompt = contract_call[0][0][-1].content
        assert "auth_service" in contract_prompt or "user_store" in contract_prompt


# ---------------------------------------------------------------------------
# Dynamic budget scaling
# ---------------------------------------------------------------------------


class TestAutoBudgetScaling:
    """PromptBuilder auto-scales topology budget based on content size."""

    def test_small_content_scales_up(self) -> None:
        """When main content is small relative to budget, topology gets more room."""
        from specweaver.graph.topology import TopologyContext
        from specweaver.llm.models import TokenBudget
        from specweaver.llm.prompt_builder import PromptBuilder

        budget = TokenBudget(limit=10000)
        builder = PromptBuilder(budget=budget)
        builder.add_instructions("Review this spec.")  # ~4 tokens
        builder.add_context("Small spec content.", "spec", priority=1)  # ~5 tokens
        builder.add_topology(
            [
                TopologyContext(
                    name="auth",
                    purpose="Auth.",
                    archetype="adapter",
                    relationship="direct",
                    constraints=[],
                ),
            ]
        )

        # Content is tiny relative to 10000 token budget
        # Auto-scaling should give topology more room (scale = 1.5)
        prompt = builder.build()
        assert prompt
        # After build, _scale should have been set to 1.5 (small content)
        assert builder._scale == 1.5

    def test_large_content_scales_down(self) -> None:
        """When content is large relative to budget, topology compressed."""
        from specweaver.graph.topology import TopologyContext
        from specweaver.llm.models import TokenBudget
        from specweaver.llm.prompt_builder import PromptBuilder

        # Tiny budget, large content
        budget = TokenBudget(limit=100)  # 100 tokens total
        builder = PromptBuilder(budget=budget)
        builder.add_instructions("x" * 400)  # ~100 tokens (>75% of 100)
        builder.add_topology(
            [
                TopologyContext(
                    name="auth",
                    purpose="Auth.",
                    archetype="adapter",
                    relationship="direct",
                    constraints=[],
                ),
            ]
        )

        prompt = builder.build()
        assert prompt
        assert builder._scale == 0.5

    def test_explicit_factor_disables_auto(self) -> None:
        """When user sets budget_scale_factor explicitly, auto-scaling off."""
        from specweaver.graph.topology import TopologyContext
        from specweaver.llm.models import TokenBudget
        from specweaver.llm.prompt_builder import PromptBuilder

        budget = TokenBudget(limit=10000)
        builder = PromptBuilder(budget=budget, budget_scale_factor=0.8)
        builder.add_instructions("Review this spec.")
        builder.add_topology(
            [
                TopologyContext(
                    name="auth",
                    purpose="Auth.",
                    archetype="adapter",
                    relationship="direct",
                    constraints=[],
                ),
            ]
        )

        builder.build()
        # Scale should stay at 0.8, not auto-computed
        assert builder._scale == 0.8

    def test_no_budget_no_scaling(self) -> None:
        """Without a budget, no scaling occurs (no error)."""
        from specweaver.llm.prompt_builder import PromptBuilder

        builder = PromptBuilder()  # No budget
        builder.add_instructions("Review this spec.")
        prompt = builder.build()
        assert "<instructions>" in prompt

    def test_no_topology_no_scaling(self) -> None:
        """Without topology blocks, auto-scaling does nothing."""
        from specweaver.llm.models import TokenBudget
        from specweaver.llm.prompt_builder import PromptBuilder

        budget = TokenBudget(limit=10000)
        builder = PromptBuilder(budget=budget)
        builder.add_instructions("Review this spec.")

        builder.build()
        # Scale should stay at default 1.0 (no topology to scale)
        assert builder._scale == 1.0
