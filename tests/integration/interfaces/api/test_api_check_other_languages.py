# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`POST /check` at code level on a Kotlin file returns C01, C06 and C08 as skipped.

Proves: TECH-093 FR-4

A real app and a registered project; the hydrator, the executor and the rules are real. Before
TECH-093, C01 came back `fail` and was counted in `failed`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_KOTLIN = "src/main/kotlin/shop/Cart.kt"


def test_a_kotlin_file_comes_back_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    root = tmp_path / "shop"
    (root / _KOTLIN).parent.mkdir(parents=True)
    (root / _KOTLIN).write_text(
        "package shop\n\nclass Cart { fun total(): Int = 0 }\n", encoding="utf-8"
    )

    db = Database(data / "specweaver.db")
    with TestClient(create_app(token=TEST_TOKEN, db=db), headers=AUTH) as client:
        client.post("/api/v1/projects", json={"name": "shop", "path": str(root), "scaffold": False})
        response = client.post(
            "/api/v1/check", json={"file": _KOTLIN, "level": "code", "project": "shop"}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    rows = {r["rule_id"]: r for r in body["results"]}
    for rule_id in ("C01", "C06", "C08"):
        assert rows[rule_id]["status"] == "skip", rows[rule_id]
        assert rows[rule_id]["message"].startswith("kotlin:"), rows[rule_id]
    failed_ids = {r["rule_id"] for r in body["results"] if r["status"] == "fail"}
    assert failed_ids.isdisjoint({"C01", "C06", "C08"})
