# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every run route and project route refuses the same way: an unknown run or project is a 404,
a run that is not parked is a 409 where a parked one is needed.

Real files in a temporary data dir; no model is called, because every request stops before a run.

Proves: TECH-090 FR-14

| Bucket | Case |
|---|---|
| Happy | a known run's status and log answer 200 |
| Boundary | a finished run is refused by `resume` and `gate` with 409 `RUN_NOT_PARKED` |
| Degradation | an unknown run is a 404 `RUN_NOT_FOUND` on all four run routes |
| Hostile | an unknown project is a 404 `PROJECT_NOT_FOUND` for `DELETE` and `use`; a known one is not removed by a failed `use` |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from specweaver.core.config.paths import state_db_path
from specweaver.core.flow.engine.state import PipelineRun, RunStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.infrastructure.database import Database
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_RUN_ROUTES = [
    ("get", "/api/v1/runs/{id}", None),
    ("get", "/api/v1/runs/{id}/log", None),
    ("post", "/api/v1/runs/{id}/resume", None),
    ("post", "/api/v1/runs/{id}/gate", {"action": "approve"}),
]


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
    app = create_app(token=TEST_TOKEN)
    db = Database(tmp_path / "data" / "specweaver.db")
    register_test_project(db, "proj", str(tmp_path))
    StateStore(state_db_path()).save_run(
        PipelineRun(
            run_id="done-1",
            pipeline_name="validate_only",
            project_name="proj",
            spec_path=str(tmp_path / "spec.md"),
            status=RunStatus.COMPLETED,
            started_at="2026-11-07T00:00:00+00:00",
            updated_at="2026-11-07T00:00:00+00:00",
        )
    )
    return TestClient(app, headers=AUTH)


def _call(client: TestClient, method: str, path: str, body: dict | None):
    return getattr(client, method)(path, json=body) if body else getattr(client, method)(path)


@pytest.mark.parametrize(("method", "path", "body"), _RUN_ROUTES)
def test_an_unknown_run_is_a_404_on_every_run_route(
    client: TestClient, method: str, path: str, body: dict | None
) -> None:
    response = _call(client, method, path.format(id="ghost"), body)

    assert response.status_code == 404
    assert response.json()["error_code"] == "RUN_NOT_FOUND"
    assert "ghost" in response.json()["detail"]


@pytest.mark.parametrize(("method", "path", "body"), _RUN_ROUTES[2:])
def test_a_run_that_is_not_parked_is_a_409(
    client: TestClient, method: str, path: str, body: dict | None
) -> None:
    response = _call(client, method, path.format(id="done-1"), body)

    assert response.status_code == 409
    assert response.json()["error_code"] == "RUN_NOT_PARKED"
    assert "status=completed" in response.json()["detail"]


@pytest.mark.parametrize(("method", "path", "body"), _RUN_ROUTES[:2])
def test_a_known_run_answers(client: TestClient, method: str, path: str, body: dict | None) -> None:
    assert _call(client, method, path.format(id="done-1"), body).status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [("delete", "/api/v1/projects/ghost"), ("post", "/api/v1/projects/ghost/use")],
)
def test_an_unknown_project_is_a_404(client: TestClient, method: str, path: str) -> None:
    response = getattr(client, method)(path)

    assert response.status_code == 404
    assert response.json()["error_code"] == "PROJECT_NOT_FOUND"
    assert "ghost" in response.json()["detail"]
    assert [p["name"] for p in client.get("/api/v1/projects").json()] == ["proj"]
