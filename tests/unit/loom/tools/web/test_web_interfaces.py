# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.loom.tools.web.interfaces — role-specific web interfaces."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from specweaver.loom.tools.web.interfaces import (
    PlannerWebInterface,
    ReviewerWebInterface,
    create_web_interface,
)
from specweaver.loom.tools.web.tool import WebTool

# ===========================================================================
# Method Visibility
# ===========================================================================

_WEB_METHODS = {"web_search", "read_url"}


class TestPlannerWebVisibility:
    """PlannerWebInterface exposes web_search and read_url."""

    @pytest.mark.parametrize("method", sorted(_WEB_METHODS))
    def test_has_method(self, method: str) -> None:
        tool = WebTool(role="planner")
        iface = PlannerWebInterface(tool)
        assert hasattr(iface, method), f"Missing method: {method}"


class TestReviewerWebVisibility:
    """ReviewerWebInterface exposes web_search and read_url."""

    @pytest.mark.parametrize("method", sorted(_WEB_METHODS))
    def test_has_method(self, method: str) -> None:
        tool = WebTool(role="reviewer")
        iface = ReviewerWebInterface(tool)
        assert hasattr(iface, method), f"Missing method: {method}"


# ===========================================================================
# Functional — interfaces delegate to tool
# ===========================================================================


class TestPlannerFunctional:
    """PlannerWebInterface delegates correctly."""

    def test_web_search_delegates(self) -> None:
        """web_search returns error (no creds) but doesn't raise."""
        tool = WebTool(role="planner")
        iface = PlannerWebInterface(tool)
        result = iface.web_search("test")
        assert result.status == "error"
        assert "credentials" in result.message.lower()

    @patch("urllib.request.urlopen", side_effect=Exception("mocked"))
    def test_read_url_delegates(self, mock: MagicMock) -> None:
        tool = WebTool(role="planner")
        iface = PlannerWebInterface(tool)
        result = iface.read_url("http://example.com")
        assert result.status == "error"


class TestReviewerFunctional:
    """ReviewerWebInterface delegates correctly."""

    def test_web_search_delegates(self) -> None:
        tool = WebTool(role="reviewer")
        iface = ReviewerWebInterface(tool)
        result = iface.web_search("test")
        assert result.status == "error"
        assert "credentials" in result.message.lower()


# ===========================================================================
# Factory
# ===========================================================================


class TestFactory:
    """create_web_interface builds correct types."""

    def test_planner(self) -> None:
        iface = create_web_interface("planner")
        assert isinstance(iface, PlannerWebInterface)

    def test_reviewer(self) -> None:
        iface = create_web_interface("reviewer")
        assert isinstance(iface, ReviewerWebInterface)

    def test_unknown_role_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            create_web_interface("hacker")

    def test_with_credentials(self) -> None:
        iface = create_web_interface("planner", api_key="key", engine_id="cx1")
        assert isinstance(iface, PlannerWebInterface)
