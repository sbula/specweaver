# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The same pipeline on the same project gets the same run through `sw run` and the API.

Proves: TECH-077 NFR-1

One database and one project, reached through the real CLI and the real app. The runner's `run` is
replaced only to capture the context each door built.

| Bucket | Case |
|---|---|
| Happy | rule file, standards, sections, isolation and topology are equal through both doors |
| Boundary | a high-DAL project: both doors give the per-run worktree and the same allow-list |
| Degradation | not applicable — each door's refusals are proven by its own tests |
| Hostile | not applicable — the claim is agreement, not input handling |
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.interfaces.api.app import create_app
from specweaver.interfaces.cli.main import app
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


def test_sw_run_and_the_api_build_the_same_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.core.flow.engine.state import RunStatus
    from specweaver.workspace.store import WorkspaceRepository

    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text("[serve]\nmax_runs = 2\n", encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "agree"
    root.mkdir()
    assert CliRunner().invoke(app, ["init", "agree", "--path", str(root)]).exit_code == 0
    (root / ".specweaver" / "pipelines").mkdir(parents=True, exist_ok=True)
    (root / ".specweaver" / "pipelines" / "one_check.yaml").write_text(_PIPELINE)
    (root / "specs" / "orders_spec.md").write_text("# Orders\n## 1. Purpose\nOrders.\n")
    (root / "CONSTITUTION.md").write_text("# Rules\nAgree.\n", encoding="utf-8")
    (root / "specweaver.toml").write_text(
        '[[docs.rule]]\npaths = ["docs/**"]\naccess = "open"\n', encoding="utf-8"
    )
    (root / "context.yaml").write_text(
        "name: orders\narchetype: pure-logic\noperational:\n  dal_level: DAL_B\n", encoding="utf-8"
    )
    (root / "billing").mkdir()
    (root / "billing" / "context.yaml").write_text(
        "name: billing\narchetype: pure-logic\nconsumes:\n  - orders\n", encoding="utf-8"
    )
    (root / ".git").mkdir(exist_ok=True)

    async def _standard() -> None:
        async with db.async_session_scope() as session:
            await WorkspaceRepository(session).save_standard(
                "agree", ".", "python", "naming", {"style": "agree_case"}, 0.9
            )

    asyncio.run(_standard())
    contexts: list[Any] = []

    async def _capture(self: PipelineRunner, *_a: object, **_k: object) -> Any:
        contexts.append(self._context)
        return type("Run", (), {"status": RunStatus.COMPLETED, "step_records": []})()

    monkeypatch.setattr(PipelineRunner, "run", _capture)
    monkeypatch.setattr(
        "specweaver.assurance.graph.hasher.DependencyHasher.save_cache", lambda _s: None
    )
    spec = root / "specs" / "orders_spec.md"
    pipeline = root / ".specweaver" / "pipelines" / "one_check.yaml"
    cli = CliRunner().invoke(app, ["run", str(pipeline), str(spec), "--project", str(root)])
    assert cli.exit_code == 0, cli.output
    with TestClient(create_app(token=TEST_TOKEN, db=db), headers=AUTH) as client:
        answer = client.post(
            "/api/v1/pipelines/one_check/run",
            json={"project": "agree", "spec": "specs/orders_spec.md"},
        )
        assert answer.status_code == 200, answer.text
        for _ in range(100):
            if len(contexts) == 2:
                break
            time.sleep(0.02)

    by_cli, by_api = contexts
    assert "Agree." in (by_cli.guidance.constitution or "")
    assert by_cli.isolation.session_isolation is True
    assert by_api.guidance == by_cli.guidance
    assert by_api.isolation == by_cli.isolation
    assert by_api.graph.topology == by_cli.graph.topology
