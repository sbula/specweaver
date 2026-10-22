# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A pipeline named by an API client is the project's own or a bundled one, and nothing else.

Proves: TECH-075 FR-10, TECH-075 NFR-2

The real app → `core.flow` parser and `assurance.validation` loader; the run's work is replaced by a
wait, so the test sees which pipeline was loaded, not what it does.

| Bucket | Case |
|---|---|
| Happy | a bundled name runs; the project's own `.specweaver/pipelines/<name>.yaml` runs; `/check` loads a project-local validation pipeline |
| Boundary | `foo.yaml`, a bundled name that is not a run pipeline (`validation_spec_default`) → 404 |
| Degradation | an unknown name → 404 on run and `/check`; an invalid project pipeline → 404; a parked run whose stored name is not allowed cannot resume |
| Hostile | a YAML file beside the server; a leading dot; a stored name that walks out of `.specweaver/pipelines`; a pipelines folder that links outside; `/check` `../../../evil` to an outside YAML that exists — all 404, never loaded |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from specweaver.core.flow.engine.runner import PipelineRunner
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_RUN_PIPELINE = """\
name: {name}
version: "1.0"
steps:
  - name: check_spec
    action: validate
    target: spec
"""

_CHECK_PIPELINE = """\
name: {name}
description: one rule
version: "1.0"
steps:
  - name: s01
    rule: S01
"""


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text("[serve]\nmax_runs = 5\n", encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)

    async def _waits(_self: PipelineRunner, *_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(PipelineRunner, "run", _waits)
    bootstrap_database(str(data / "specweaver.db"))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text("# A\n## 1. Purpose\nDoes A.\n")
    pipelines = project / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True)
    (pipelines / "mine.yaml").write_text(_RUN_PIPELINE.format(name="mine"), encoding="utf-8")
    (pipelines / "my_check.yaml").write_text(
        _CHECK_PIPELINE.format(name="my_check"), encoding="utf-8"
    )
    (tmp_path / "beside.yaml").write_text(_RUN_PIPELINE.format(name="beside"), encoding="utf-8")
    (tmp_path / "evil.yaml").write_text(_CHECK_PIPELINE.format(name="evil"), encoding="utf-8")
    app = create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db"))
    with TestClient(app, headers=AUTH) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        yield client, tmp_path


def _run(client: TestClient, name: str):
    return client.post(
        f"/api/v1/pipelines/{name}/run", json={"project": "rest", "spec": "specs/a_spec.md"}
    )


@pytest.mark.parametrize("name", ["validate_only", "mine"])
def test_a_bundled_or_project_pipeline_runs(world: tuple[TestClient, Path], name: str) -> None:
    client, _ = world

    started = _run(client, name)

    assert started.status_code == 200, started.text


@pytest.mark.parametrize(
    "name",
    [
        "beside",
        "beside.yaml",
        ".hidden",
        "mine.yaml",
        "validation_spec_default",
        "nothing_here",
    ],
)
def test_any_other_name_is_not_found(world: tuple[TestClient, Path], name: str) -> None:
    client, tmp_path = world

    refused = _run(client, name)

    assert refused.status_code == 404, refused.text
    assert refused.json()["error_code"] == "PIPELINE_NOT_FOUND"
    assert str(tmp_path) not in refused.json()["detail"]


def test_an_invalid_project_pipeline_is_not_found(world: tuple[TestClient, Path]) -> None:
    client, tmp_path = world
    pipelines = tmp_path / "proj" / ".specweaver" / "pipelines"
    (pipelines / "broken.yaml").write_text("- not a mapping\n", encoding="utf-8")

    refused = _run(client, "broken")

    assert refused.status_code == 404, refused.text
    assert refused.json()["error_code"] == "PIPELINE_NOT_FOUND"


def test_a_pipelines_folder_that_links_outside_is_not_read(
    world: tuple[TestClient, Path],
) -> None:
    client, tmp_path = world
    outside = tmp_path / "outside_pipelines"
    outside.mkdir()
    (outside / "planted.yaml").write_text(_RUN_PIPELINE.format(name="planted"), encoding="utf-8")
    pipelines = tmp_path / "proj" / ".specweaver" / "pipelines"
    for item in pipelines.iterdir():
        item.unlink()
    pipelines.rmdir()
    pipelines.symlink_to(outside)

    refused = _run(client, "planted")

    assert refused.status_code == 404, refused.text


@pytest.mark.parametrize("stored", ["beside", "../../in_project"])
def test_a_parked_run_with_a_name_not_allowed_does_not_resume(
    world: tuple[TestClient, Path], stored: str
) -> None:
    """`../../in_project` lands inside the project, outside `.specweaver/` where agents may write."""
    from specweaver.core.config.paths import state_db_path
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus
    from specweaver.core.flow.engine.store import StateStore

    client, tmp_path = world
    (tmp_path / "proj" / "in_project.yaml").write_text(
        _RUN_PIPELINE.format(name="in_project"), encoding="utf-8"
    )
    StateStore(state_db_path()).save_run(
        PipelineRun(
            run_id="r-old",
            pipeline_name=stored,
            project_name="rest",
            spec_path="specs/a_spec.md",
            status=RunStatus.PARKED,
            started_at="2026-10-22T00:00:00",
            updated_at="2026-10-22T00:00:00",
        )
    )

    refused = client.post("/api/v1/runs/r-old/resume")

    assert refused.status_code == 404, refused.text
    assert refused.json()["error_code"] == "PIPELINE_NOT_FOUND"


def _check(client: TestClient, pipeline: str):
    return client.post(
        "/api/v1/check",
        json={"file": "specs/a_spec.md", "project": "rest", "pipeline": pipeline},
    )


def test_check_loads_a_project_pipeline(world: tuple[TestClient, Path]) -> None:
    client, _ = world

    checked = _check(client, "my_check")

    assert checked.status_code == 200, checked.text
    assert [r["rule_id"] for r in checked.json()["results"]] == ["S01"]


@pytest.mark.parametrize(
    "pipeline", ["../../../evil", "..\\..\\..\\evil", ".hidden", "nothing_here"]
)
def test_check_refuses_a_name_that_is_not_bare_or_not_there(
    world: tuple[TestClient, Path], pipeline: str
) -> None:
    client, tmp_path = world

    refused = _check(client, pipeline)

    assert refused.status_code == 404, refused.text
    assert refused.json()["error_code"] == "PIPELINE_NOT_FOUND"
    assert str(tmp_path) not in refused.json()["detail"]
