# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An API run honours its topology selector and can start a feature whose spec does not exist yet.

Proves: TECH-077 FR-7

A real app, database and project with two modules; the runner's `run` is replaced only to capture
the context a door built.

| Bucket | Case |
|---|---|
| Happy | `selector: nhop` gives a different topology slice than `direct` |
| Boundary | `new_feature` with a module name starts; its spec is `specs/<name>_spec.md` inside the project |
| Degradation | a validate run of a spec that does not exist is still refused with 404 |
| Hostile | `new_feature` with `../../escape` answers 400 and starts nothing |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
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


_MACHINE = """schema_version = 1

[serve]
max_runs = 2

[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "local-model@local", max_output_tokens = 4096 }

[brake]
hosted_spend_per_run = 1
tokens_per_run = 100000
agent_turns = 5
"""


@pytest.fixture()
def world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path, list[Any]]]:
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "proj"
    (root / ".specweaver" / "pipelines").mkdir(parents=True)
    (root / ".specweaver" / "pipelines" / "one_check.yaml").write_text(_PIPELINE)
    (root / "specs").mkdir()
    (root / "specs" / "orders_spec.md").write_text("# Orders\n## 1. Purpose\nOrders.\n")
    (root / "context.yaml").write_text("name: orders\narchetype: pure-logic\n", encoding="utf-8")
    for name, consumes in (("billing", "orders"), ("ledger", "billing")):
        (root / name).mkdir()
        (root / name / "context.yaml").write_text(
            f"name: {name}\narchetype: pure-logic\nconsumes:\n  - {consumes}\n", encoding="utf-8"
        )
    contexts: list[Any] = []

    async def _capture(self: PipelineRunner, *_args: object, **_kwargs: object) -> None:
        contexts.append(self._context)

    monkeypatch.setattr(PipelineRunner, "run", _capture)
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    with TestClient(create_app(token=TEST_TOKEN, db=Database(path)), headers=AUTH) as client:
        client.post("/api/v1/projects", json={"name": "rest", "path": str(root), "scaffold": False})
        yield client, root, contexts


def _context(contexts: list[Any]) -> Any:
    for _ in range(100):
        if contexts:
            return contexts.pop()
        time.sleep(0.02)
    raise AssertionError("no run started")


def _run(client: TestClient, name: str, spec: str, **extra: str) -> Any:
    return client.post(
        f"/api/v1/pipelines/{name}/run", json={"project": "rest", "spec": spec, **extra}
    )


def _slice(topology: Any) -> set[str]:
    return {context.name for context in topology or []}


def test_the_selector_chooses_the_slice(world) -> None:
    client, _root, contexts = world

    assert _run(client, "one_check", "specs/orders_spec.md", selector="direct").status_code == 200
    direct = _context(contexts).graph.topology
    assert _run(client, "one_check", "specs/orders_spec.md", selector="nhop").status_code == 200
    nhop = _context(contexts).graph.topology

    assert direct is not None
    assert _slice(nhop) != _slice(direct)


def test_new_feature_starts_with_a_spec_still_to_write(world) -> None:
    client, root, contexts = world

    answer = _run(client, "new_feature", "invoicing")

    assert answer.status_code == 200, answer.text
    assert _context(contexts).spec_path == root.resolve() / "specs" / "invoicing_spec.md"


def test_a_missing_spec_is_still_refused_for_other_pipelines(world) -> None:
    client, _root, contexts = world

    answer = _run(client, "one_check", "specs/nothing_spec.md")

    assert answer.status_code == 404, answer.text
    assert contexts == []


def test_new_feature_cannot_leave_the_project(world) -> None:
    client, _root, contexts = world

    answer = _run(client, "new_feature", "../../escape")

    assert answer.status_code == 400, answer.text
    assert contexts == []
