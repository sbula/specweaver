# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run` and `sw resume` give a model-free pipeline no router and attach the analyzers.

A real registered project; only the runner is replaced, to capture the context it is given.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from specweaver.core.flow.interfaces.cli import _execute_run, resume
from specweaver.interfaces.cli.main import app
from specweaver.workspace.analyzers.factory import AnalyzerFactory

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    assert runner.invoke(app, ["init", tmp_path.name.lower(), "--path", str(root)]).exit_code == 0
    (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
    return root


def _context_of(runner_class: MagicMock) -> object:
    runner_class.assert_called_once()
    return runner_class.call_args.args[1]


def test_a_model_free_run_gets_no_router(project: Path) -> None:
    with patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class:
        runner_class.return_value.run = AsyncMock()
        _execute_run(
            pipeline="validate_only",
            spec_or_module=str(project / "spec.md"),
            verbose=False,
            json_output=False,
            selector="direct",
            project=str(project),
            resume_id=None,
        )

    context = _context_of(runner_class)
    assert context.model.llm_router is None
    assert context.analysis.analyzer_factory is AnalyzerFactory


def test_a_model_free_resume_gets_no_router(project: Path, tmp_path: Path) -> None:
    run_state = MagicMock(
        run_id="run-123",
        spec_path=str(project / "spec.md"),
        pipeline_name="validate_only",
        project_name=tmp_path.name.lower(),
    )
    with (
        patch("specweaver.core.flow.interfaces.cli._get_state_store") as store,
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class,
    ):
        store.return_value.load_run.return_value = run_state
        runner_class.return_value.resume = AsyncMock()
        resume(run_id="run-123", verbose=False, json_output=False, model=None)

    context = _context_of(runner_class)
    assert context.model.llm_router is None
    assert context.analysis.analyzer_factory is AnalyzerFactory


def test_an_empty_spec_stops_the_run(project: Path) -> None:
    (project / "empty.md").touch()

    with pytest.raises(typer.Exit) as exit_:
        _execute_run(
            pipeline="validate_only",
            spec_or_module=str(project / "empty.md"),
            project=str(project),
            resume_id=None,
            verbose=False,
            json_output=False,
            selector="direct",
        )

    assert exit_.value.exit_code == 1
