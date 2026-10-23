# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw resume --model` hands the run model to the router, like `sw run` does.

Proves: C-FLOW-13 FR-16

| Bucket | Case |
|---|---|
| Happy | `sw resume <id> --model m@gb10` → the models are wired with that run model |
| Boundary | `sw resume <id>` with no flag → wired with none, so the files decide |
| Degradation | not applicable — the router's own refusals are proven in `test_run_model.py` |
| Hostile | `--model gpt-6` → refused before the run is even loaded |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from tests.rendering import shows
from typer.testing import CliRunner

from specweaver.core.config.llm_settings import RoleEntry
from specweaver.core.flow.engine.state import PipelineRun, RunStatus
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".sw" / "specweaver.db"))
    db = Database(tmp_path / ".sw" / "specweaver.db")
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
    return db


def _resume(tmp_path: Path, *flags: str):
    project = tmp_path / "res-proj"
    project.mkdir()
    runner.invoke(app, ["init", "res-proj", "--path", str(project)])
    spec = project / "specs" / "a_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text("# A\n", encoding="utf-8")
    parked = PipelineRun(
        run_id="abc1234567890",
        pipeline_name="validate_only",
        project_name="res-proj",
        spec_path=str(spec),
        status=RunStatus.PARKED,
        started_at="",
        updated_at="",
    )

    class _Done:
        status = RunStatus.COMPLETED
        step_records = ()

    with (
        patch("specweaver.core.flow.interfaces.cli._get_state_store") as store,
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as runner_class,
        patch("specweaver.assurance.graph.hasher.DependencyHasher.save_cache"),
        patch("specweaver.core.flow.interfaces.cli.build_run_or_exit") as wire,
    ):
        store.return_value.load_run.return_value = parked
        runner_class.return_value.resume = AsyncMock(return_value=_Done())
        result = runner.invoke(app, ["resume", "abc1234567890", *flags])
    return result, wire, store


class TestResumeRunModel:
    def test_the_run_model_reaches_the_router(self, tmp_path: Path) -> None:
        result, wire, _store = _resume(tmp_path, "--model", "qwen3-coder-next@gb10")

        assert result.exit_code == 0, result.output
        assert wire.call_args.kwargs["run_model"] == RoleEntry.model_validate(
            "qwen3-coder-next@gb10"
        )

    def test_without_the_flag_the_files_decide(self, tmp_path: Path) -> None:
        result, wire, _store = _resume(tmp_path)

        assert result.exit_code == 0, result.output
        assert wire.call_args.kwargs["run_model"] is None

    def test_a_model_without_a_server_is_refused_before_the_run_loads(self, tmp_path: Path) -> None:
        result, wire, store = _resume(tmp_path, "--model", "gpt-6")

        assert result.exit_code == 1
        assert shows(result.output, "model@server")
        store.return_value.load_run.assert_not_called()
        wire.assert_not_called()
