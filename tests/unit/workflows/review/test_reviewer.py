# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for confidence-based scoring in ReviewFinding and ReviewResult.

Covers:
- ReviewFinding.confidence field
- ReviewFinding.below_threshold field
- Reviewer._parse_response confidence extraction
- Reviewer confidence_threshold filtering
"""

from __future__ import annotations

import pytest

from specweaver.workflows.review.reviewer import (
    Reviewer,
    ReviewFinding,
    ReviewResult,
    ReviewVerdict,
)

# ---------------------------------------------------------------------------
# ReviewFinding model — confidence field
# ---------------------------------------------------------------------------


class TestReviewFindingConfidence:
    """ReviewFinding has a confidence field (0-100) and below_threshold flag."""

    def test_default_confidence_is_zero(self) -> None:
        f = ReviewFinding(message="test finding")
        assert f.confidence == 0

    def test_confidence_can_be_set(self) -> None:
        f = ReviewFinding(message="test", confidence=85)
        assert f.confidence == 85

    def test_below_threshold_default_false(self) -> None:
        f = ReviewFinding(message="test")
        assert f.below_threshold is False

    def test_below_threshold_can_be_set(self) -> None:
        f = ReviewFinding(message="test", below_threshold=True)
        assert f.below_threshold is True

    def test_confidence_round_trip_json(self) -> None:
        """Confidence survives serialization round-trip."""
        f = ReviewFinding(message="coherent", confidence=92, below_threshold=False)
        data = f.model_dump()
        assert data["confidence"] == 92
        assert data["below_threshold"] is False
        f2 = ReviewFinding.model_validate(data)
        assert f2.confidence == 92


# ---------------------------------------------------------------------------
# ReviewResult — above_threshold_findings helper
# ---------------------------------------------------------------------------


class TestReviewResultConfidenceFiltering:
    """ReviewResult provides access to findings above/below threshold."""

    def test_above_threshold_findings(self) -> None:
        """above_threshold_findings excludes below_threshold=True findings."""
        findings = [
            ReviewFinding(message="high", confidence=90, below_threshold=False),
            ReviewFinding(message="low", confidence=50, below_threshold=True),
            ReviewFinding(message="mid", confidence=80, below_threshold=False),
        ]
        result = ReviewResult(
            verdict=ReviewVerdict.DENIED,
            findings=findings,
        )
        above = result.above_threshold_findings
        assert len(above) == 2
        assert all(not f.below_threshold for f in above)

    def test_all_findings_still_accessible(self) -> None:
        """Original findings list includes everything."""
        findings = [
            ReviewFinding(message="a", confidence=90, below_threshold=False),
            ReviewFinding(message="b", confidence=30, below_threshold=True),
        ]
        result = ReviewResult(verdict=ReviewVerdict.DENIED, findings=findings)
        assert len(result.findings) == 2


# ---------------------------------------------------------------------------
# Reviewer._parse_response — confidence extraction
# ---------------------------------------------------------------------------


class TestParseResponseConfidence:
    """Reviewer._parse_response extracts confidence from LLM findings."""

    @pytest.fixture()
    def reviewer(self) -> Reviewer:
        """Create a Reviewer with a mock LLM (only _parse_response needed)."""
        return Reviewer.__new__(Reviewer)

    def test_parse_confidence_in_brackets(self, reviewer: Reviewer) -> None:
        """Confidence extracted from [confidence: N] in finding text."""
        text = """\
VERDICT: DENIED
- Missing error handling for timeout case [confidence: 92]
- Consider adding retry logic [confidence: 45]
Overall the spec needs work."""
        reviewer._confidence_threshold = 80
        result = reviewer._parse_response(text)
        assert len(result.findings) == 2
        assert result.findings[0].confidence == 92
        assert result.findings[0].below_threshold is False
        assert result.findings[1].confidence == 45
        assert result.findings[1].below_threshold is True

    def test_parse_no_confidence_defaults_to_zero(self, reviewer: Reviewer) -> None:
        """Findings without confidence get confidence=0 and below_threshold=True."""
        text = """\
