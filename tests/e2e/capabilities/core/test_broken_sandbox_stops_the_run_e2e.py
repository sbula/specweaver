# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run` on a project with a broken `[sandbox]` stops before any step, naming the line.

Proves: TECH-076 FR-4, TECH-076 FR-1

The real CLI, a real `sw init` project and the bundled `validate_only` pipeline. Before this, the
run's isolation lookup swallowed the error and ran with isolation off.

| Bucket | Case |
|---|---|
| Happy | a valid `[sandbox]` runs `validate_only` and records a run |
| Boundary | not applicable — absent and empty sections are proven by `test_project_settings_strict.py` |
| Degradation | not applicable — other lookup failures keep their best effort (design decision 5) |
| Hostile | `execution_mod = "container"`: exit 1, `specweaver.toml:<line>: sandbox.execution_mod` printed, no run recorded |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.core.config.paths import state_db_path
from specweaver.core.flow.engine.store import StateStore
from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e


def _project(tmp_path: Path, sandbox: str) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "sandboxed", "--path", str(project)]).exit_code == 0
    (project / "specs" / "a_spec.md").write_text(
        "# A\n\nThe thing does one job.\n", encoding="utf-8"
    )
    (project / "specweaver.toml").write_text(f"[sandbox]\n{sandbox}\n", encoding="utf-8")
    return project


def _runs() -> int:
    return len(StateStore(state_db_path()).list_runs()) if state_db_path().exists() else 0


@pytest.mark.usefixtures("_mock_db")
def test_a_misspelt_sandbox_key_stops_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path, 'execution_mod = "container"')
    monkeypatch.chdir(project)
    before = _runs()

    result = runner.invoke(
        app, ["run", "validate_only", "specs/a_spec.md", "--project", str(project)]
    )

    assert result.exit_code == 1, result.output
    assert shows(result.output, "specweaver.toml:2: sandbox.execution_mod")
    assert "Traceback" not in result.output
    assert _runs() == before


@pytest.mark.usefixtures("_mock_db")
def test_a_valid_sandbox_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path, 'execution_mode = "host"')
    monkeypatch.chdir(project)
    before = _runs()

    result = runner.invoke(
        app, ["run", "validate_only", "specs/a_spec.md", "--project", str(project)]
    )

    assert "sandbox." not in result.output, result.output
    assert _runs() == before + 1
