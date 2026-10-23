# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How many runs the API takes at once is the user's number, `[serve] max_runs`.

Proves: D-UI-01 FR-7

The real app, settings file and run registry; the pipeline's run is replaced by one that waits, so a
run stays active while the next is asked for.

| Bucket | Case |
|---|---|
| Happy | with `max_runs = 2` two runs start |
| Boundary | with `max_runs = 1` the second run is refused while the first runs |
| Degradation | without `[serve]` a run is refused, naming `serve.max_runs` |
| Hostile | `max_runs = 0` is refused when the settings are read |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import parse_machine_file
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_PIPELINE = """\
name: one_check
version: "1.0"
steps:
  - name: check_spec
    action: validate
    target: spec
"""


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, serve: str) -> TestClient:
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text(serve, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    own = tmp_path / "proj" / ".specweaver" / "pipelines"
    own.mkdir(parents=True)
    (own / "one_check.yaml").write_text(_PIPELINE, encoding="utf-8")

    async def _waits(_self: PipelineRunner, *_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(30)

    monkeypatch.setattr(PipelineRunner, "run", _waits)
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text("# A\n## 1. Purpose\nDoes A.\n")
    client = TestClient(create_app(token=TEST_TOKEN, db=Database(path)), headers=AUTH)
    client.post("/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False})
    return client


def _run(client: TestClient):
    return client.post(
        "/api/v1/pipelines/one_check/run", json={"project": "rest", "spec": "specs/a_spec.md"}
    )


def test_two_runs_start_when_two_are_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _client(tmp_path, monkeypatch, "[serve]\nmax_runs = 2\n") as client:
        codes = [_run(client).status_code, _run(client).status_code]

    assert codes == [200, 200]


def test_a_second_run_is_refused_when_one_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _client(tmp_path, monkeypatch, "[serve]\nmax_runs = 1\n") as client:
        first, second = _run(client), _run(client)

    assert first.status_code == 200
    assert second.status_code == 429 and second.json()["error_code"] == "MAX_CONCURRENT_RUNS"


def test_without_the_setting_a_run_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _client(tmp_path, monkeypatch, "") as client:
        refused = _run(client)

    assert refused.status_code == 409
    assert refused.json()["error_code"] == "SETTING_NOT_SET"
    assert "serve.max_runs" in refused.json()["detail"]


def test_zero_runs_is_refused_when_read() -> None:
    with pytest.raises(SettingsFileError, match="max_runs"):
        parse_machine_file("[serve]\nmax_runs = 0\n", "settings.toml")
