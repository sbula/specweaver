# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`POST /check` judges a file with its own project's domain profile, not the active project's.

Proves: TECH-077 FR-4

A real app and two registered projects; the pipeline loader is spied on to see which validation
pipeline the check used.

| Bucket | Case |
|---|---|
| Happy | a project with the `web-app` profile is checked with that profile's pipeline |
| Boundary | a project with no profile is checked with the default pipeline |
| Degradation | not applicable — an unknown project is a 404 tested by the path tests |
| Hostile | project B, while project A (`web-app`) is active, never gets A's profile |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN
from tests.fixtures.db_utils import set_test_active_project

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_SPEC = "# Orders\n\n## 1. Purpose\nTakes orders.\n"


@pytest.fixture()
def world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, list[str]]]:
    from specweaver.assurance.validation import pipeline_loader
    from specweaver.workspace.store import WorkspaceRepository

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    db = Database(path)
    seen: list[str] = []
    real = pipeline_loader.load_pipeline_yaml

    def _spy(name: str, **kwargs: object) -> object:
        seen.append(name)
        return real(name, **kwargs)

    monkeypatch.setattr(pipeline_loader, "load_pipeline_yaml", _spy)
    with TestClient(create_app(token=TEST_TOKEN, db=db), headers=AUTH) as client:
        for name in ("ay", "bee"):
            root = tmp_path / name
            (root / "specs").mkdir(parents=True)
            (root / "specs" / "orders_spec.md").write_text(_SPEC, encoding="utf-8")
            client.post(
                "/api/v1/projects", json={"name": name, "path": str(root), "scaffold": False}
            )

        async def _profile() -> None:
            async with db.async_session_scope() as session:
                await WorkspaceRepository(session).set_domain_profile("ay", "web-app")

        asyncio.run(_profile())
        set_test_active_project(db, "ay")
        yield client, seen


def _check(client: TestClient, project: str) -> object:
    return client.post("/api/v1/check", json={"file": "specs/orders_spec.md", "project": project})


def test_a_project_is_checked_with_its_own_profile(world) -> None:
    client, seen = world

    assert _check(client, "ay").status_code == 200

    assert seen[0] == "validation_spec_web_app"


def test_another_project_never_gets_the_active_projects_profile(world) -> None:
    client, seen = world

    assert _check(client, "bee").status_code == 200

    assert seen[0] == "validation_spec_default"
