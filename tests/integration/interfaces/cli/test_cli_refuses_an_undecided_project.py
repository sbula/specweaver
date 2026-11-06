# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run` and `sw implement` refuse a project whose root does not decide its language.

Proves: TECH-079 FR-8

A real project from `sw init`, real settings; the refusal comes before any step runs.

| Bucket | Case |
|---|---|
| Happy | with `[implement] language` set, the same mixed root runs `sw run` |
| Boundary | a root with no build file and no code file is refused too, naming the setting |
| Degradation | a door that does not need the language (`sw draft`) builds its run and keeps the refusal |
| Hostile | pyproject.toml beside package.json and tsconfig.json: both commands print the refusal, exit 1, and run no step; with session isolation on, any door stops |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from specweaver.core.config.settings import SpecWeaverSettings
from specweaver.interfaces.cli.main import app
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration
runner = CliRunner()

_PIPELINE = """name: one_step
version: "1.0"
steps:
  - name: only
    action: bash
    target: script
    params: {script: s.sh, args: ["ran"]}
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    root = tmp_path / "proj"
    root.mkdir()
    assert runner.invoke(app, ["init", "mixed", "--path", str(root)]).exit_code == 0
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    script = root / ".specweaver" / "scripts" / "s.sh"
    script.write_text('#!/usr/bin/env bash\necho "$1" >> steps.log\n', encoding="utf-8")
    (root / "one_step.yaml").write_text(_PIPELINE, encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def _mixed(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "tsconfig.json").write_text("{}", encoding="utf-8")


def _run(project: Path):
    return runner.invoke(
        app, ["run", "one_step.yaml", "specs/greeter_spec.md", "--project", str(project)]
    )


def test_sw_run_refuses_a_mixed_root(project: Path) -> None:
    _mixed(project)

    result = _run(project)

    assert result.exit_code == 1, result.output
    assert shows(result.output, "python (pyproject.toml) and typescript (package.json)")
    assert shows(result.output, "set [implement] language in specweaver.toml")
    assert not (project / "steps.log").exists()


def test_sw_run_refuses_a_root_with_nothing_to_decide_by(project: Path) -> None:
    result = _run(project)

    assert result.exit_code == 1, result.output
    assert shows(result.output, "no build file and no code file")


def test_the_language_setting_lets_sw_run_start(project: Path) -> None:
    _mixed(project)
    (project / "specweaver.toml").write_text('[implement]\nlanguage = "python"\n')

    result = _run(project)

    assert result.exit_code == 0, result.output
    assert (project / "steps.log").read_text(encoding="utf-8") == "ran\n"


def test_sw_implement_refuses_a_mixed_root(project: Path) -> None:
    _mixed(project)

    with (
        doubled_llm(MagicMock()),
        patch(
            "specweaver.core.config.bootstrap.settings_loader.load_settings",
            return_value=SpecWeaverSettings(),
        ),
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class,
    ):
        result = runner.invoke(
            app, ["implement", "specs/greeter_spec.md", "--project", str(project)]
        )

    assert result.exit_code == 1, result.output
    assert shows(result.output, "set [implement] language in specweaver.toml")
    assert not runner_class.called


def _build(project: Path):
    from specweaver.core.flow.engine.parser import load_pipeline
    from specweaver.interfaces.run_doors.run_doors import build_run_or_exit

    pipeline = load_pipeline(project / "one_step.yaml")
    return build_run_or_exit(project, project / "specs" / "greeter_spec.md", pipeline)


def test_a_door_that_does_not_need_the_language_builds_its_run(project: Path) -> None:
    _mixed(project)

    context = _build(project)

    assert context.isolation.profile is None
    assert "set [implement] language" in (context.isolation.undecided or "")


def test_any_door_stops_when_session_isolation_needs_the_language(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Q1 [agreed 2026-11-06]: the run never goes on without the isolation it asked for."""
    _mixed(project)
    (project / "specweaver.toml").write_text("[sandbox]\nenforce_session_isolation = true\n")

    with pytest.raises(typer.Exit) as caught:
        _build(project)

    assert caught.value.exit_code == 1
    assert shows(capsys.readouterr().out, "set [implement] language in specweaver.toml")
