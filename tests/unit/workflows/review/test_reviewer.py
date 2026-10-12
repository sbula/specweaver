# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Reviewer._parse_response: verdict, findings and summary from the model's text."""

from __future__ import annotations

import pytest

from specweaver.workflows.review.reviewer import (
    Reviewer,
    ReviewResult,
    ReviewVerdict,
)


@pytest.fixture()
def reviewer() -> Reviewer:
    return Reviewer.__new__(Reviewer)


class TestParseResponse:
    def test_findings_and_summary(self, reviewer: Reviewer) -> None:
        text = """\
VERDICT: DENIED
- Missing error handling for timeout case
- Consider adding retry logic
Overall the spec needs work."""
        result = reviewer._parse_response(text)
        assert result.verdict == ReviewVerdict.DENIED
        assert [f.message for f in result.findings] == [
            "Missing error handling for timeout case",
            "Consider adding retry logic",
        ]
        assert result.summary == "Overall the spec needs work."

    def test_empty_response_produces_denied(self, reviewer: Reviewer) -> None:
        result = reviewer._parse_response("")
        assert result.verdict == ReviewVerdict.DENIED
        assert result.findings == []
        assert result.summary == ""

    def test_accepted_verdict_with_findings(self, reviewer: Reviewer) -> None:
        """ACCEPTED can still carry findings (warnings, not blockers)."""
        text = "VERDICT: ACCEPTED\n- Minor: rename a variable\n- Note: add a docstring\nGood."
        result = reviewer._parse_response(text)
        assert result.verdict == ReviewVerdict.ACCEPTED
        assert len(result.findings) == 2

    def test_no_verdict_defaults_to_denied(self, reviewer: Reviewer) -> None:
        result = reviewer._parse_response("Some review text.\n- Issue found\nConclusion.")
        assert result.verdict == ReviewVerdict.DENIED
        assert len(result.findings) == 1

    def test_the_result_round_trips_json(self) -> None:
        result = ReviewResult(verdict=ReviewVerdict.DENIED, summary="s")
        assert ReviewResult.model_validate_json(result.model_dump_json()) == result


# ---------------------------------------------------------------------------
# Project Metadata injection
# ---------------------------------------------------------------------------
