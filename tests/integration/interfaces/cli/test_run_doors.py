# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The CLI turns every error of the run builder into a refusal, never a traceback.

Proves: TECH-077 FR-2, TECH-077 FR-5

A real `sw init` project and database; nothing is doubled.

| Bucket | Case |
|---|---|
| Happy | a registered folder gives a context with the project's rule file |
| Boundary | a pipeline with no model step needs no model settings |
| Degradation | a worktree that cannot start, or a resumed run's worktree that is gone, is refused |
| Hostile | a broken `[sandbox]` refuses naming the key; an unregistered folder refuses naming `sw init` |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import typer
from typer.testing import CliRunner

from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
from specweaver.interfaces.cli import run_doors
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    data = tmp_path / ".specweaver-test"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    assert runner.invoke(app, ["init", "doors", "--path", str(root)]).exit_code == 0
    (root / "CONSTITUTION.md").write_text("# Rules\nKeep it small.\n", encoding="utf-8")
    (root / "specs" / "orders_spec.md").write_text("# Orders\n", encoding="utf-8")
    return root


def _validate(root: Path) -> PipelineDefinition:
    return PipelineDefinition.create_single_step("one", StepAction.VALIDATE, StepTarget.SPEC)


def test_a_registered_folder_gets_its_rule_file(project: Path) -> None:
    context = run_doors.build_run_or_exit(
        project, project / "specs" / "orders_spec.md", _validate(project)
    )

    assert "Keep it small." in (context.guidance.constitution or "")
    assert context.model.llm_router is None


def test_an_unregistered_folder_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stray = tmp_path / "stray"
    stray.mkdir()

    with pytest.raises(typer.Exit) as exit_:
        run_doors.build_run_or_exit(stray, stray / "x_spec.md", _validate(stray))

    assert exit_.value.exit_code == 1
    assert "sw init" in " ".join(capsys.readouterr().out.split())


def test_a_broken_setting_is_refused(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "specweaver.toml").write_text('[sandbox]\nexecution_mod = "container"\n')

    with pytest.raises(typer.Exit) as exit_:
        run_doors.build_run_or_exit(
            project, project / "specs" / "orders_spec.md", _validate(project)
        )

    assert exit_.value.exit_code == 1
    assert "execution_mod" in capsys.readouterr().out


def test_a_worktree_that_cannot_start_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    from specweaver.core.flow.engine.session import SessionWorktreeError

    error = SessionWorktreeError("session isolation could not start (not a git repository).")

    with pytest.raises(typer.Exit) as exit_:
        run_doors.refuse_unstarted_worktree(error)

    assert exit_.value.exit_code == 1
    assert "could not start" in capsys.readouterr().out


_TWO_STEPS = """name: two_steps
version: "1.0"
steps:
  - name: first
    action: validate
    target: spec
  - name: second
    action: validate
    target: spec
"""


def test_a_resume_whose_worktree_is_gone_is_refused(project: Path) -> None:
    """A run parked before its project escalated has no session worktree to continue in."""
    from specweaver.core.config.paths import state_db_path
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepRecord
    from specweaver.core.flow.engine.store import StateStore

    (project / ".git").mkdir()
    (project / "context.yaml").write_text("operational:\n  dal_level: DAL_B\n", encoding="utf-8")
    (project / "two_steps.yaml").write_text(_TWO_STEPS, encoding="utf-8")
    StateStore(state_db_path()).save_run(
        PipelineRun(
            run_id="gone-0001",
            pipeline_name="two_steps",
            project_name="doors",
            spec_path=str(project / "specs" / "orders_spec.md"),
            status=RunStatus.PARKED,
            current_step=1,
            step_records=[StepRecord(step_name="first"), StepRecord(step_name="second")],
            started_at="",
            updated_at="",
        )
    )

    result = runner.invoke(app, ["resume", "gone-0001"])

    assert result.exit_code == 1, result.output
    assert "is gone" in " ".join(result.output.split())
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_no_folder_means_the_active_project(project: Path) -> None:
    context = run_doors.build_run_or_exit(
        None, project / "specs" / "orders_spec.md", _validate(project)
    )

    assert context.project_path == project.resolve()


_MACHINE = """schema_version = 1

[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "local-model@local", max_output_tokens = 4096 }
"""


def test_a_router_tells_its_missing_calls_at_the_end(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock

    from specweaver.infrastructure.llm.interfaces import command
    from tests.scripted_llm import doubled_llm

    (tmp_path / ".specweaver-test" / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    told: list[object] = []
    monkeypatch.setattr(command, "tell_missing_at_end", told.append)
    review = PipelineDefinition.create_single_step("one", StepAction.REVIEW, StepTarget.SPEC)

    with doubled_llm(MagicMock()):
        context = run_doors.build_run_or_exit(project, project / "specs" / "orders_spec.md", review)

    assert context.model.llm_router is not None
    assert told == [context.model.llm_router]