VERDICT: DENIED
- Missing error handling
Summary line."""
        reviewer._confidence_threshold = 80
        result = reviewer._parse_response(text)
        assert len(result.findings) == 1
        assert result.findings[0].confidence == 0
        assert result.findings[0].below_threshold is True

    def test_parse_confidence_zero_threshold_shows_all(self, reviewer: Reviewer) -> None:
        """With threshold=0, all findings have below_threshold=False."""
        text = """\
VERDICT: ACCEPTED
- Minor style issue [confidence: 30]
Good overall."""
        reviewer._confidence_threshold = 0
        result = reviewer._parse_response(text)
        assert result.findings[0].below_threshold is False

    def test_parse_confidence_stripped_from_message(self, reviewer: Reviewer) -> None:
        """The [confidence: N] tag is stripped from the finding message."""
        text = """\
VERDICT: DENIED
- Missing error handling [confidence: 85]
Summary."""
        reviewer._confidence_threshold = 80
        result = reviewer._parse_response(text)
        assert "[confidence" not in result.findings[0].message
        assert result.findings[0].message == "Missing error handling"


# ---------------------------------------------------------------------------
# Reviewer.__init__ — confidence_threshold parameter
# ---------------------------------------------------------------------------


class TestReviewerConfidenceThreshold:
    """Reviewer accepts confidence_threshold in constructor."""

    def test_default_threshold_is_80(self) -> None:
        """Default confidence_threshold is 80."""

        # Need a mock LLM
        class MockLLM:
            pass

        r = Reviewer(llm=MockLLM(), confidence_threshold=80)  # type: ignore[arg-type]
        assert r._confidence_threshold == 80

    def test_custom_threshold(self) -> None:
        class MockLLM:
            pass

        r = Reviewer(llm=MockLLM(), confidence_threshold=50)  # type: ignore[arg-type]
        assert r._confidence_threshold == 50

    def test_no_threshold_uses_default(self) -> None:
        class MockLLM:
            pass

        r = Reviewer(llm=MockLLM())  # type: ignore[arg-type]
        assert r._confidence_threshold == 80


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestReviewerEdgeCases:
    """Edge cases for confidence parsing and threshold behavior."""

    @pytest.fixture()
    def reviewer(self) -> Reviewer:
        r = Reviewer.__new__(Reviewer)
        r._confidence_threshold = 80
        return r

    def test_confidence_equals_threshold_is_above(self, reviewer: Reviewer) -> None:
        """Confidence exactly at threshold should be ABOVE threshold."""
        text = """\
VERDICT: DENIED
- Issue found [confidence: 80]
Summary."""
        result = reviewer._parse_response(text)
        assert result.findings[0].confidence == 80
        assert result.findings[0].below_threshold is False

    def test_malformed_confidence_tag_returns_zero(self, reviewer: Reviewer) -> None:
        """[confidence: abc] returns confidence=0."""
        text = """\
