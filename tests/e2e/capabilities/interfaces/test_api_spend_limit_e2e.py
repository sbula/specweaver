# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A REST request that reaches a spend limit gets 402 `SPEND_LIMIT`, naming the limit (US-04 S6).

Proves: B-FLOW-05 FR-10

| Bucket | Case |
|---|---|
| Happy | not applicable — a request within its limits is proven by the endpoint tests |
| Boundary | the very first call of `POST /review` would cross the model's limit |
| Degradation | nobody can answer over REST, so the request stops instead of pausing |
| Hostile | not applicable — no request field reaches the limit |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
import pytest
from starlette.testclient import TestClient

from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 1000 }

[models."qwen3-coder-next"]
tokens_per_run = 500

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000000
agent_turns = 5
"""


def test_a_request_at_a_limit_gets_402_naming_it(tmp_path: Path, monkeypatch) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    bootstrap_database(str(data_dir / "specweaver.db"))
    client = TestClient(create_app(db=Database(data_dir / "specweaver.db")))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n", encoding="utf-8")
    client.post("/api/v1/projects", json={"name": "p402", "path": str(project), "scaffold": False})

    with fake_httpx2(lambda _request: httpx2.Response(500)) as seen:
        response = client.post(
            "/api/v1/review", json={"file": "specs/greeter_spec.md", "project": "p402"}
        )

    assert seen == []
    assert response.status_code == 402, response.text
    body = response.json()
    assert body["error_code"] == "SPEND_LIMIT"
    assert 'models."qwen3-coder-next".tokens_per_run' in body["detail"]
