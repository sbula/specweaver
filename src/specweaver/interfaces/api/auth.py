# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The server's token: no answer without it, for HTTP and the WebSocket alike.

A local bind keeps the network out, not a web page: a page can rebind its own name to 127.0.0.1, or
post a form across sites. Only a secret the page cannot know stops both. A program sends it as
`Authorization: Bearer`; a browser gets it once from the printed address and keeps it as a strict,
HttpOnly cookie; a WebSocket, which a browser cannot give a header, may also carry it as `?token=`.
"""

from __future__ import annotations

import hmac
import secrets
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode

from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse, RedirectResponse
from starlette.websockets import WebSocket

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

COOKIE = "sw_token"
#: Answers without a token: it says only that the server is up.
OPEN_PATHS = frozenset({"/healthz"})


def make_token() -> str:
    """A new token for one start of the server."""
    return secrets.token_urlsafe(32)


class TokenGuard:
    """ASGI middleware refusing every request that does not carry the token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self._app = app
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or scope["path"] in OPEN_PATHS:
            await self._app(scope, receive, send)
            return
        connection = HTTPConnection(scope)
        query = dict(parse_qsl(scope.get("query_string", b"").decode()))
        if scope["type"] == "websocket":
            if self._holds(connection) or self._matches(query.get("token")):
                await self._app(scope, receive, send)
            else:
                await WebSocket(scope, receive, send).close(code=1008)
            return
        if self._holds(connection):
            await self._app(scope, receive, send)
        elif scope["method"] == "GET" and self._matches(query.get("token")):
            await _set_cookie(self._token, scope, query)(scope, receive, send)
        else:
            refusal = {"detail": "a token is required", "error_code": "UNAUTHORIZED"}
            await JSONResponse(refusal, status_code=401)(scope, receive, send)

    def _holds(self, connection: HTTPConnection) -> bool:
        header = connection.headers.get("authorization", "")
        bearer = header[len("Bearer ") :] if header.startswith("Bearer ") else None
        return self._matches(bearer) or self._matches(connection.cookies.get(COOKIE))

    def _matches(self, given: str | None) -> bool:
        return given is not None and hmac.compare_digest(given.encode(), self._token.encode())


def _set_cookie(token: str, scope: Scope, query: dict[str, Any]) -> RedirectResponse:
    """The browser's first visit: keep the token as a cookie, and leave the address without it."""
    rest = urlencode({key: value for key, value in query.items() if key != "token"})
    response = RedirectResponse(scope["path"] + (f"?{rest}" if rest else ""), status_code=303)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/")
    return response
