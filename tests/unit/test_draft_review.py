# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for context providers, drafter, and reviewer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.context.provider import ContextProvider
from specweaver.drafting.drafter import SPEC_SECTIONS, Drafter
from specweaver.llm.models import GenerationConfig, LLMResponse
from specweaver.review.reviewer import Reviewer, ReviewFinding, ReviewResult, ReviewVerdict

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Mock context provider for testing
# ---------------------------------------------------------------------------


class MockContextProvider(ContextProvider):
    """Context provider that returns pre-defined answers."""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self._answers = answers or {}
        self._default = "Default answer"

    @property
    def name(self) -> str:
        return "mock"

    async def ask(self, question: str, *, section: str = "") -> str:
        return self._answers.get(section, self._default)


class SkipContextProvider(ContextProvider):
    """Context provider that always skips (returns empty)."""

    @property
    def name(self) -> str:
        return "skip"

    async def ask(self, question: str, *, section: str = "") -> str:
        return ""


# ---------------------------------------------------------------------------
# Context Provider tests
# ---------------------------------------------------------------------------


class TestContextProvider:
    """Test context provider interface."""

    @pytest.mark.asyncio
    async def test_mock_provider_returns_answers(self) -> None:
        provider = MockContextProvider(answers={"Purpose": "A greeting service"})
        answer = await provider.ask("What does it do?", section="Purpose")
        assert answer == "A greeting service"

    @pytest.mark.asyncio
    async def test_mock_provider_default(self) -> None:
        provider = MockContextProvider()
        answer = await provider.ask("Unknown question", section="Unknown")
        assert answer == "Default answer"

    @pytest.mark.asyncio
    async def test_skip_provider(self) -> None:
        provider = SkipContextProvider()
        answer = await provider.ask("Any question")
        assert answer == ""

    def test_provider_name(self) -> None:
        assert MockContextProvider().name == "mock"
        assert SkipContextProvider().name == "skip"


# ---------------------------------------------------------------------------
# Drafter tests
# ---------------------------------------------------------------------------


