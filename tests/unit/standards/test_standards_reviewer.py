# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for standards/reviewer.py — HITL document review."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.standards.analyzer import CategoryResult
from specweaver.standards.reviewer import StandardsReviewer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def reviewer() -> StandardsReviewer:
    return StandardsReviewer()


def _make_result(
    category: str = "naming",
    dominant: dict | None = None,
    confidence: float = 0.85,
    sample_size: int = 10,
) -> CategoryResult:
    return CategoryResult(
        category=category,
        dominant=dominant or {"function_style": "snake_case"},
        confidence=confidence,
        sample_size=sample_size,
    )


# ---------------------------------------------------------------------------
# Accept action
# ---------------------------------------------------------------------------


class TestAcceptAction:
    """HITL accept saves results with confirmed_by='hitl'."""

    def test_accept_single_category(self, reviewer: StandardsReviewer) -> None:
        """Pressing 'a' accepts a single category."""
        results = {"root": [_make_result("naming")]}
        with patch("rich.prompt.Prompt.ask", return_value="a"):
            accepted = reviewer.review(results, existing={})
        assert len(accepted["root"]) == 1
        assert accepted["root"][0].category == "naming"

    def test_accept_all_scope(self, reviewer: StandardsReviewer) -> None:
        """Pressing 'A' accepts all remaining categories in the scope."""
        results = {
            "root": [
                _make_result("naming"),
                _make_result("docstrings", dominant={"coverage": "full"}),
                _make_result("type_hints", dominant={"style": "inline"}),
            ],
        }
        with patch("rich.prompt.Prompt.ask", return_value="A"):
            accepted = reviewer.review(results, existing={})
        assert len(accepted["root"]) == 3


# ---------------------------------------------------------------------------
# Reject action
# ---------------------------------------------------------------------------


class TestRejectAction:
    """HITL reject excludes categories from results."""

    def test_reject_single(self, reviewer: StandardsReviewer) -> None:
        """Pressing 'r' rejects a single category."""
        results = {"root": [_make_result("naming")]}
        with patch("rich.prompt.Prompt.ask", return_value="r"):
            accepted = reviewer.review(results, existing={})
        assert len(accepted["root"]) == 0

    def test_skip_scope(self, reviewer: StandardsReviewer) -> None:
        """Pressing 'S' skips (rejects) the entire scope."""
        results = {
            "backend": [
                _make_result("naming"),
                _make_result("docstrings", dominant={"coverage": "full"}),
            ],
        }
        with patch("rich.prompt.Prompt.ask", return_value="S"):
            accepted = reviewer.review(results, existing={})
        assert len(accepted["backend"]) == 0


# ---------------------------------------------------------------------------
# Edit action
# ---------------------------------------------------------------------------


