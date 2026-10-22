# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run the API starts or resumes reads the project's doc policy, as one from the CLI does.

Proves: C-EXEC-08 NFR-1
Proves: C-EXEC-08 FR-1
Proves: C-FLOW-11 FR-6
Proves: D-INTL-08 FR-2

| Bucket | Case |
|---|---|
| Happy | a project's `[docs]` rule is on the context of a run the API starts |
| Boundary | a parked run resumed by a gate decision reads the policy again: a `[docs]` broken since the start refuses the resume |
| Degradation | not applicable — a missing file is the empty policy, proven by the CLI tests |
| Hostile | a broken `[docs]` refuses the start with `DOC_POLICY`, naming the line, and no run starts |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_GOOD = '[[docs.rule]]\npaths = ["docs/user_guides/**"]\naccess = "open"\n'
_BROKEN = '[[docs.rule]]\npaths = ["docs/**"]\naccess = "wide"\n'
_PIPELINE = """name: two_steps
version: "1.0"
steps:
  - name: first
    action: bash
    target: script
    params: {script: s.sh, args: ["one"]}
    gate: {type: hitl, condition: completed}
  - name: second
    action: bash
    target: script
    params: {script: s.sh, args: ["two"]}
"""


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Path]]:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    (data / "settings.toml").write_text("[serve]\nmax_runs = 3\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    own = tmp_path / "proj" / ".specweaver" / "pipelines"
    own.mkdir(parents=True)
    (own / "two_steps.yaml").write_text(_PIPELINE, encoding="utf-8")
    bootstrap_database(str(data / "specweaver.db"))
    project = tmp_path / "proj"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "a_spec.md").write_text("# A\n", encoding="utf-8")
    scripts = project / ".specweaver" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "s.sh").write_text('#!/usr/bin/env bash\necho "$1" >> steps.log\n', encoding="utf-8")
    with TestClient(
        create_app(token=TEST_TOKEN, db=Database(data / "specweaver.db")), headers=AUTH
    ) as client:
        client.post(
            "/api/v1/projects", json={"name": "rest", "path": str(project), "scaffold": False}
        )
        yield client, project


def _start(client: TestClient) -> Any:
    return client.post(
        "/api/v1/pipelines/two_steps/run", json={"project": "rest", "spec": "specs/a_spec.md"}
    )


def test_a_started_run_carries_the_projects_rules(world: tuple[TestClient, Path]) -> None:
    client, project = world
    (project / "specweaver.toml").write_text(_GOOD, encoding="utf-8")

    with patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class:
        runner_class.return_value.run = AsyncMock()
        _start(client)

    rules = runner_class.call_args.args[1].isolation.doc_policy.rule
    assert [rule.access for rule in rules] == ["open"]


def test_a_broken_docs_section_refuses_the_start(world: tuple[TestClient, Path]) -> None:
    client, project = world
    (project / "specweaver.toml").write_text(_BROKEN, encoding="utf-8")

    answer = _start(client)

    assert answer.status_code == 500, answer.json()
    assert answer.json()["error_code"] == "DOC_POLICY"
    assert "specweaver.toml:3:" in answer.json()["detail"]
    assert not (project / "steps.log").exists()


def test_a_resume_reads_the_policy_again(world: tuple[TestClient, Path]) -> None:
    client, project = world
    run_id = _start(client).json()["run_id"]
    for _ in range(100):
        if client.get(f"/api/v1/runs/{run_id}").json().get("status") in {"parked", "failed"}:
            break
        time.sleep(0.05)
    (project / "specweaver.toml").write_text(_BROKEN, encoding="utf-8")

    answer = client.post(f"/api/v1/runs/{run_id}/gate", json={"action": "approve"})

    assert answer.status_code == 500, answer.json()
    assert answer.json()["error_code"] == "DOC_POLICY"
    assert (project / "steps.log").read_text(encoding="utf-8").split() == ["one"]


def test_a_started_run_carries_the_projects_autonomy(world: tuple[TestClient, Path]) -> None:
    """C-FLOW-11 FR-6."""
    client, project = world
    (project / "specweaver.toml").write_text('[autonomy]\nmode = "agentic"\n', encoding="utf-8")

    with patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class:
        runner_class.return_value.run = AsyncMock()
        _start(client)

    assert runner_class.call_args.args[1].isolation.autonomy.mode == "agentic"


def test_a_broken_autonomy_section_refuses_the_start(world: tuple[TestClient, Path]) -> None:
    client, project = world
    (project / "specweaver.toml").write_text('[autonomy]\nmode = "free"\n', encoding="utf-8")

    answer = _start(client)

    assert answer.status_code == 500, answer.json()
    assert answer.json()["error_code"] == "AUTONOMY_POLICY"
    assert "specweaver.toml:2:" in answer.json()["detail"]


def test_a_started_run_carries_the_projects_language(world: tuple[TestClient, Path]) -> None:
    """D-INTL-08 FR-2."""
    client, project = world
    (project / "specweaver.toml").write_text(
        '[implement]\nlanguage = "typescript"\n', encoding="utf-8"
    )

    with patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class:
        runner_class.return_value.run = AsyncMock()
        _start(client)

    assert runner_class.call_args.args[1].isolation.language == "typescript"