VERDICT: DENIED
- Issue found [confidence: abc]
Summary."""
        result = reviewer._parse_response(text)
        assert result.findings[0].confidence == 0
        assert result.findings[0].below_threshold is True

    def test_negative_confidence_returns_zero(self, reviewer: Reviewer) -> None:
        """[confidence: -5] returns confidence=0 (regex doesn't match negative)."""
        text = """\
VERDICT: DENIED
- Issue found [confidence: -5]
Summary."""
        result = reviewer._parse_response(text)
        assert result.findings[0].confidence == 0

    def test_multiple_confidence_tags_uses_first(self, reviewer: Reviewer) -> None:
        """Only the first [confidence: N] tag is extracted."""
        text = """\
VERDICT: DENIED
- Issue [confidence: 90] is important [confidence: 50]
Summary."""
        result = reviewer._parse_response(text)
        assert result.findings[0].confidence == 90

    def test_confidence_over_100_accepted(self, reviewer: Reviewer) -> None:
        """LLM could return confidence > 100 — code accepts it."""
        text = """\
VERDICT: DENIED
- Very confident finding [confidence: 150]
Summary."""
        result = reviewer._parse_response(text)
        assert result.findings[0].confidence == 150
        assert result.findings[0].below_threshold is False

    def test_empty_response_produces_denied(self, reviewer: Reviewer) -> None:
        """Empty response defaults to DENIED with no findings."""
        result = reviewer._parse_response("")
        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 0
        assert result.summary == ""

    def test_confidence_in_summary_not_extracted(self, reviewer: Reviewer) -> None:
        """Confidence tags in non-finding lines are ignored."""
        text = """\
VERDICT: ACCEPTED
Overall good [confidence: 50] quality.
Summary line."""
        result = reviewer._parse_response(text)
        # No findings — confidence tag is in a non-finding line
        assert len(result.findings) == 0

    def test_accepted_verdict_with_findings(self, reviewer: Reviewer) -> None:
        """ACCEPTED verdict can still have findings (warnings, not blockers)."""
        text = """\
VERDICT: ACCEPTED
- Minor: consider renaming variable [confidence: 30]
- Note: add docstring [confidence: 20]
Overall the code is good."""
        result = reviewer._parse_response(text)
        assert result.verdict == ReviewVerdict.ACCEPTED
        assert len(result.findings) == 2
        # Both below threshold (50), so below_threshold is True
        assert all(f.below_threshold for f in result.findings)

    def test_no_verdict_defaults_to_denied(self, reviewer: Reviewer) -> None:
        """Response with no VERDICT line defaults to DENIED (conservative)."""
        text = """\
Some review text.
- Issue found [confidence: 80]
Conclusion."""
        result = reviewer._parse_response(text)
        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 1

    def test_mixed_confidence_threshold_filtering(self, reviewer: Reviewer) -> None:
        """Findings above and below threshold are correctly flagged."""
        text = """\
VERDICT: DENIED
- Critical bug [confidence: 90]
- Minor style [confidence: 30]
- Medium concern [confidence: 50]
Summary."""
        result = reviewer._parse_response(text)
        assert len(result.findings) == 3
        # threshold=80: 90 above, 30 and 50 below
        above = [f for f in result.findings if not f.below_threshold]
        below = [f for f in result.findings if f.below_threshold]
        assert len(above) == 1  # only 90 is >= threshold
        assert len(below) == 2  # 30 and 50 are < 80


# ---------------------------------------------------------------------------
# Project Metadata injection
# ---------------------------------------------------------------------------


class TestReviewerProjectMetadata:
    """Reviewer injects project_metadata into the PromptBuilder."""

    @pytest.mark.asyncio
    async def test_review_spec_injects_metadata(self) -> None:
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        from specweaver.infrastructure.llm.models import (
            LLMResponse,
            ProjectMetadata,
            PromptSafeConfig,
        )

        mock_llm = AsyncMock()
        # Mock LLM generation output needs to be valid Review format
        mock_llm.generate.return_value = LLMResponse(
            text="VERDICT: ACCEPTED\nSummary", model="test"
        )

        reviewer = Reviewer(llm=mock_llm)
        metadata = ProjectMetadata(
            project_name="injector_test",
            archetype="pure-logic",
            language_target="python",
            date_iso="now",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test"),
        )

        with patch("pathlib.Path.read_text", return_value="spec content"):
            await reviewer.review_spec(Path("dummy.md"), project_metadata=metadata)

        # Assert format correctly injected (prompt is in the USER message at index 1)
        prompt = mock_llm.generate.call_args[0][0][1].content
        assert "<project_metadata>" in prompt
        assert '"project_name": "injector_test"' in prompt

    @pytest.mark.asyncio
    async def test_review_code_injects_metadata(self) -> None:
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        from specweaver.infrastructure.llm.models import (
            LLMResponse,
            ProjectMetadata,
            PromptSafeConfig,
        )

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(
            text="VERDICT: ACCEPTED\nSummary", model="test"
        )

        reviewer = Reviewer(llm=mock_llm)
        metadata = ProjectMetadata(
            project_name="injector_code_test",
            archetype="script",
            language_target="bash",
            date_iso="now",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test"),
        )

        with patch("pathlib.Path.read_text", return_value="code content"):
            await reviewer.review_code(
                Path("dummy.md"), Path("dummy.py"), project_metadata=metadata
            )

        prompt = mock_llm.generate.call_args[0][0][1].content
        assert "<project_metadata>" in prompt
        assert '"project_name": "injector_code_test"' in prompt