class TestEditAction:
    """HITL edit allows modifying the JSON data dict."""

    def test_edit_modifies_data(self, reviewer: StandardsReviewer) -> None:
        """Pressing 'e' then entering new JSON → updated data."""
        results = {"root": [_make_result("naming")]}
        new_data = json.dumps({"function_style": "camelCase"})

        with patch("rich.prompt.Prompt.ask", side_effect=["e", new_data]):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["root"]) == 1
        assert accepted["root"][0].dominant == {"function_style": "camelCase"}

    def test_edit_invalid_json_retries(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Invalid JSON → retry prompt, then accept valid JSON."""
        results = {"root": [_make_result("naming")]}

        with patch(
            "rich.prompt.Prompt.ask",
            side_effect=["e", "not valid json", '{"style": "ok"}'],
        ):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["root"]) == 1
        assert accepted["root"][0].dominant == {"style": "ok"}


# ---------------------------------------------------------------------------
# Multi-scope combined review
# ---------------------------------------------------------------------------


class TestMultiScopeReview:
    """Combined review across multiple scopes."""

    def test_reviews_all_scopes(self, reviewer: StandardsReviewer) -> None:
        """Review processes all scopes in order."""
        results = {
            ".": [_make_result("naming")],
            "backend": [_make_result("docstrings", dominant={"coverage": "full"})],
        }
        # Accept root naming, reject backend docstrings
        with patch("rich.prompt.Prompt.ask", side_effect=["a", "r"]):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["."]) == 1
        assert len(accepted["backend"]) == 0

    def test_empty_results(self, reviewer: StandardsReviewer) -> None:
        """Empty results dict → returns empty dict."""
        with patch("rich.prompt.Prompt.ask") as mock_ask:
            accepted = reviewer.review({}, existing={})
        mock_ask.assert_not_called()
        assert accepted == {}


# ---------------------------------------------------------------------------
# Re-scan diff
# ---------------------------------------------------------------------------


class TestRescanDiff:
    """Re-scan shows diff between old and new standards."""

    def test_diff_shown_when_existing_standards(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """When existing standards differ from new, diff is shown."""
        results = {"root": [_make_result("naming", dominant={"style": "camelCase"})]}
        existing = {
            "root": [
                {
                    "category": "naming",
                    "data": json.dumps({"style": "snake_case"}),
                    "confidence": 0.9,
                    "confirmed_by": None,
                },
            ],
        }

        with patch("rich.prompt.Prompt.ask", return_value="a"):
            accepted = reviewer.review(results, existing=existing)

        assert len(accepted["root"]) == 1

    def test_no_diff_for_new_scope(self, reviewer: StandardsReviewer) -> None:
        """No existing standards for scope → no diff shown."""
        results = {"new_scope": [_make_result("naming")]}

        with patch("rich.prompt.Prompt.ask", return_value="a"):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["new_scope"]) == 1


# ---------------------------------------------------------------------------
# Already-resolved conflicts
# ---------------------------------------------------------------------------


class TestConflictHandling:
    """Scope inheritance conflicts with existing HITL decisions."""

    def test_already_confirmed_not_re_reviewed(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Categories already confirmed_by='hitl' skip re-review."""
        results = {"root": [_make_result("naming")]}
        existing = {
            "root": [
                {
                    "category": "naming",
                    "data": json.dumps({"function_style": "snake_case"}),
                    "confidence": 0.85,
                    "confirmed_by": "hitl",
                },
            ],
        }

        # If data unchanged AND already confirmed → auto-accept (no prompt)
        with patch("rich.prompt.Prompt.ask") as mock_ask:
            accepted = reviewer.review(results, existing=existing)
        # Should NOT have been asked (auto-accepted)
        mock_ask.assert_not_called()
        assert len(accepted["root"]) == 1

    def test_hitl_confirmed_but_data_changed_prompts(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """HITL-confirmed category with CHANGED data → prompts for review."""
        results = {"root": [_make_result("naming", dominant={"style": "camelCase"})]}
        existing = {
            "root": [
                {
                    "category": "naming",
                    "data": json.dumps({"function_style": "snake_case"}),
                    "confidence": 0.85,
                    "confirmed_by": "hitl",
                },
            ],
        }

        with patch("rich.prompt.Prompt.ask", return_value="a") as mock_ask:
            accepted = reviewer.review(results, existing=existing)
        # Data changed → prompt WAS asked
        mock_ask.assert_called_once()
        assert len(accepted["root"]) == 1

    def test_existing_category_not_in_results(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Existing category not in new results → no crash, no interaction."""
        results = {"root": [_make_result("naming")]}
        existing = {
            "root": [
                {
                    "category": "docstrings",
                    "data": json.dumps({"style": "google"}),
                    "confidence": 0.9,
                    "confirmed_by": "hitl",
                },
            ],
        }

        with patch("rich.prompt.Prompt.ask", return_value="a"):
            accepted = reviewer.review(results, existing=existing)
        assert len(accepted["root"]) == 1


# ---------------------------------------------------------------------------
# Additional gap tests — edge cases and contracts
# ---------------------------------------------------------------------------


class TestEditEdgeCases:
    """Additional edge cases for the edit action."""

    def test_edit_non_dict_json_retries(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Edit with non-dict JSON (list) → retry, then accept valid dict."""
        results = {"root": [_make_result("naming")]}

        with patch(
            "rich.prompt.Prompt.ask",
            side_effect=["e", "[1, 2, 3]", '{"style": "fixed"}'],
        ):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["root"]) == 1
        assert accepted["root"][0].dominant == {"style": "fixed"}


class TestAcceptAllEdgeCases:
    """Edge cases for Accept All action."""

    def test_accept_all_on_first_category(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Accept All on first category → all remaining accepted."""
        results = {
            "root": [
                _make_result("naming"),
                _make_result("docstrings", dominant={"style": "google"}),
                _make_result("imports", dominant={"style": "grouped"}),
            ],
        }

        with patch("rich.prompt.Prompt.ask", return_value="A"):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["root"]) == 3

    def test_accept_all_on_last_category(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Accept All on last category → just that one accepted (no remaining)."""
        results = {
            "root": [
                _make_result("naming"),
                _make_result("docstrings", dominant={"style": "google"}),
            ],
        }

        # Accept first, then Accept All on second (last)
        with patch("rich.prompt.Prompt.ask", side_effect=["a", "A"]):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["root"]) == 2


class TestMultiScopeFlowEdgeCases:
    """Edge cases for multi-scope review flow."""

    def test_skip_scope_then_next_scope_proceeds(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Skip scope → next scope still receives full review."""
        results = {
            "alpha": [_make_result("naming")],
            "beta": [_make_result("docstrings", dominant={"style": "google"})],
        }

        # Skip alpha, accept beta
        with patch("rich.prompt.Prompt.ask", side_effect=["S", "a"]):
            accepted = reviewer.review(results, existing={})

        assert len(accepted["alpha"]) == 0
        assert len(accepted["beta"]) == 1

    def test_scope_review_order_is_sorted(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """Scopes are reviewed in sorted alphabetical order."""
        results = {
            "zeta": [_make_result("naming")],
            "alpha": [_make_result("docstrings", dominant={"style": "google"})],
        }

        scope_order: list[str] = []
        original_show = reviewer._show_category

        def track_scope(scope, result):
            scope_order.append(scope)
            original_show(scope, result)

        reviewer._show_category = track_scope

        with patch("rich.prompt.Prompt.ask", return_value="a"):
            reviewer.review(results, existing={})

        assert scope_order == ["alpha", "zeta"]


class TestShowMethods:
    """Tests for _show_category and _show_diff rendering."""

    def test_show_category_renders_without_crash(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """_show_category renders a Rich table without crashing."""
        result = _make_result("naming", confidence=0.85)
        # Should not raise
        reviewer._show_category("root", result)

    def test_show_diff_with_json_string_data(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """_show_diff handles data stored as JSON string (not dict)."""
        old = {
            "category": "naming",
            "data": json.dumps({"style": "snake_case"}),
            "confidence": 0.9,
            "confirmed_by": None,
        }
        new = _make_result("naming", dominant={"style": "camelCase"})
        # Should not raise
        reviewer._show_diff("root", "naming", old, new)

    def test_show_diff_with_dict_data(
        self, reviewer: StandardsReviewer,
    ) -> None:
        """_show_diff handles data stored as dict directly."""
        old = {
            "category": "naming",
            "data": {"style": "snake_case"},
            "confidence": 0.9,
            "confirmed_by": None,
        }
        new = _make_result("naming", dominant={"style": "camelCase"})
        # Should not raise
        reviewer._show_diff("root", "naming", old, new)

