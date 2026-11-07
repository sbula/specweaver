# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""On a fresh machine the API builds its files and answers on a current schema.

Proves: TECH-090 FR-7 (path P-2)
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e


def test_a_fresh_machine_api_answers_on_a_current_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))

    with TestClient(create_app(token=TEST_TOKEN), headers=AUTH) as client:
        assert client.get("/healthz").status_code == 200
        projects = client.get("/api/v1/projects")

    assert projects.status_code == 200, projects.text
    assert projects.json() == []
    for name in ("specweaver.db", "pipeline_state.db"):
        with closing(sqlite3.connect(data / name)) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