def _make_mock_llm(response_text: str = "Generated content") -> MagicMock:
    """Create a mock LLM adapter."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=LLMResponse(
        text=response_text,
        model="test-model",
    ))
    mock_llm.available.return_value = True
    return mock_llm


class TestDrafter:
    """Test the spec drafter."""

    def test_spec_sections_defined(self) -> None:
        assert len(SPEC_SECTIONS) == 5
        names = [s["name"] for s in SPEC_SECTIONS]
        assert "Purpose" in names
        assert "Contract" in names
        assert "Protocol" in names
        assert "Policy" in names
        assert "Boundaries" in names

    @pytest.mark.asyncio
    async def test_draft_creates_file(self, tmp_path: Path) -> None:
        mock_llm = _make_mock_llm()
        provider = MockContextProvider(answers={
            "Purpose": "Generates greetings",
            "Contract": "Takes name, returns string",
            "Protocol": "1. Validate input 2. Format greeting",
            "Policy": "Raises ValueError on empty name",
            "Boundaries": "No logging, no persistence",
        })
        drafter = Drafter(llm=mock_llm, context_provider=provider)

        result = await drafter.draft("greet_service", tmp_path)

        assert result.exists()
        assert result.name == "greet_service_spec.md"
        content = result.read_text(encoding="utf-8")
        assert "Greet Service" in content
        assert "## 1. Purpose" in content
        assert "## Done Definition" in content

    @pytest.mark.asyncio
    async def test_draft_with_skipped_sections(self, tmp_path: Path) -> None:
        mock_llm = _make_mock_llm()
        provider = SkipContextProvider()
        drafter = Drafter(llm=mock_llm, context_provider=provider)

        result = await drafter.draft("empty_spec", tmp_path)

        content = result.read_text(encoding="utf-8")
        assert "TODO" in content  # Skipped sections get TODO markers

    @pytest.mark.asyncio
    async def test_draft_calls_llm_for_each_section(self, tmp_path: Path) -> None:
        mock_llm = _make_mock_llm()
        provider = MockContextProvider()
        drafter = Drafter(llm=mock_llm, context_provider=provider)

        await drafter.draft("test_service", tmp_path)

        # LLM should be called once for each of the 5 sections
        assert mock_llm.generate.call_count == 5

    @pytest.mark.asyncio
    async def test_draft_creates_output_dir(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "nested" / "specs"
        mock_llm = _make_mock_llm()
        provider = MockContextProvider()
        drafter = Drafter(llm=mock_llm, context_provider=provider)

        result = await drafter.draft("nested_spec", output_dir)

        assert result.exists()
        assert output_dir.exists()

    @pytest.mark.asyncio
    async def test_draft_custom_config(self, tmp_path: Path) -> None:
        mock_llm = _make_mock_llm()
        provider = MockContextProvider()
        config = GenerationConfig(model="custom-model", temperature=0.2)
        drafter = Drafter(llm=mock_llm, context_provider=provider, config=config)

        await drafter.draft("custom", tmp_path)

        # Verify the custom config was passed to LLM
        call_args = mock_llm.generate.call_args_list[0]
        used_config = call_args[0][1]
        assert used_config.model == "custom-model"
        assert used_config.temperature == 0.2


# ---------------------------------------------------------------------------
# Reviewer tests
# ---------------------------------------------------------------------------


class TestReviewer:
    """Test the LLM reviewer."""

    @pytest.mark.asyncio
    async def test_review_spec_accepted(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "test_spec.md"
        spec_file.write_text("# Good Spec\n\n## 1. Purpose\nDoes things.", encoding="utf-8")

        mock_llm = _make_mock_llm(
            "VERDICT: ACCEPTED\n\n"
            "- Clear purpose statement\n"
            "- Good structure\n\n"
            "Overall, this spec is well-written."
        )
        reviewer = Reviewer(llm=mock_llm)

        result = await reviewer.review_spec(spec_file)

        assert result.verdict == ReviewVerdict.ACCEPTED
        assert len(result.findings) == 2
        assert result.summary  # Should have a summary

    @pytest.mark.asyncio
    async def test_review_spec_denied(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "bad_spec.md"
        spec_file.write_text("# Bad Spec", encoding="utf-8")

        mock_llm = _make_mock_llm(
            "VERDICT: DENIED\n\n"
            "- Missing Contract section\n"
            "- No error handling defined\n\n"
            "This spec is incomplete."
        )
        reviewer = Reviewer(llm=mock_llm)

        result = await reviewer.review_spec(spec_file)

        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 2

    @pytest.mark.asyncio
    async def test_review_code_against_spec(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec Content", encoding="utf-8")
        code_file = tmp_path / "code.py"
        code_file.write_text("def greet(): pass", encoding="utf-8")

        mock_llm = _make_mock_llm("VERDICT: ACCEPTED\n\nCode matches spec.")
        reviewer = Reviewer(llm=mock_llm)

        result = await reviewer.review_code(code_file, spec_file)

        assert result.verdict == ReviewVerdict.ACCEPTED

    @pytest.mark.asyncio
    async def test_review_error_handling(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM failed"))
        reviewer = Reviewer(llm=mock_llm)

        result = await reviewer.review_spec(spec_file)

        assert result.verdict == ReviewVerdict.ERROR
        assert "failed" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_review_no_verdict_defaults_denied(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec", encoding="utf-8")

        mock_llm = _make_mock_llm("Some text without any verdict marker.")
        reviewer = Reviewer(llm=mock_llm)

        result = await reviewer.review_spec(spec_file)

        # Conservative: no verdict -> denied
        assert result.verdict == ReviewVerdict.DENIED

    def test_review_result_model(self) -> None:
        result = ReviewResult(verdict=ReviewVerdict.ACCEPTED, summary="Good")
        assert result.findings == []
        assert result.raw_response == ""

    def test_review_finding_model(self) -> None:
        finding = ReviewFinding(message="Issue found")
        assert finding.category == ""
        assert finding.severity == "info"

    def test_review_verdict_enum(self) -> None:
        assert ReviewVerdict.ACCEPTED.value == "accepted"
        assert ReviewVerdict.DENIED.value == "denied"
        assert ReviewVerdict.ERROR.value == "error"


# ---------------------------------------------------------------------------
# CLI check integration tests (using test fixtures)
# ---------------------------------------------------------------------------


class TestCLICheck:
    """Test the wired sw check command."""

    def test_check_good_spec(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/good_spec.md"])

        assert result.exit_code == 0
        assert "PASS" in result.output or "PASSED" in result.output

    def test_check_bad_spec_fails(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/bad_spec_ambiguous.md"])

        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_check_nonexistent_file(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "nonexistent.md"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_check_unknown_level(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/good_spec.md", "--level", "cosmic"])

        assert result.exit_code == 1
        assert "Unknown" in result.output or "unknown" in result.output

    def test_check_code_level_stub(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/good_spec.md", "--level", "code"])

        # Code validation is now implemented — should show rule results
        assert "C01" in result.output or "Code Validation" in result.output
