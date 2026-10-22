# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project path given over the API is stored, and answered, as the resolved folder.

Proves: TECH-075 FR-7, TECH-075 NFR-2

The real app → `resolve_project_path` (the resolver `sw init` uses) → the workspace store.

| Bucket | Case |
|---|---|
| Happy | POST and PUT with a relative path store and answer the resolved folder |
| Boundary | one folder by two spellings is one project (409); the API and `sw init`'s resolver agree |
| Degradation | PUT to a missing folder → 400 `PATH_NOT_FOUND`, the row unchanged |
| Hostile | a file instead of a folder, or a blank path (which would mean the server's folder) → 400 on POST and PUT; an error names only the input |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from specweaver.workspace.project.discovery import resolve_project_path
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    bootstrap_database(str(data / "specweaver.db"))
    (tmp_path / "proj").mkdir()
    (tmp_path / "moved").mkdir()
    (tmp_path / "a_file.txt").write_text("x", encoding="utf-8")
    app = create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db"))
    with TestClient(app, headers=AUTH) as client:
        yield client, tmp_path


def _create(client: TestClient, name: str, path: str):
    return client.post("/api/v1/projects", json={"name": name, "path": path, "scaffold": False})


def _stored(client: TestClient, name: str) -> str:
    return next(p["path"] for p in client.get("/api/v1/projects").json() if p["name"] == name)


@pytest.mark.parametrize("given", ["proj", "moved/../proj", "./proj/"])
def test_create_stores_and_answers_the_resolved_folder(
    world: tuple[TestClient, Path], given: str
) -> None:
    client, tmp_path = world
    wanted = str((tmp_path / "proj").resolve())

    created = _create(client, "p", given)

    assert created.status_code == 201, created.text
    assert created.json()["path"] == wanted
    assert _stored(client, "p") == wanted
    assert _stored(client, "p") == str(resolve_project_path(given))


def test_update_stores_and_answers_the_resolved_folder(world: tuple[TestClient, Path]) -> None:
    client, tmp_path = world
    _create(client, "p", "proj")

    updated = client.put("/api/v1/projects/p", json={"path": "proj/../moved"})

    assert updated.status_code == 200, updated.text
    assert updated.json()["path"] == str((tmp_path / "moved").resolve())
    assert _stored(client, "p") == str((tmp_path / "moved").resolve())


def test_one_folder_by_two_spellings_is_one_project(world: tuple[TestClient, Path]) -> None:
    client, tmp_path = world
    _create(client, "p", "proj")

    again = _create(client, "q", str(tmp_path / "moved" / ".." / "proj"))

    assert again.status_code == 409, again.text


@pytest.mark.parametrize("given", ["missing", "a_file.txt"])
def test_update_to_a_path_that_is_not_a_folder_is_refused(
    world: tuple[TestClient, Path], given: str
) -> None:
    client, tmp_path = world
    _create(client, "p", "proj")
    before = _stored(client, "p")

    refused = client.put("/api/v1/projects/p", json={"path": given})

    assert refused.status_code == 400, refused.text
    assert refused.json()["error_code"] == "PATH_NOT_FOUND"
    assert given in refused.json()["detail"]
    assert str(tmp_path) not in refused.json()["detail"]
    assert _stored(client, "p") == before


@pytest.mark.parametrize("given", ["missing", "a_file.txt", "", "   "])
def test_create_with_a_path_that_is_not_a_folder_is_refused(
    world: tuple[TestClient, Path], given: str
) -> None:
    client, tmp_path = world

    refused = _create(client, "p", given)

    assert refused.status_code == 400, refused.text
    assert refused.json()["error_code"] == "PATH_NOT_FOUND"
    assert str(tmp_path) not in refused.json()["detail"]
    assert client.get("/api/v1/projects").json() == []


def test_moving_onto_another_projects_folder_by_another_spelling_is_refused(
    world: tuple[TestClient, Path],
) -> None:
    client, _ = world
    _create(client, "p", "proj")
    _create(client, "q", "moved")

    refused = client.put("/api/v1/projects/q", json={"path": "moved/../proj"})

    assert refused.status_code == 400, refused.text
    assert refused.json()["error_code"] == "INVALID_PATH"
    assert _stored(client, "q").endswith("moved")
