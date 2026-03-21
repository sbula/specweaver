# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests — CLI _helpers module.

Tests: _print_summary, _select_topology_contexts,
       _load_constitution_content, _load_standards_content.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import typer

from specweaver.validation.models import Finding, RuleResult, Severity, Status

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# _print_summary
# ---------------------------------------------------------------------------


class TestPrintSummary:
    """Test _print_summary exit-code logic."""

    def _make_result(self, status: Status) -> RuleResult:
        return RuleResult(
            rule_id="S01", rule_name="Test Rule",
            status=status, message="msg",
        )

    def test_all_pass_no_exit(self) -> None:
        """All PASS results → no exit raised."""
        from specweaver.cli._helpers import _print_summary

        results = [self._make_result(Status.PASS)]
        _print_summary(results)  # should not raise

    def test_fail_raises_exit_1(self) -> None:
        """Any FAIL result → typer.Exit(code=1)."""
        from specweaver.cli._helpers import _print_summary

        results = [
            self._make_result(Status.PASS),
            self._make_result(Status.FAIL),
        ]
        with pytest.raises(typer.Exit) as exc_info:
            _print_summary(results)
        assert exc_info.value.exit_code == 1

    def test_warn_no_exit_default(self) -> None:
        """WARN without strict → no exit raised."""
        from specweaver.cli._helpers import _print_summary

        results = [self._make_result(Status.WARN)]
        _print_summary(results)  # should not raise

    def test_warn_strict_raises_exit_1(self) -> None:
        """WARN with strict=True → typer.Exit(code=1)."""
        from specweaver.cli._helpers import _print_summary

        results = [self._make_result(Status.WARN)]
        with pytest.raises(typer.Exit) as exc_info:
            _print_summary(results, strict=True)
        assert exc_info.value.exit_code == 1

    def test_mixed_fail_and_warn(self) -> None:
        """FAIL takes priority over WARN → exit(1)."""
        from specweaver.cli._helpers import _print_summary

        results = [
            self._make_result(Status.WARN),
            self._make_result(Status.FAIL),
        ]
        with pytest.raises(typer.Exit) as exc_info:
            _print_summary(results)
        assert exc_info.value.exit_code == 1

    def test_empty_results_no_exit(self) -> None:
        """Empty results list → no exit raised."""
        from specweaver.cli._helpers import _print_summary

        _print_summary([])  # should not raise


# ---------------------------------------------------------------------------
# _select_topology_contexts
# ---------------------------------------------------------------------------


class TestSelectTopologyContexts:
    """Test _select_topology_contexts."""

    def test_none_graph_returns_none(self) -> None:
        """None graph → None result."""
        from specweaver.cli._helpers import _select_topology_contexts

        result = _select_topology_contexts(None, "some_module")
        assert result is None

    def test_unknown_selector_falls_back(self) -> None:
        """Unknown selector name → fallback to 'direct', still works."""
        from specweaver.cli._helpers import _select_topology_contexts

        mock_graph = MagicMock()
        mock_graph.nodes = {"mod_a": MagicMock()}
        # The fallback DirectNeighborSelector will call select() on the graph
        # — mock returns empty list → function returns None
        with patch(
            "specweaver.graph.selectors.DirectNeighborSelector.select",
            return_value=[],
        ):
            result = _select_topology_contexts(
                mock_graph, "mod_a", selector_name="nonexistent",
            )
        assert result is None

    def test_empty_related_returns_none(self) -> None:
        """Selector returns no related modules → None."""
        from specweaver.cli._helpers import _select_topology_contexts

        mock_graph = MagicMock()
        mock_graph.nodes = {"mod_a": MagicMock()}
        # Patch the selector to return empty
        with patch(
            "specweaver.cli._helpers._get_selector_map",
            return_value={"direct": MagicMock(return_value=MagicMock(select=MagicMock(return_value=[])))},
        ):
            from specweaver.graph.selectors import DirectNeighborSelector

            with patch.object(
                DirectNeighborSelector, "select", return_value=[],
            ):
                result = _select_topology_contexts(
                    mock_graph, "mod_a", selector_name="direct",
                )
        assert result is None


# ---------------------------------------------------------------------------
# _load_constitution_content
# ---------------------------------------------------------------------------


class TestLoadConstitutionContent:
    """Test _load_constitution_content."""

    def test_returns_content_when_found(self, tmp_path) -> None:
        """Returns constitution content when file exists."""
        from specweaver.cli._helpers import _load_constitution_content

        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("# Test Constitution\n", encoding="utf-8")

        result = _load_constitution_content(tmp_path)
        assert result is not None
        assert "Test Constitution" in result

    def test_returns_none_when_not_found(self, tmp_path) -> None:
        """Returns None when no constitution exists."""
        from specweaver.cli._helpers import _load_constitution_content

        result = _load_constitution_content(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# _load_standards_content
# ---------------------------------------------------------------------------


class TestLoadStandardsContent:
    """Test _load_standards_content."""

    @patch("specweaver.cli._helpers._core.get_db")
    def test_no_active_project_returns_none(self, mock_get_db) -> None:
        """No active project → None."""
        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = None
        mock_get_db.return_value = mock_db

        result = _load_standards_content(MagicMock())
        assert result is None

    @patch("specweaver.cli._helpers._core.get_db")
    def test_no_standards_returns_none(self, mock_get_db) -> None:
        """Active project but no standards → None."""
        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "myproject"
        mock_db.get_standards.return_value = []
        mock_get_db.return_value = mock_db

        result = _load_standards_content(MagicMock())
        assert result is None

    @patch("specweaver.cli._helpers._core.get_db")
    def test_formats_standards_correctly(self, mock_get_db) -> None:
        """Standards present → formatted string with categories."""
        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "myproject"
        mock_db.get_standards.return_value = [
            {
                "language": "python",
                "category": "naming",
                "data": json.dumps({"snake_case": "functions"}),
                "confidence": 0.95,
            },
        ]
        mock_get_db.return_value = mock_db

        result = _load_standards_content(MagicMock())
        assert result is not None
        assert "python/naming" in result
        assert "confidence=95%" in result
        assert "snake_case" in result
