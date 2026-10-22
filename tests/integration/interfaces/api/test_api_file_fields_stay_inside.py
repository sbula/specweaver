# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every API file field is judged by where the path lands, not by its text.

Proves: TECH-075 FR-3, TECH-075 NFR-2, TECH-075 NFR-3

The real app and routes → `resolve_file_in_project` → `core.flow` helper → `WorkspaceBoundary`.

| Bucket | Case |
|---|---|
| Happy | `/check` on a spec inside answers 200 |
| Boundary | a link inside that points inside passes the check |
| Degradation | a missing file inside answers 404 `FILE_NOT_FOUND` |
| Hostile | a link inside that points outside: 400 on `/implement`, `/review`, `/check`, the answer naming only the input |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_SPEC = "# A — Component Spec\n## 1. Purpose\nDoes A.\n"


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text(_SPEC, encoding="utf-8")
    (project / "specs" / "alias_spec.md").symlink_to(project / "specs" / "a_spec.md")
    (tmp_path / "outside_spec.md").write_text(_SPEC, encoding="utf-8")
    (project / "specs" / "leak_spec.md").symlink_to(tmp_path / "outside_spec.md")
    app = create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db"))
    with TestClient(app, headers=AUTH) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        yield client, tmp_path


@pytest.mark.parametrize("route", ["/api/v1/implement", "/api/v1/review", "/api/v1/check"])
def test_a_link_that_points_outside_is_refused(world: tuple[TestClient, Path], route: str) -> None:
    client, tmp_path = world

    refused = client.post(route, json={"file": "specs/leak_spec.md", "project": "rest"})

    assert refused.status_code == 400, refused.text
    assert refused.json()["error_code"] == "PATH_TRAVERSAL"
    assert "specs/leak_spec.md" in refused.json()["detail"]
    assert str(tmp_path) not in refused.json()["detail"]


@pytest.mark.parametrize("file", ["specs/a_spec.md", "specs/alias_spec.md"])
def test_a_file_inside_is_checked(world: tuple[TestClient, Path], file: str) -> None:
    client, _ = world

    checked = client.post("/api/v1/check", json={"file": file, "project": "rest"})

    assert checked.status_code == 200, checked.text


def test_a_missing_file_inside_is_not_found(world: tuple[TestClient, Path]) -> None:
    client, _ = world

    missing = client.post("/api/v1/check", json={"file": "specs/none.md", "project": "rest"})

    assert missing.status_code == 404
    assert missing.json()["error_code"] == "FILE_NOT_FOUND"
