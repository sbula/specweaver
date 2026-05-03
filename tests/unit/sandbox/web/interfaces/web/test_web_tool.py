# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.core.loom.tools.web.tool — WebTool + _strip_html."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.loom.tools.web.tool import (
    ROLE_INTENTS,
    TOOL_TIMEOUT_SECONDS,
    WebTool,
    WebToolResult,
    _strip_html,
)

# ===========================================================================
# WebToolResult
# ===========================================================================


class TestWebToolResult:
    """WebToolResult data model."""

    def test_success_result(self) -> None:
        r = WebToolResult(status="success", data={"url": "http://ex.com"})
        assert r.status == "success"
        assert r.data["url"] == "http://ex.com"

    def test_error_result(self) -> None:
        r = WebToolResult(status="error", message="fail")
        assert r.status == "error"
        assert r.message == "fail"
        assert r.data is None

    def test_frozen(self) -> None:
        r = WebToolResult(status="success")
        with pytest.raises(AttributeError):
            r.status = "error"  # type: ignore[misc]


# ===========================================================================
# Role-Intent Mapping
# ===========================================================================


class TestRoleIntents:
    """Verify all roles have web_search + read_url."""

    @pytest.mark.parametrize("role", ["planner", "reviewer", "implementer", "drafter"])
    def test_role_has_both_intents(self, role: str) -> None:
        assert ROLE_INTENTS[role] == frozenset({"web_search", "read_url"})


# ===========================================================================
# Constructor
# ===========================================================================


class TestWebToolConstructor:
    """Constructor validation."""

    def test_valid_role(self) -> None:
        tool = WebTool(role="planner")
        assert tool.role == "planner"

    def test_unknown_role_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            WebTool(role="hacker")

    def test_web_enabled_with_credentials(self) -> None:
        tool = WebTool(role="planner", api_key="key", engine_id="cx1")
        assert tool.web_enabled is True

    def test_web_disabled_without_key(self) -> None:
        tool = WebTool(role="planner", api_key="", engine_id="cx1")
        assert tool.web_enabled is False

    def test_web_disabled_without_engine_id(self) -> None:
        tool = WebTool(role="planner", api_key="key", engine_id="")
        assert tool.web_enabled is False


# ===========================================================================
# web_search
# ===========================================================================


class TestWebSearch:
    """web_search intent tests."""

    def test_no_credentials_returns_error(self) -> None:
        tool = WebTool(role="planner")
        result = tool.web_search("test query")
        assert result.status == "error"
        assert "credentials" in result.message.lower()

    @patch("urllib.request.urlopen")
    def test_successful_search(self, mock_urlopen: MagicMock) -> None:
        import json

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "items": [
                    {"title": "Result 1", "snippet": "Snippet 1", "link": "http://example.com/1"},
                    {"title": "Result 2", "snippet": "Snippet 2", "link": "http://example.com/2"},
                ]
            }
        ).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        tool = WebTool(role="planner", api_key="key", engine_id="cx1")
        result = tool.web_search("python docs")
        assert result.status == "success"
        assert len(result.data) == 2
        assert result.data[0]["title"] == "Result 1"
        assert result.data[0]["url"] == "http://example.com/1"

    @patch("urllib.request.urlopen")
    def test_max_results_respected(self, mock_urlopen: MagicMock) -> None:
        import json

        items = [
            {"title": f"R{i}", "snippet": f"S{i}", "link": f"http://ex.com/{i}"} for i in range(10)
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"items": items}).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        tool = WebTool(role="planner", api_key="key", engine_id="cx1")
        result = tool.web_search("test", max_results=3)
        assert len(result.data) <= 3

    @patch("urllib.request.urlopen")
    def test_empty_results(self, mock_urlopen: MagicMock) -> None:
        import json

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({}).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        tool = WebTool(role="planner", api_key="key", engine_id="cx1")
        result = tool.web_search("nonexistent query xyz")
        assert result.status == "success"
        assert result.data == []

    @patch("urllib.request.urlopen", side_effect=Exception("Network error"))
    def test_network_error_returns_error(self, mock_urlopen: MagicMock) -> None:
        tool = WebTool(role="planner", api_key="key", engine_id="cx1")
        result = tool.web_search("test")
        assert result.status == "error"
        assert "Network error" in result.message


