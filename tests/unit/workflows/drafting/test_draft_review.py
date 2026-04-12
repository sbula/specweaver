# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for context providers, drafter, and reviewer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.infrastructure.llm.errors import GenerationError
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse
from specweaver.workflows.drafting.drafter import SPEC_SECTIONS, Drafter
from specweaver.workflows.review.reviewer import (
    Reviewer,
    ReviewFinding,
    ReviewResult,
    ReviewVerdict,
)
from specweaver.workspace.context.hitl_provider import HITLProvider
from specweaver.workspace.context.provider import ContextProvider

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
    mock_llm.generate = AsyncMock(
        return_value=LLMResponse(
            text=response_text,
            model="test-model",
        )
    )
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
        provider = MockContextProvider(
            answers={
                "Purpose": "Generates greetings",
                "Contract": "Takes name, returns string",
                "Protocol": "1. Validate input 2. Format greeting",
                "Policy": "Raises ValueError on empty name",
                "Boundaries": "No logging, no persistence",
            }
        )
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

        from specweaver.interfaces.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/good_spec.md"])

        assert result.exit_code == 0
        assert "PASS" in result.output or "PASSED" in result.output

    def test_check_bad_spec_fails(self) -> None:
        from typer.testing import CliRunner

        from specweaver.interfaces.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/bad_spec_ambiguous.md"])

        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_check_nonexistent_file(self) -> None:
        from typer.testing import CliRunner

        from specweaver.interfaces.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "nonexistent.md"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_check_unknown_level(self) -> None:
        from typer.testing import CliRunner

        from specweaver.interfaces.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/good_spec.md", "--level", "cosmic"])

        assert result.exit_code == 1
        assert "Unknown" in result.output or "unknown" in result.output

    def test_check_code_level_stub(self) -> None:
        from typer.testing import CliRunner

        from specweaver.interfaces.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["check", "tests/fixtures/good_spec.md", "--level", "code"])

        # Code validation is now implemented — should show rule results
        assert "C01" in result.output or "Code Validation" in result.output


# ---------------------------------------------------------------------------
# HITL Provider — Rich prompt tests
# ---------------------------------------------------------------------------


