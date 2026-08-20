# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw serve` reaches the network only when asked to.

Proves: D-UI-01 FR-3

Phase 1 of this API ships **no authentication** — the plan says so outright and justifies it by
the server being local-only. That makes the bind address the entire access control story: change
the default from `127.0.0.1` to `0.0.0.0` and every endpoint here, including the ones that start
pipeline runs and execute code, is reachable by anything on the network with no credential at all.

Nothing tested it. The suite has 145 API tests and the closest was a CORS regex assertion, which
governs which *browser origins* may call a server somebody can already reach — a different
question. So this was a one-character change away from an unauthenticated remote surface, with a
green suite either side of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typer.testing import CliRunner

from specweaver.interfaces.cli.routers.serve_router import serve, serve_cli

if TYPE_CHECKING:
    import pytest

if TYPE_CHECKING:
    import pytest


def _default(name: str) -> Any:
    """The declared default of one `serve` option, read from the signature itself."""
    import inspect

    parameter = inspect.signature(serve).parameters[name]
    return parameter.default.default


def test_the_default_bind_is_the_loopback_address() -> None:
    assert _default("host") == "127.0.0.1"


def test_the_default_bind_is_not_a_wildcard() -> None:
    """Stated separately and on purpose: `0.0.0.0` and `::` are the two values that would expose
    an unauthenticated API, and an equality check on the good value would still pass if someone
    introduced a third."""
    assert _default("host") not in {"0.0.0.0", "::", "*", ""}


def test_the_bind_address_reaches_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """A default nothing forwards is decoration.

    This is the half that a signature check cannot see: `serve` could declare `127.0.0.1` and hand
    uvicorn something else entirely.
    """
    seen: dict[str, Any] = {}

    def _capture(app: Any, **kwargs: Any) -> None:
        seen.update(kwargs)

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", _capture)
    monkeypatch.setattr("specweaver.interfaces.api.app.create_app", lambda **kwargs: object())

    # `serve_cli` holds one command, which Typer flattens onto the app itself.
    result = CliRunner().invoke(serve_cli, [])

    assert result.exit_code == 0, result.output
    assert seen.get("host") == "127.0.0.1"


def test_an_explicit_host_is_still_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control. A server that ignored `--host` would pass every assertion above while being
    unable to serve a container or a LAN deliberately — the opposite failure, equally real."""
    seen: dict[str, Any] = {}

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: seen.update(kwargs))
    monkeypatch.setattr("specweaver.interfaces.api.app.create_app", lambda **kwargs: object())

    result = CliRunner().invoke(serve_cli, ["--host", "10.0.0.5"])

    assert result.exit_code == 0, result.output
    assert seen.get("host") == "10.0.0.5"
