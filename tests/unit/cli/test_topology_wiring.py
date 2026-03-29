# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""TDD tests for CLI topology wiring: _select_topology_contexts and --selector flag."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from specweaver.cli import _get_selector_map, _select_topology_contexts


class TestSelectorMap:
    """Ensure _get_selector_map returns all expected selectors."""

    def test_contains_all_four_selectors(self) -> None:
        selector_map = _get_selector_map()
        assert "direct" in selector_map
        assert "nhop" in selector_map
        assert "constraint" in selector_map
        assert "impact" in selector_map

    def test_classes_are_correct(self) -> None:
        from specweaver.graph.selectors import (
            ConstraintOnlySelector,
            DirectNeighborSelector,
            ImpactWeightedSelector,
            NHopConstraintSelector,
        )

        selector_map = _get_selector_map()
        assert selector_map["direct"] is DirectNeighborSelector
        assert selector_map["nhop"] is NHopConstraintSelector
        assert selector_map["constraint"] is ConstraintOnlySelector
        assert selector_map["impact"] is ImpactWeightedSelector


class TestSelectTopologyContexts:
    """Tests for _select_topology_contexts helper."""

    def test_returns_none_when_no_graph(self) -> None:
        result = _select_topology_contexts(None, "greet_service")
        assert result is None

    def test_returns_none_when_no_related_modules(self) -> None:
        """Graph exists but module has no neighbours."""
        mock_graph = MagicMock()
        # DirectNeighborSelector().select() returns empty set
        with patch(
            "specweaver.graph.selectors.DirectNeighborSelector.select",
            return_value=set(),
        ):
            result = _select_topology_contexts(
                mock_graph,
                "isolated_module",
                selector_name="direct",
            )
        assert result is None

    def test_returns_contexts_when_related_found(self) -> None:
        """When selector finds related modules, returns contexts."""
        mock_graph = MagicMock()
        mock_contexts = [MagicMock(), MagicMock()]
        mock_graph.format_context_summary.return_value = mock_contexts

        with patch(
            "specweaver.graph.selectors.DirectNeighborSelector.select",
            return_value={"auth_service", "user_store"},
        ):
            result = _select_topology_contexts(
                mock_graph,
                "greet_service",
                selector_name="direct",
            )

        assert result == mock_contexts
        mock_graph.format_context_summary.assert_called_once_with(
            "greet_service",
            {"auth_service", "user_store"},
        )

    def test_unknown_selector_falls_back_to_direct(self) -> None:
        """Unknown selector name prints warning and falls back."""
        mock_graph = MagicMock()
        mock_graph.format_context_summary.return_value = [MagicMock()]

        with patch(
            "specweaver.graph.selectors.DirectNeighborSelector.select",
            return_value={"some_module"},
        ):
            result = _select_topology_contexts(
                mock_graph,
                "greet_service",
                selector_name="nonexistent",
            )

        # Should still return contexts (falls back to DirectNeighborSelector)
        assert result is not None

    def test_uses_specified_selector(self) -> None:
        """Verify that the specified selector class is instantiated."""
        mock_graph = MagicMock()
        mock_graph.format_context_summary.return_value = [MagicMock()]

        with patch(
            "specweaver.graph.selectors.NHopConstraintSelector.select",
            return_value={"related_module"},
        ) as mock_select:
            _select_topology_contexts(
                mock_graph,
                "greet_service",
                selector_name="nhop",
            )
        mock_select.assert_called_once()


class TestSelectorCLIFlag:
    """Verify --selector flag is registered on all LLM commands."""

    def test_draft_has_selector_flag(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["draft", "--help"])
        assert "--selector" in result.output

    def test_review_has_selector_flag(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["review", "--help"])
        assert "--selector" in result.output

    def test_implement_has_selector_flag(self) -> None:
        from typer.testing import CliRunner

        from specweaver.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["implement", "--help"])
        assert "--selector" in result.output
