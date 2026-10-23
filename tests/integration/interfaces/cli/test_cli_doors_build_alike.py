# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every CLI door hands its run the same parts, from the one project the run is for.

Proves: TECH-077 FR-2, TECH-077 FR-3, TECH-077 FR-4

The real CLI over real `sw init` projects, settings files, stored standards and a rule file. The
model is doubled; the runner is replaced only to capture the context a door hands it, except where
the run itself must fail.

| Bucket | Case |
|---|---|
| Happy | `sw implement`, `sw review`, `sw draft` each get the rule file, the standards and the sections |
| Boundary | on a high-DAL project, the read-only `sw review` gets no per-run worktree; `sw implement` and `sw draft` do |
| Degradation | `sw implement` and `sw draft` on a high-DAL project with no git stop, naming the worktree, no traceback |
| Hostile | `sw implement` in project B while project A is active takes B's standards, never A's |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration

_MACHINE = """schema_version = 1

[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "local-model@local", max_output_tokens = 4096 }
"""

_SETTINGS = """[[docs.rule]]
paths = ["docs/**"]
access = "open"

[sandbox]
enforce_worktree_isolation = true
"""


@pytest.fixture(autouse=True)
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    data = tmp_path / ".specweaver-test"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    (data / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    return data


def _project(tmp_path: Path, name: str, *, rule: str, standard: str) -> Path:
    from specweaver.core.config.database import Database
    from specweaver.workspace.store import WorkspaceRepository

    root = tmp_path / name
    root.mkdir()
    assert runner.invoke(app, ["init", name, "--path", str(root)]).exit_code == 0
    (root / "CONSTITUTION.md").write_text(f"# Rules\n{rule}\n", encoding="utf-8")
    (root / "specweaver.toml").write_text(_SETTINGS, encoding="utf-8")
    (root / "context.yaml").write_text(
        f"name: {name}\narchetype: pure-logic\noperational:\n  dal_level: DAL_B\n", encoding="utf-8"
    )
    (root / ".git").mkdir()
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")

    async def _save() -> None:
        async with db.async_session_scope() as session:
            await WorkspaceRepository(session).save_standard(
                name, ".", "python", "naming", {"style": standard}, 0.9
            )

    asyncio.run(_save())
    return root


@pytest.fixture()
def bee(tmp_path: Path) -> Path:
    """Project B, the one every command below is run on."""
    root = _project(tmp_path, "bee", rule="Bee rule.", standard="bee_case")
    _project(tmp_path, "ay", rule="Ay rule.", standard="ay_case")  # registered last: active
    return root


def _captured(args: list[str]) -> object:
    from specweaver.core.flow.engine.state import RunStatus

    state = MagicMock(status=RunStatus.COMPLETED, step_records=[])
    with (
        doubled_llm(MagicMock()),
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class,
    ):
        runner_class.return_value.run = AsyncMock(return_value=state)
        result = runner.invoke(app, args)
    assert runner_class.called, result.output
    return runner_class.call_args.args[1]


def _implement(bee: Path) -> object:
    return _captured(["implement", str(bee / "specs" / "greeter_spec.md"), "--project", str(bee)])


def _review(bee: Path) -> object:
    return _captured(["review", str(bee / "specs" / "greeter_spec.md"), "--project", str(bee)])


def _draft(bee: Path) -> object:
    return _captured(["draft", "orders", "--project", str(bee)])


@pytest.mark.parametrize(
    "door", [_implement, _review, _draft], ids=["implement", "review", "draft"]
)
def test_every_door_gets_every_part_from_its_project(door, bee: Path) -> None:
    context = door(bee)

    assert "Bee rule." in (context.guidance.constitution or "")
    assert "bee_case" in (context.guidance.standards or "")
    assert "ay_case" not in (context.guidance.standards or "")
    assert [rule.access for rule in context.isolation.doc_policy.rule] == ["open"]
    assert context.isolation.enforce_isolation is True


@pytest.mark.parametrize(
    ("door", "per_run"),
    [(_implement, True), (_review, False), (_draft, True)],
    ids=["implement", "review", "draft"],
)
def test_only_doors_that_write_get_a_per_run_worktree(door, per_run: bool, bee: Path) -> None:
    assert door(bee).isolation.session_isolation is per_run


def test_a_draft_still_talks_to_the_terminal(bee: Path) -> None:
    from specweaver.interfaces.cli.hitl_provider import HITLProvider

    assert isinstance(_draft(bee).context_provider, HITLProvider)


@pytest.mark.parametrize(
    "args",
    [["implement", "specs/greeter_spec.md"], ["draft", "orders"]],
    ids=["implement", "draft"],
)
def test_a_writing_door_without_git_stops_naming_the_worktree(
    args: list[str], bee: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (bee / ".git").rmdir()
    monkeypatch.chdir(bee)

    with doubled_llm(MagicMock()):
        result = runner.invoke(app, [*args, "--project", str(bee)])

    assert result.exit_code == 1, result.output
    assert "could not start" in " ".join(result.output.split())
    assert result.exception is None or isinstance(result.exception, SystemExit)
