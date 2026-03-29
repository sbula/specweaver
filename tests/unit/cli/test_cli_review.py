# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests — CLI review module.

Tests: _display_review_result, _execute_review dispatch logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import typer

from specweaver.review.reviewer import ReviewFinding, ReviewResult, ReviewVerdict

# ---------------------------------------------------------------------------
# _display_review_result
# ---------------------------------------------------------------------------


class TestDisplayReviewResult:
    """Test _display_review_result exit-code logic and output."""

    def test_accepted_no_exit(self) -> None:
        """ACCEPTED → no exit raised."""
        from specweaver.cli.review import _display_review_result

        result = ReviewResult(
            verdict=ReviewVerdict.ACCEPTED,
            summary="Looks good.",
            findings=[],
        )
        _display_review_result(result)  # should not raise

    def test_denied_raises_exit_1(self) -> None:
        """DENIED → typer.Exit(code=1)."""
        from specweaver.cli.review import _display_review_result

        result = ReviewResult(
            verdict=ReviewVerdict.DENIED,
            summary="Missing sections.",
            findings=[ReviewFinding(message="No Purpose section")],
        )
        with pytest.raises(typer.Exit) as exc_info:
            _display_review_result(result)
        assert exc_info.value.exit_code == 1

    def test_error_raises_exit_1(self) -> None:
        """ERROR → typer.Exit(code=1)."""
        from specweaver.cli.review import _display_review_result

        result = ReviewResult(
            verdict=ReviewVerdict.ERROR,
            summary="Review failed: API error",
        )
        with pytest.raises(typer.Exit) as exc_info:
            _display_review_result(result)
        assert exc_info.value.exit_code == 1

    def test_findings_displayed(self) -> None:
        """Findings list is printed in output."""
        from specweaver.cli.review import _display_review_result

        result = ReviewResult(
            verdict=ReviewVerdict.DENIED,
            summary="Bad spec.",
            findings=[
                ReviewFinding(message="Missing error paths"),
                ReviewFinding(message="Unclear contract"),
            ],
        )
        # Should not crash before raising exit
        with pytest.raises(typer.Exit):
            _display_review_result(result)


# ---------------------------------------------------------------------------
# _execute_review — dispatch logic
# ---------------------------------------------------------------------------


class TestExecuteReview:
    """Test _execute_review spec vs code dispatch."""

    def test_spec_review_when_no_spec_arg(self, tmp_path) -> None:
        """When spec=None, calls review_spec."""
        from specweaver.cli.review import _execute_review

        spec_file = tmp_path / "test_spec.md"
        spec_file.write_text("# Spec\n", encoding="utf-8")

        expected = ReviewResult(verdict=ReviewVerdict.ACCEPTED, summary="OK")
        mock_reviewer = MagicMock()
        mock_reviewer.review_spec = AsyncMock(return_value=expected)

        result = _execute_review(
            mock_reviewer,
            spec_file,
            spec=None,
        )
        assert result.verdict == ReviewVerdict.ACCEPTED
        mock_reviewer.review_spec.assert_called_once()

    def test_code_review_when_spec_arg(self, tmp_path) -> None:
        """When spec is set, calls review_code."""
        from specweaver.cli.review import _execute_review

        code_file = tmp_path / "module.py"
        code_file.write_text("pass\n", encoding="utf-8")
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# Spec\n", encoding="utf-8")

        expected = ReviewResult(verdict=ReviewVerdict.DENIED, summary="Bad")
        mock_reviewer = MagicMock()
        mock_reviewer.review_code = AsyncMock(return_value=expected)

        result = _execute_review(
            mock_reviewer,
            code_file,
            spec=str(spec_file),
        )
        assert result.verdict == ReviewVerdict.DENIED
        mock_reviewer.review_code.assert_called_once()

    def test_missing_spec_raises_exit(self, tmp_path) -> None:
        """Non-existent spec path → typer.Exit(code=1)."""
        from specweaver.cli.review import _execute_review

        code_file = tmp_path / "module.py"
        code_file.write_text("pass\n", encoding="utf-8")

        with pytest.raises(typer.Exit) as exc_info:
            _execute_review(
                MagicMock(),
                code_file,
                spec="nonexistent_spec.md",
            )
        assert exc_info.value.exit_code == 1

    def test_llm_error_returns_error_verdict(self, tmp_path) -> None:
        """LLM exception → ReviewResult(ERROR), not a traceback."""
        from specweaver.cli.review import _execute_review

        spec_file = tmp_path / "test_spec.md"
        spec_file.write_text("# Spec\n", encoding="utf-8")

        mock_reviewer = MagicMock()

        async def _crash(*args, **kwargs):
            msg = "API unavailable"
            raise RuntimeError(msg)

        mock_reviewer.review_spec = _crash

        result = _execute_review(mock_reviewer, spec_file, spec=None)
        assert result.verdict == ReviewVerdict.ERROR
        assert "API unavailable" in result.summary