# ===========================================================================
# read_url
# ===========================================================================


class TestReadUrl:
    """read_url intent tests."""

    @patch("urllib.request.urlopen")
    def test_successful_read(self, mock_urlopen: MagicMock) -> None:
        html = "<html><body><p>Hello world</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.read.return_value = html.encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        tool = WebTool(role="planner")
        result = tool.read_url("http://example.com")
        assert result.status == "success"
        assert "Hello world" in result.data["content"]
        assert result.data["url"] == "http://example.com"

    @patch("urllib.request.urlopen")
    def test_truncation(self, mock_urlopen: MagicMock) -> None:
        html = "<p>" + "x" * 500 + "</p>"
        mock_resp = MagicMock()
        mock_resp.read.return_value = html.encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        tool = WebTool(role="planner")
        result = tool.read_url("http://example.com", max_chars=100)
        assert result.status == "success"
        assert len(result.data["content"]) <= 100
        assert result.data["truncated"] is True
        assert "truncated" in result.data["warning"].lower()

    @patch("urllib.request.urlopen", side_effect=Exception("404 Not Found"))
    def test_network_error(self, mock_urlopen: MagicMock) -> None:
        tool = WebTool(role="planner")
        result = tool.read_url("http://example.com/missing")
        assert result.status == "error"
        assert "404" in result.message


# ===========================================================================
# _strip_html
# ===========================================================================


class TestStripHtml:
    """Tests for the _strip_html helper (regex fallback path)."""

    def test_strips_tags(self) -> None:
        html = "<p>Hello <strong>world</strong></p>"
        text = _strip_html(html)
        assert "Hello" in text
        assert "world" in text
        assert "<p>" not in text
        assert "<strong>" not in text

    def test_strips_script(self) -> None:
        html = "<script>alert('xss')</script><p>Content</p>"
        text = _strip_html(html)
        assert "alert" not in text
        assert "Content" in text

    def test_strips_style(self) -> None:
        html = "<style>body { color: red; }</style><p>Visible</p>"
        text = _strip_html(html)
        assert "color" not in text
        assert "Visible" in text

    def test_empty_input(self) -> None:
        assert _strip_html("") == ""

    def test_plain_text_passthrough(self) -> None:
        text = "No HTML tags here"
        assert _strip_html(text) == text

    def test_collapses_whitespace(self) -> None:
        html = "<p>  lots   of   spaces  </p>"
        text = _strip_html(html)
        # Should not have consecutive spaces
        assert "  " not in text or text.strip() == text


# ===========================================================================
# Role gating
# ===========================================================================


class TestRoleGating:
    """All roles currently allow all web intents — verify no exceptions."""

    @pytest.mark.parametrize("role", ["planner", "reviewer", "implementer", "drafter"])
    def test_web_search_allowed(self, role: str) -> None:
        tool = WebTool(role=role)
        # Should not raise WebToolError
        result = tool.web_search("test")  # Will return error (no creds) but won't raise
        assert result.status == "error"  # No creds, but intent was allowed

    @pytest.mark.parametrize("role", ["planner", "reviewer", "implementer", "drafter"])
    @patch("urllib.request.urlopen", side_effect=Exception("mocked"))
    def test_read_url_allowed(self, mock_urlopen: MagicMock, role: str) -> None:
        tool = WebTool(role=role)
        # Should not raise WebToolError
        result = tool.read_url("http://example.com")
        assert result.status == "error"  # Network error (mocked), but intent was allowed


# ===========================================================================
# Constants
# ===========================================================================


class TestConstants:
    """Verify module-level constants."""

    def test_timeout(self) -> None:
        assert TOOL_TIMEOUT_SECONDS == 10
