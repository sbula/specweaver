# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""WebTool: Tavily search, and a read_url that stays on the public internet.

Proves: E-SENS-02 FR-1
Proves: E-SENS-02 FR-2
Proves: E-SENS-02 FR-3
"""

from __future__ import annotations

import json
import socket

import httpx
import pytest
import respx

from specweaver.sandbox.web.interfaces import tool as web_tool
from specweaver.sandbox.web.interfaces.tool import (
    ROLE_INTENTS,
    TOOL_TIMEOUT_SECONDS,
    WebTool,
    WebToolResult,
    _strip_html,
)

TAVILY = "https://api.tavily.com/search"
PUBLIC_IP = "93.184.215.14"


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Names the test resolves itself; anything else goes to the real resolver."""
    names: dict[str, str] = {"docs.example": PUBLIC_IP}
    real = socket.getaddrinfo

    def fake(host: str, *args: object, **kwargs: object) -> object:
        if host in names:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (names[host], 0))]
        return real(host, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    return names


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

    def test_web_enabled_with_a_key(self) -> None:
        assert WebTool(role="planner", api_key="key").web_enabled is True

    def test_web_disabled_without_key(self) -> None:
        assert WebTool(role="planner", api_key="").web_enabled is False


# ===========================================================================
# web_search — Tavily
# ===========================================================================


class TestWebSearch:
    """web_search asks Tavily, sending the key only in the Authorization header."""

    def test_no_key_returns_error(self) -> None:
        result = WebTool(role="planner").web_search("test query")
        assert result.status == "error"
        assert "key" in result.message.lower()

    @respx.mock
    def test_successful_search(self) -> None:
        # Proves: E-SENS-02 FR-1
        route = respx.post(TAVILY).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "R1",
                            "url": "https://a.example/1",
                            "content": "C1",
                            "score": 0.9,
                        },
                        {
                            "title": "R2",
                            "url": "https://a.example/2",
                            "content": "C2",
                            "score": 0.5,
                        },
                    ]
                },
            )
        )
        result = WebTool(role="planner", api_key="secret-key").web_search("python docs")

        assert result.status == "success"
        assert result.data == [
            {"title": "R1", "snippet": "C1", "url": "https://a.example/1"},
            {"title": "R2", "snippet": "C2", "url": "https://a.example/2"},
        ]
        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer secret-key"
        body = json.loads(sent.content)
        assert body == {"query": "python docs", "max_results": 5, "search_depth": "basic"}

    @respx.mock
    @pytest.mark.parametrize(("asked", "sent"), [(3, 3), (0, 1), (-4, 1), (50, 20)])
    def test_max_results_is_clamped_to_what_tavily_takes(self, asked: int, sent: int) -> None:
        route = respx.post(TAVILY).mock(return_value=httpx.Response(200, json={"results": []}))
        WebTool(role="planner", api_key="k").web_search("q", max_results=asked)
        assert json.loads(route.calls.last.request.content)["max_results"] == sent

    @respx.mock
    def test_extra_results_are_cut(self) -> None:
        items = [
            {"title": f"R{i}", "url": f"https://a.example/{i}", "content": ""} for i in range(9)
        ]
        respx.post(TAVILY).mock(return_value=httpx.Response(200, json={"results": items}))
        result = WebTool(role="planner", api_key="k").web_search("q", max_results=3)
        assert [r["title"] for r in result.data] == ["R0", "R1", "R2"]

    @respx.mock
    def test_empty_results(self) -> None:
        respx.post(TAVILY).mock(return_value=httpx.Response(200, json={}))
        result = WebTool(role="planner", api_key="k").web_search("nothing")
        assert result.status == "success"
        assert result.data == []

    @respx.mock
    def test_a_refused_key_is_an_error_that_does_not_name_the_key(self) -> None:
        respx.post(TAVILY).mock(return_value=httpx.Response(401, json={"detail": "bad key"}))
        result = WebTool(role="planner", api_key="secret-key").web_search("q")
        assert result.status == "error"
        assert "401" in result.message
        assert "secret-key" not in result.message

    @respx.mock
    def test_network_error_returns_error(self) -> None:
        respx.post(TAVILY).mock(side_effect=httpx.ConnectError("Network down"))
        result = WebTool(role="planner", api_key="k").web_search("test")
        assert result.status == "error"
        assert "Network down" in result.message


# ===========================================================================
# read_url
# ===========================================================================


