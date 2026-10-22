# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`POST /pipelines/{name}/run` runs only a spec inside the project.

Proves: TECH-075 FR-2, TECH-075 NFR-1, TECH-075 NFR-2

The real app, token, settings file, run store and the bundled `validate_only` pipeline. Nothing is
faked: the run happens or it does not.

| Bucket | Case |
|---|---|
| Happy | a spec inside runs, and the run holds the resolved spec path |
| Boundary | not applicable — a link inside that points inside is proven by FR-3's seam test |
| Degradation | an unknown project answers 404 and starts no run |
| Hostile | `../`, absolute and an escaping link to an outside file that exists: 400, no run, no absolute path in the answer; an outside file that does not exist is also 400, so the answer never tells which outside files exist |
"""

from __future__ import annotations

import sqlite3
import time
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.e2e

_SPEC = "# A\n## 1. Purpose\nDoes A.\n"


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text("[serve]\nmax_runs = 3\n", encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    bootstrap_database(str(data / "specweaver.db"))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text(_SPEC, encoding="utf-8")
    (tmp_path / "outside_spec.md").write_text(_SPEC, encoding="utf-8")
    (project / "specs" / "leak_spec.md").symlink_to(tmp_path / "outside_spec.md")
    app = create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db"))
    with TestClient(app, headers=AUTH) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        yield client, tmp_path


def _start(client: TestClient, spec: str, project: str = "rest"):
    return client.post(
        "/api/v1/pipelines/validate_only/run", json={"project": project, "spec": spec}
    )


def _runs(tmp_path: Path) -> int:
    db = tmp_path / "data" / "pipeline_state.db"
    if not db.exists():
        return 0
    with sqlite3.connect(db) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM flow_pipeline_runs").fetchone()[0])


def test_a_spec_inside_runs_with_its_resolved_path(world: tuple[TestClient, Path]) -> None:
    client, tmp_path = world

    started = _start(client, "specs/../specs/a_spec.md")
    assert started.status_code == 200, started.text
    run_id = started.json()["run_id"]
    run: dict[str, object] = {}
    for _ in range(200):
        reply = client.get(f"/api/v1/runs/{run_id}")
        if reply.status_code == 200:
            run = reply.json()
            if run.get("status") not in ("pending", "running", "not_started"):
                break
        time.sleep(0.05)

    assert run.get("spec_path") == str((tmp_path / "proj" / "specs" / "a_spec.md").resolve())


@pytest.mark.parametrize(
    "spec", ["../outside_spec.md", "../no_such_spec.md", "specs/leak_spec.md", "ABSOLUTE"]
)
def test_a_spec_outside_is_refused_and_starts_nothing(
    world: tuple[TestClient, Path], spec: str
) -> None:
    client, tmp_path = world
    given = str(tmp_path / "outside_spec.md") if spec == "ABSOLUTE" else spec

    refused = _start(client, given)

    assert refused.status_code == 400, refused.text
    assert refused.json()["error_code"] == "PATH_TRAVERSAL"
    detail = refused.json()["detail"]
    assert given in detail
    if spec != "ABSOLUTE":
        assert str(tmp_path) not in detail
    time.sleep(0.2)
    assert _runs(tmp_path) == 0


def test_an_unknown_project_starts_nothing(world: tuple[TestClient, Path]) -> None:
    client, tmp_path = world

    refused = _start(client, "specs/a_spec.md", project="nobody")

    assert refused.status_code == 404
    assert refused.json()["error_code"] == "PROJECT_NOT_FOUND"
    assert _runs(tmp_path) == 0
