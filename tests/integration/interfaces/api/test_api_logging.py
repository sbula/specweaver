# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The API logs to its own file in the CLI's log folder, never to the CLI's `_global` one.

Proves: TECH-090 FR-12

| Bucket | Case |
|---|---|
| Happy | a route's log record reaches `logs/_api/specweaver.log` |
| Boundary | nothing of it reaches `logs/_global/` |
| Degradation | not applicable: setting up logging has no input that can fail here |
| Hostile | `_api` can never be a project's name, so no project shares the file |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from specweaver.interfaces.api.app import create_app
from specweaver.workspace.store import _validate_project_name
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def test_a_route_logs_to_the_api_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    app = create_app(token=TEST_TOKEN)

    with TestClient(app, headers=AUTH) as client:
        assert client.get("/healthz").status_code == 200
    for handler in logging.getLogger("specweaver").handlers:
        handler.flush()

    log = (data / "logs" / "_api" / "specweaver.log").read_text(encoding="utf-8")
    assert "Executing healthz API endpoint" in log
    assert not (data / "logs" / "_global").exists()


def test_api_can_never_be_a_project_name() -> None:
    with pytest.raises(ValueError, match="Invalid project name"):
        _validate_project_name("_api")