class TestHITLProvider:
    """Test the Human-in-the-Loop context provider."""

    def test_name(self) -> None:
        """Provider name should be 'hitl'."""
        provider = HITLProvider()
        assert provider.name == "hitl"

    @patch("specweaver.workspace.context.hitl_provider.Prompt.ask")
    async def test_ask_returns_stripped_input(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should return stripped user input."""
        mock_ask.return_value = "  user answer  "
        console = MagicMock()

        provider = HITLProvider(console=console)
        result = await provider.ask("What does it do?")
        assert result == "user answer"

    @patch("specweaver.workspace.context.hitl_provider.Prompt.ask")
    async def test_ask_with_section(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should display section context when provided."""
        mock_ask.return_value = "answer"
        console = MagicMock()

        provider = HITLProvider(console=console)
        result = await provider.ask(
            "Describe the purpose",
            section="Purpose",
        )

        assert result == "answer"
        calls = console.print.call_args_list
        section_printed = any("Section:" in str(c) and "Purpose" in str(c) for c in calls)
        assert section_printed

    @patch("specweaver.workspace.context.hitl_provider.Prompt.ask")
    async def test_ask_without_section(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should NOT display section context when not provided."""
        mock_ask.return_value = "answer"
        console = MagicMock()

        provider = HITLProvider(console=console)
        await provider.ask("What?")

        calls = console.print.call_args_list
        section_printed = any("Section:" in str(c) for c in calls)
        assert not section_printed

    @patch("specweaver.workspace.context.hitl_provider.Prompt.ask")
    async def test_ask_empty_input(
        self,
        mock_ask: MagicMock,
    ) -> None:
        """Should return empty string when user presses Enter."""
        mock_ask.return_value = ""
        console = MagicMock()

        provider = HITLProvider(console=console)
        result = await provider.ask("Skip this?")
        assert result == ""

    def test_default_console(self) -> None:
        """Should create a default Console if none provided."""
        provider = HITLProvider()
        assert provider._console is not None


# ---------------------------------------------------------------------------
# Drafter — behavioral tests (failure, unexpected input)
# ---------------------------------------------------------------------------


def _failing_llm(exc: Exception | None = None) -> MagicMock:
    """Create a mock LLM that raises on generate."""
    mock = MagicMock()
    mock.generate = AsyncMock(
        side_effect=exc or GenerationError("LLM exploded", provider="test"),
    )
    return mock


class TestDrafterBehavioral:
    """Behavioral tests: failure, unexpected input."""

    @pytest.mark.asyncio
    async def test_llm_error_during_section_propagates(
        self,
        tmp_path: Path,
    ) -> None:
        """Failure: LLM error during _generate_section → propagates."""
        drafter = Drafter(
            llm=_failing_llm(),
            context_provider=MockContextProvider(),
        )
        with pytest.raises(GenerationError):
            await drafter.draft("test_comp", tmp_path)

    @pytest.mark.asyncio
    async def test_name_with_special_chars(self, tmp_path: Path) -> None:
        """Unexpected input: name with special chars → file still created."""
        drafter = Drafter(
            llm=_make_mock_llm("Generated content"),
            context_provider=MockContextProvider(),
        )
        result = await drafter.draft("my special comp!", tmp_path)

        assert result.exists()
        assert result.name == "my special comp!_spec.md"

    @pytest.mark.asyncio
    async def test_empty_name(self, tmp_path: Path) -> None:
        """Boundary: empty component name → file still created."""
        drafter = Drafter(
            llm=_make_mock_llm("Generated content"),
            context_provider=MockContextProvider(),
        )
        result = await drafter.draft("", tmp_path)

        assert result.exists()
        assert result.name == "_spec.md"


# ---------------------------------------------------------------------------
# Reviewer — behavioral tests (failure, boundaries)
# ---------------------------------------------------------------------------


class TestReviewerBehavioral:
    """Behavioral tests: failure, unexpected input, boundaries."""

    @pytest.mark.asyncio
    async def test_whitespace_only_response(self, tmp_path: Path) -> None:
        """Unexpected input: LLM returns only whitespace → DENIED."""
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")

        reviewer = Reviewer(llm=_make_mock_llm("   \n\n\t  "))
        result = await reviewer.review_spec(spec)

        assert result.verdict == ReviewVerdict.DENIED

    @pytest.mark.asyncio
    async def test_empty_spec_file_still_reviews(self, tmp_path: Path) -> None:
        """Boundary: 0-byte spec → review still executes."""
        spec = tmp_path / "empty.md"
        spec.write_text("", encoding="utf-8")

        reviewer = Reviewer(llm=_make_mock_llm("VERDICT: ACCEPTED\nLooks fine."))
        result = await reviewer.review_spec(spec)

        assert result.verdict == ReviewVerdict.ACCEPTED

    @pytest.mark.asyncio
    async def test_error_verdict_preserves_message(
        self,
        tmp_path: Path,
    ) -> None:
        """Exception: error verdict includes the original exception text."""
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")

        specific_error = GenerationError("timeout after 30s", provider="gemini")
        reviewer = Reviewer(llm=_failing_llm(specific_error))
        result = await reviewer.review_spec(spec)

        assert result.verdict == ReviewVerdict.ERROR
        assert "timeout after 30s" in result.summary

    @pytest.mark.asyncio
    async def test_code_review_spec_not_found(self, tmp_path: Path) -> None:
        """Unexpected input: spec path doesn't exist → FileNotFoundError."""
        code = tmp_path / "code.py"
        code.write_text("pass", encoding="utf-8")
        spec = tmp_path / "nonexistent.md"

        reviewer = Reviewer(llm=_make_mock_llm("VERDICT: ACCEPTED"))
        with pytest.raises(FileNotFoundError):
            await reviewer.review_code(code, spec)

    @pytest.mark.asyncio
    async def test_code_review_code_not_found(self, tmp_path: Path) -> None:
        """Unexpected input: code path doesn't exist → FileNotFoundError."""
        spec = tmp_path / "spec.md"
        spec.write_text("# Spec", encoding="utf-8")
        code = tmp_path / "nonexistent.py"

        reviewer = Reviewer(llm=_make_mock_llm("VERDICT: ACCEPTED"))
        with pytest.raises(FileNotFoundError):
            await reviewer.review_code(code, spec)


# ---------------------------------------------------------------------------
# Reviewer._parse_response — edge cases
# ---------------------------------------------------------------------------


class TestReviewerParseResponse:
    """Edge cases for _parse_response verdict and findings extraction."""

    def test_multiple_findings_extracted(self) -> None:
        """Multiple '- ' lines → multiple ReviewFinding objects."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "VERDICT: DENIED\n"
            "- Missing type hints\n"
            "- No error handling\n"
            "- Docstring missing\n"
            "Overall low quality.",
        )

        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 3
        assert result.findings[0].message == "Missing type hints"
        assert result.findings[2].message == "Docstring missing"

    def test_no_findings(self) -> None:
        """Response with verdict but no '- ' lines → empty findings."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response("VERDICT: ACCEPTED\nLooks great.")

        assert result.verdict == ReviewVerdict.ACCEPTED
        assert len(result.findings) == 0
        assert result.summary == "Looks great."

    def test_verdict_on_later_line(self) -> None:
        """VERDICT keyword not on first line → still detected."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "I've reviewed the spec carefully.\nVERDICT: ACCEPTED\nAll good.",
        )

        assert result.verdict == ReviewVerdict.ACCEPTED

    def test_raw_response_preserved(self) -> None:
        """raw_response field contains the original text."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        text = "VERDICT: DENIED\n- Issue found"
        result = reviewer._parse_response(text)

        assert result.raw_response == text


# ---------------------------------------------------------------------------
# Reviewer._parse_response — robustness edge cases
# ---------------------------------------------------------------------------


class TestReviewerParseResponseRobustness:
    """Robustness tests for LLM response parsing (unpredictable LLM output)."""

    def test_completely_empty_response(self) -> None:
        """Empty string response → DENIED (conservative), no findings."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response("")
        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 0
        assert result.raw_response == ""

    def test_whitespace_only_response(self) -> None:
        """Whitespace-only → DENIED, no findings."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response("   \n\n\t  ")
        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 0

    def test_multiple_verdict_lines_uses_first(self) -> None:
        """If LLM outputs multiple VERDICT lines, first one wins."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "VERDICT: ACCEPTED\n"
            "- Everything looks good\n"
            "VERDICT: DENIED\n"  # LLM contradicts itself
            "Actually, I changed my mind.",
        )
        # Both ACCEPTED and DENIED are present in uppercase text
        # The actual code checks for both — ACCEPTED is checked first
        assert result.verdict == ReviewVerdict.ACCEPTED

    def test_verdict_case_insensitive(self) -> None:
        """verdict: accepted (lowercase) should still be detected."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response("verdict: accepted\nOK.")
        assert result.verdict == ReviewVerdict.ACCEPTED

    def test_verdict_mixed_case(self) -> None:
        """Verdict: Denied (mixed) should be detected."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response("Verdict: Denied\n- Bad spec.")
        assert result.verdict == ReviewVerdict.DENIED

    def test_findings_with_nested_dashes(self) -> None:
        """Findings line containing sub-dashes should extract full message."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "VERDICT: DENIED\n"
            "- Missing error handling - no try/except blocks\n"
            "- Function name is non-descriptive",
        )
        assert len(result.findings) == 2
        # Full content after "- " preserved, including internal dashes
        assert "no try/except blocks" in result.findings[0].message

    def test_unicode_findings(self) -> None:
        """Unicode characters in findings should be preserved."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "VERDICT: DENIED\n"
            "- Spëcification fehlt Klarheit\n"
            "- 日本語のテスト\n"
            "Zusammenfassung: Mangelhaft.",
        )
        assert len(result.findings) == 2
        assert "Spëcification" in result.findings[0].message
        assert "日本語" in result.findings[1].message

    def test_summary_is_last_non_finding_line(self) -> None:
        """Summary should be the last non-empty, non-VERDICT, non-finding line."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "VERDICT: ACCEPTED\nSome preamble text.\n- A finding\nOverall conclusion here.",
        )
        assert result.summary == "Overall conclusion here."

    def test_only_findings_no_summary(self) -> None:
        """Response with only VERDICT + findings and no summary text."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "VERDICT: DENIED\n- Issue one\n- Issue two",
        )
        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 2
        # Summary might be empty or a finding-like string

    def test_verdict_embedded_in_prose_still_detected(self) -> None:
        """VERDICT: ACCEPTED embedded in a prose paragraph still matches."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "After careful review, I believe VERDICT: ACCEPTED is appropriate.\n"
            "- Good structure\n"
            "Well done.",
        )
        assert result.verdict == ReviewVerdict.ACCEPTED

    def test_finding_with_leading_whitespace(self) -> None:
        """Finding lines with leading spaces before '- ' should still parse."""
        reviewer = Reviewer(llm=_make_mock_llm(""))
        result = reviewer._parse_response(
            "VERDICT: DENIED\n  - Indented finding\nRegular text.",
        )
        # Lines are stripped before checking for "- "
        assert len(result.findings) == 1
        assert result.findings[0].message == "Indented finding"


# ---------------------------------------------------------------------------
# Drafter — all sections skipped
# ---------------------------------------------------------------------------


class TestDrafterAllSkipped:
    """Test draft behavior when user skips every section."""

    @pytest.mark.asyncio
    async def test_all_sections_skipped_creates_placeholders(
        self,
        tmp_path: Path,
    ) -> None:
        """All 5 sections skipped → file created with TODO placeholders."""
        drafter = Drafter(
            llm=_make_mock_llm("Should not be called"),
            context_provider=SkipContextProvider(),
        )
        result = await drafter.draft("skipped_comp", tmp_path)

        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert content.count("TODO") >= 5  # one per skipped section
