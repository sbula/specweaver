# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The REST endpoints that call a model really call it, through the same steps as the CLI.

Proves: C-FLOW-01 FR-5

Settings file → `POST /review` and `POST /implement` → the pipeline handlers → a real adapter.
Only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | `POST /review` returns the model's verdict; `POST /implement` writes the code and the tests; each call is one `ok` row in the cost ledger (`C-FLOW-01` FR-1, FR-4) |
| Boundary | not applicable — the request shapes are proven by the endpoint unit tests |
| Degradation | a ledger that refuses rows: both endpoints still answer, with `unwritten_calls` (`C-FLOW-01` FR-5) |
| Hostile | not applicable — paths are proven by `resolve_file_in_project`'s own tests |
"""

from __future__ import annotations

import sqlite3
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

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000000
agent_turns = 5
"""


def _reply(text: str) -> dict:
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    bootstrap_database(str(data_dir / "specweaver.db"))
    test_client = TestClient(create_app(db=Database(data_dir / "specweaver.db")))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "greeter_spec.md").write_text(
        "# Greeter\n## 1. Purpose\nGreets.\n", encoding="utf-8"
    )
    test_client.post(
        "/api/v1/projects", json={"name": "api", "path": str(project), "scaffold": False}
    )
    return test_client


def test_review_returns_the_models_verdict(client: TestClient) -> None:
    verdict = "VERDICT: DENIED\n- missing error paths [confidence: 90]\nNeeds work."

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(verdict))) as seen:
        response = client.post(
            "/api/v1/review", json={"file": "specs/greeter_spec.md", "project": "api"}
        )

    assert seen, "the endpoint never called the model"
    assert response.status_code == 200, response.text
    assert response.json()["verdict"] == "denied"


def test_implement_writes_the_code_and_the_tests(client: TestClient, tmp_path: Path) -> None:
    code = "def greet() -> str:\n    return 'hi'\n"

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(code))) as seen:
        response = client.post(
            "/api/v1/implement", json={"file": "specs/greeter_spec.md", "project": "api"}
        )

    assert len(seen) == 2, "code and tests are two model calls"
    assert response.status_code == 200, response.text
    body = response.json()
    assert (tmp_path / "proj" / "src" / "greeter.py").read_text(encoding="utf-8").strip()
    assert body["code_path"].endswith("src/greeter.py")
    assert body["test_path"].endswith("tests/test_greeter.py")


def _ledger(tmp_path: Path) -> list[tuple[str, str, str, int, int]]:
    with sqlite3.connect(tmp_path / "data" / "specweaver.db") as db:
        return db.execute(
            "SELECT project_name, task_type, call_status, prompt_tokens, completion_tokens"
            " FROM llm_usage_log"
        ).fetchall()


@pytest.mark.parametrize(
    ("endpoint", "reply", "task_type", "calls"),
    [
        ("review", "VERDICT: ACCEPTED\nFine.", "review", 1),
        ("implement", "def greet() -> str:\n    return 'hi'\n", "implement", 2),
    ],
)
def test_every_api_model_call_is_one_ledger_row(
    client: TestClient, tmp_path: Path, endpoint: str, reply: str, task_type: str, calls: int
) -> None:
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(reply))):
        response = client.post(
            f"/api/v1/{endpoint}", json={"file": "specs/greeter_spec.md", "project": "api"}
        )

    assert response.status_code == 200, response.text
    assert _ledger(tmp_path) == [("api", task_type, "ok", 10, 10)] * calls
    assert response.json()["unwritten_calls"] == 0


@pytest.mark.parametrize(
    ("endpoint", "reply", "calls"),
    [("review", "VERDICT: ACCEPTED\nFine.", 1), ("implement", "def greet():\n    pass\n", 2)],
)
def test_an_endpoint_whose_ledger_refuses_rows_answers_how_many_are_missing(
    client: TestClient, tmp_path: Path, monkeypatch, endpoint: str, reply: str, calls: int
) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _refused(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(LlmRepository, "open_call", _refused)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(reply))):
        response = client.post(
            f"/api/v1/{endpoint}", json={"file": "specs/greeter_spec.md", "project": "api"}
        )

    assert response.status_code == 200, response.text
    assert response.json()["unwritten_calls"] == calls
    assert _ledger(tmp_path) == []
