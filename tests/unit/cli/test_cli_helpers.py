# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests — CLI _helpers module.

Tests: _print_summary, _select_topology_contexts,
       _load_constitution_content, _load_standards_content.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import typer

from specweaver.validation.models import RuleResult, Status

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
                "scope": ".",
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


# ---------------------------------------------------------------------------
# _load_standards_content — scope-aware and token cap (gap tests)
# ---------------------------------------------------------------------------


class TestLoadStandardsContentScopeAware:
    """Scope-aware loading, token cap, and format tests."""

    @patch("specweaver.cli._helpers._core.get_db")
    def test_target_path_resolves_scope(self, mock_get_db) -> None:
        """target_path → _resolve_scope identifies correct scope."""
        from pathlib import Path as _Path

        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        mock_db.list_scopes.return_value = [".", "backend/auth"]
        mock_db.get_standards.side_effect = lambda name, scope=None: [
            {
                "scope": scope or ".",
                "language": "python",
                "category": "naming",
                "data": json.dumps({"style": "snake_case"}),
                "confidence": 0.9,
            },
        ]
        mock_get_db.return_value = mock_db

        result = _load_standards_content(
            _Path("/proj"), target_path=_Path("/proj/backend/auth/login.py"),
        )
        assert result is not None
        assert "python/naming" in result

    @patch("specweaver.cli._helpers._core.get_db")
    def test_target_path_loads_scope_and_root(self, mock_get_db) -> None:
        """target_path with non-root scope → loads scope + root standards."""
        from pathlib import Path as _Path

        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        mock_db.list_scopes.return_value = [".", "backend"]

        scope_std = {
            "scope": "backend", "language": "python", "category": "naming",
            "data": json.dumps({"style": "snake_case"}), "confidence": 0.9,
        }
        root_std = {
            "scope": ".", "language": "python", "category": "docstrings",
            "data": json.dumps({"style": "google"}), "confidence": 0.85,
        }

        def get_standards_mock(name, scope=None):
            if scope == "backend":
                return [scope_std]
            if scope == ".":
                return [root_std]
            return [scope_std, root_std]

        mock_db.get_standards.side_effect = get_standards_mock
        mock_get_db.return_value = mock_db

        result = _load_standards_content(
            _Path("/proj"), target_path=_Path("/proj/backend/app.py"),
        )
        assert result is not None
        assert "naming" in result
        assert "docstrings" in result

    @patch("specweaver.cli._helpers._core.get_db")
    def test_target_path_root_scope_no_root_duplicate(self, mock_get_db) -> None:
        """target_path resolving to '.' → root standards not loaded twice."""
        from pathlib import Path as _Path

        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        mock_db.list_scopes.return_value = ["."]
        mock_db.get_standards.return_value = [
            {
                "scope": ".", "language": "python", "category": "naming",
                "data": json.dumps({"style": "snake_case"}), "confidence": 0.9,
            },
        ]
        mock_get_db.return_value = mock_db

        result = _load_standards_content(
            _Path("/proj"), target_path=_Path("/proj/main.py"),
        )
        assert result is not None
        # Should contain naming exactly once
        assert result.count("naming") == 1

    @patch("specweaver.cli._helpers._core.get_db")
    def test_token_cap_truncates_long_output(self, mock_get_db) -> None:
        """Output exceeding max_chars is truncated."""
        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        # Generate many standards to exceed limit
        mock_db.get_standards.return_value = [
            {
                "scope": ".", "language": "python", "category": f"cat_{i}",
                "data": json.dumps({"pattern": "x" * 100}), "confidence": 0.9,
            }
            for i in range(50)
        ]
        mock_get_db.return_value = mock_db

        result = _load_standards_content(MagicMock(), max_chars=200)
        assert result is not None
        # Truncation suffix is "\n[... truncated]" (17 chars), slicing at max-15
        # gives max_chars + 2 — verify it's close and truncated
        assert len(result) < 250
        assert "[... truncated]" in result

    @patch("specweaver.cli._helpers._core.get_db")
    def test_token_cap_untouched_below_limit(self, mock_get_db) -> None:
        """Output below max_chars is NOT truncated."""
        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        mock_db.get_standards.return_value = [
            {
                "scope": ".", "language": "python", "category": "naming",
                "data": json.dumps({"style": "snake_case"}), "confidence": 0.9,
            },
        ]
        mock_get_db.return_value = mock_db

        result = _load_standards_content(MagicMock(), max_chars=5000)
        assert result is not None
        assert "[... truncated]" not in result

    @patch("specweaver.cli._helpers._core.get_db")
    def test_token_cap_scope_specific_prioritized(self, mock_get_db) -> None:
        """Scope-specific standards appear before root in output."""
        from pathlib import Path as _Path

        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        mock_db.list_scopes.return_value = [".", "backend"]

        scope_std = {
            "scope": "backend", "language": "python", "category": "naming",
            "data": json.dumps({"scope_specific": "yes"}), "confidence": 0.9,
        }
        root_std = {
            "scope": ".", "language": "python", "category": "docstrings",
            "data": json.dumps({"root_standard": "yes"}), "confidence": 0.85,
        }

        def get_standards_mock(name, scope=None):
            if scope == "backend":
                return [scope_std]
            if scope == ".":
                return [root_std]
            return []

        mock_db.get_standards.side_effect = get_standards_mock
        mock_get_db.return_value = mock_db

        result = _load_standards_content(
            _Path("/proj"), target_path=_Path("/proj/backend/app.py"),
        )
        assert result is not None
        # Scope-specific appears before root
        scope_idx = result.index("scope_specific")
        root_idx = result.index("root_standard")
        assert scope_idx < root_idx

    @patch("specweaver.cli._helpers._core.get_db")
    def test_target_path_none_backward_compatible(self, mock_get_db) -> None:
        """target_path=None → all standards loaded (backward compat)."""
        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        mock_db.get_standards.return_value = [
            {
                "scope": ".", "language": "python", "category": "naming",
                "data": json.dumps({"style": "snake_case"}), "confidence": 0.9,
            },
        ]
        mock_get_db.return_value = mock_db

        # target_path=None by default
        result = _load_standards_content(MagicMock())
        assert result is not None
        assert "naming" in result

    @patch("specweaver.cli._helpers._core.get_db")
    def test_format_includes_scope_prefix(self, mock_get_db) -> None:
        """Output format includes [scope/language/category] prefix."""
        from specweaver.cli._helpers import _load_standards_content

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        mock_db.get_standards.return_value = [
            {
                "scope": "backend", "language": "python", "category": "naming",
                "data": json.dumps({"style": "snake_case"}), "confidence": 0.9,
            },
        ]
        mock_get_db.return_value = mock_db

        result = _load_standards_content(MagicMock())
        assert result is not None
        assert "[backend/python/naming]" in result

