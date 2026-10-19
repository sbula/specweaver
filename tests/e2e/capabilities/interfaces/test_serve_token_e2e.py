# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw serve` makes a token, keeps it where only its owner can read it, and hands it to the user.

Proves: D-UI-01 FR-6, NFR-1

The real CLI; only `uvicorn.run` is replaced, so the app it would serve is caught and asked.

| Bucket | Case |
|---|---|
| Happy | the printed dashboard address carries the token, and the app serves it |
| Boundary | each start makes a new token |
| Degradation | not applicable — the server is never started |
| Hostile | the token file is readable by its owner only; no log line carries the token; the app refuses a request without it |
"""

from __future__ import annotations

import logging
import re
import stat
from typing import TYPE_CHECKING, Any

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from specweaver.core.config.database import Database

runner = CliRunner()


def _serve(monkeypatch: pytest.MonkeyPatch) -> tuple[str, Any]:
    import uvicorn

    caught: dict[str, Any] = {}
    monkeypatch.setattr(uvicorn, "run", lambda served, **_kwargs: caught.setdefault("app", served))
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split()), caught["app"]


def test_serve_hands_out_its_token(
    _mock_db: Database,
    _isolate_env: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        output, served = _serve(monkeypatch)

    token = (_isolate_env / "serve.token").read_text(encoding="utf-8").strip()
    assert re.search(rf"/dashboard\?token={re.escape(token)}", output)
    assert stat.S_IMODE((_isolate_env / "serve.token").stat().st_mode) == 0o600
    assert not [r for r in caplog.records if token in r.getMessage()]
    client = TestClient(served)
    assert client.get("/api/v1/projects").status_code == 401
    assert (
        client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )


def test_each_start_makes_a_new_token(
    _mock_db: Database, _isolate_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _serve(monkeypatch)
    first = (_isolate_env / "serve.token").read_text(encoding="utf-8")
    _serve(monkeypatch)

    assert (_isolate_env / "serve.token").read_text(encoding="utf-8") != first