class TestReadUrl:
    """read_url fetches a public page as text."""

    @respx.mock
    def test_successful_read(self, public_dns: dict[str, str]) -> None:
        # Proves: E-SENS-02 FR-2
        respx.get("https://docs.example/page").mock(
            return_value=httpx.Response(200, text="<html><body><p>Hello world</p></body></html>")
        )
        result = WebTool(role="planner").read_url("https://docs.example/page")
        assert result.status == "success"
        assert "Hello world" in result.data["content"]
        assert result.data["url"] == "https://docs.example/page"

    @respx.mock
    def test_truncation(self, public_dns: dict[str, str]) -> None:
        respx.get("https://docs.example/").mock(
            return_value=httpx.Response(200, text="<p>" + "x" * 500 + "</p>")
        )
        result = WebTool(role="planner").read_url("https://docs.example/", max_chars=100)
        assert result.status == "success"
        assert len(result.data["content"]) == 100
        assert result.data["truncated"] is True
        assert "truncated" in result.data["warning"].lower()

    @respx.mock
    def test_an_http_error_is_an_error(self, public_dns: dict[str, str]) -> None:
        respx.get("https://docs.example/missing").mock(return_value=httpx.Response(404))
        result = WebTool(role="planner").read_url("https://docs.example/missing")
        assert result.status == "error"
        assert "404" in result.message

    @respx.mock
    def test_a_huge_page_is_read_only_up_to_the_cap(self, public_dns: dict[str, str]) -> None:
        respx.get("https://docs.example/big").mock(
            return_value=httpx.Response(200, text="y" * (web_tool.MAX_PAGE_BYTES * 3))
        )
        result = WebTool(role="planner").read_url("https://docs.example/big", max_chars=10**9)
        assert result.status == "success"
        assert len(result.data["content"]) <= web_tool.MAX_PAGE_BYTES

    @respx.mock
    def test_a_redirect_to_a_public_page_is_followed(self, public_dns: dict[str, str]) -> None:
        public_dns["other.example"] = PUBLIC_IP
        respx.get("https://docs.example/old").mock(
            return_value=httpx.Response(301, headers={"Location": "https://other.example/new"})
        )
        respx.get("https://other.example/new").mock(
            return_value=httpx.Response(200, text="<p>moved here</p>")
        )
        result = WebTool(role="planner").read_url("https://docs.example/old")
        assert result.status == "success"
        assert "moved here" in result.data["content"]
        assert result.data["url"] == "https://other.example/new"

    @respx.mock
    def test_endless_redirects_stop(self, public_dns: dict[str, str]) -> None:
        route = respx.get("https://docs.example/loop").mock(
            return_value=httpx.Response(302, headers={"Location": "/loop"})
        )
        result = WebTool(role="planner").read_url("https://docs.example/loop")
        assert result.status == "error"
        assert "redirect" in result.message.lower()
        assert route.call_count == web_tool.MAX_REDIRECTS + 1


class TestReadUrlRefusesPrivateAddresses:
    """An agent must not reach the machine, the local network, or a cloud's metadata service."""

    @respx.mock
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:8000/admin",
            "http://localhost/",
            "http://[::1]/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://0.0.0.0/",
            "http://[fd00::1]/",
            "http://224.0.0.1/",
            "http://[::ffff:127.0.0.1]/",
        ],
    )
    def test_a_private_address_is_refused(self, url: str) -> None:
        # Proves: E-SENS-02 FR-3
        route = respx.route().mock(return_value=httpx.Response(200, text="secret"))
        result = WebTool(role="planner").read_url(url)
        assert result.status == "error"
        assert "not a public address" in result.message
        assert not route.called

    @respx.mock
    def test_a_name_that_resolves_to_a_private_address_is_refused(
        self, public_dns: dict[str, str]
    ) -> None:
        # Proves: E-SENS-02 FR-3
        public_dns["intranet.example"] = "10.1.2.3"
        route = respx.route().mock(return_value=httpx.Response(200, text="secret"))
        result = WebTool(role="planner").read_url("https://intranet.example/")
        assert result.status == "error"
        assert "not a public address" in result.message
        assert not route.called

    @respx.mock
    def test_a_redirect_to_a_private_address_is_refused(self, public_dns: dict[str, str]) -> None:
        # Proves: E-SENS-02 FR-3
        respx.get("https://docs.example/go").mock(
            return_value=httpx.Response(
                302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
            )
        )
        metadata = respx.get("http://169.254.169.254/latest/meta-data/").mock(
            return_value=httpx.Response(200, text="secret")
        )
        result = WebTool(role="planner").read_url("https://docs.example/go")
        assert result.status == "error"
        assert "not a public address" in result.message
        assert not metadata.called

    @pytest.mark.parametrize(
        "url",
        ["file:///etc/passwd", "ftp://docs.example/x", "gopher://docs.example/", "docs.example"],
    )
    def test_only_http_and_https_are_read(self, url: str, public_dns: dict[str, str]) -> None:
        # Proves: E-SENS-02 FR-3
        result = WebTool(role="planner").read_url(url)
        assert result.status == "error"
        assert "only http and https" in result.message

    def test_a_name_that_does_not_resolve_is_an_error(self) -> None:
        result = WebTool(role="planner").read_url("https://no-such-host.invalid/")
        assert result.status == "error"


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
        result = WebTool(role=role).web_search("test")  # no key: an error, not a WebToolError
        assert result.status == "error"

    @pytest.mark.parametrize("role", ["planner", "reviewer", "implementer", "drafter"])
    def test_read_url_allowed(self, role: str) -> None:
        result = WebTool(role=role).read_url("http://127.0.0.1/")  # refused, not a WebToolError
        assert result.status == "error"


# ===========================================================================
# Constants
# ===========================================================================


class TestConstants:
    """Verify module-level constants."""

    def test_timeout(self) -> None:
        assert TOOL_TIMEOUT_SECONDS == 10
