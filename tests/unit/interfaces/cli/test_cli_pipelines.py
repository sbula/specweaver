# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for specweaver.interfaces.cli.pipelines — run, resume, pipelines commands.

These are *unit* tests with mocked runner/store/LLM internals.
The integration tests in tests/integration/cli/test_cli_pipelines.py
cover the real CLI via CliRunner with file I/O.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from specweaver.interfaces.cli.pipelines import (
    _create_display,
    _resolve_spec_path,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".sw-test" / "specweaver.db"))
    db = Database(tmp_path / ".sw-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.get_db", lambda: db)
    return db


# ── _resolve_spec_path edge cases ────────────────────────────────────────


class TestResolveSpecPathEdgeCases:
    def test_module_with_underscores(self, tmp_path: Path) -> None:
        result = _resolve_spec_path("new_feature", "my_cool_service", tmp_path)
        assert result == tmp_path / "specs" / "my_cool_service_spec.md"

    def test_module_with_hyphens(self, tmp_path: Path) -> None:
        result = _resolve_spec_path("new_feature", "my-service", tmp_path)
        assert result == tmp_path / "specs" / "my-service_spec.md"

    def test_absolute_path_existing(self, tmp_path: Path) -> None:
        spec = tmp_path / "abs" / "spec.md"
        spec.parent.mkdir()
        spec.write_text("content")
        result = _resolve_spec_path("validate_only", str(spec), tmp_path)
        assert result == spec

    def test_nonexistent_returns_literal(self, tmp_path: Path) -> None:
        result = _resolve_spec_path("validate_only", "ghost.md", tmp_path)
        assert result == Path("ghost.md")


# ── _create_display ──────────────────────────────────────────────────────


class TestCreateDisplayOptions:
    def test_verbose_flag(self) -> None:
        from specweaver.core.flow.engine.display import RichPipelineDisplay

        display = _create_display(verbose=True)
        assert isinstance(display, RichPipelineDisplay)

    def test_json_overrides_verbose(self) -> None:
        from specweaver.core.flow.engine.display import JsonPipelineDisplay

        display = _create_display(use_json=True, verbose=True)
        assert isinstance(display, JsonPipelineDisplay)


# ── sw run — unit tests (mocked internals) ───────────────────────────────


class TestRunPipelineMocked:
    def test_run_with_failed_pipeline_exits_1(self, tmp_path: Path) -> None:
        """A pipeline that ends FAILED should produce exit code 1."""

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "test-proj", "--path", str(project_dir)])

        spec = project_dir / "specs" / "test_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Spec\n## 1. Purpose\nDoes stuff.\n")

        with patch("specweaver.interfaces.cli.pipelines._execute_run") as mock_exec:
            mock_exec.side_effect = typer.Exit(code=1)
            result = runner.invoke(
                app,
                ["run", "validate_only", str(spec), "--project", str(project_dir)],
            )
        assert result.exit_code == 1

    def test_run_file_not_found_exits_1(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "fnf-proj", "--path", str(project_dir)])

        result = runner.invoke(
            app,
            ["run", "validate_only", "missing.md", "--project", str(project_dir)],
        )
        assert result.exit_code == 1

    def test_run_value_error_exits_1(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "ve-proj", "--path", str(project_dir)])

        with patch("specweaver.interfaces.cli.pipelines._execute_run") as mock_exec:
            mock_exec.side_effect = ValueError("bad input!")
            result = runner.invoke(
                app,
                ["run", "validate_only", "x.md", "--project", str(project_dir)],
            )
        assert result.exit_code == 1

    def test_run_generic_exception_exits_1(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "ge-proj", "--path", str(project_dir)])

        with patch("specweaver.interfaces.cli.pipelines._execute_run") as mock_exec:
            mock_exec.side_effect = RuntimeError("unexpected")
            result = runner.invoke(
                app,
                ["run", "validate_only", "x.md", "--project", str(project_dir)],
            )
        assert result.exit_code == 1
        assert "error" in result.output.lower()

    def test_run_success_saves_cache(self, tmp_path: Path) -> None:
        """SF-4: verifies DependencyHasher is called on COMPLETED status."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "test-proj", "--path", str(project_dir)])

        spec = project_dir / "specs" / "test_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Spec\n## 1. Purpose\nDoes stuff.\n")

        with (
            patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
            patch(
                "specweaver.assurance.graph.hasher.DependencyHasher.save_cache"
            ) as mock_save_cache,
        ):
            from unittest.mock import AsyncMock

            from specweaver.core.flow.engine.state import RunStatus

            mock_runner = mock_runner_class.return_value

            # return a mocked final run
            class DummyRun:
                def __init__(self, status: RunStatus) -> None:
                    self.status = status

            mock_runner.run = AsyncMock(return_value=DummyRun(RunStatus.COMPLETED))

            result = runner.invoke(
                app, ["run", "validate_only", str(spec), "--project", str(project_dir)]
            )

        if result.exit_code != 0:
            print(result.stdout)
        assert result.exit_code == 0
        assert mock_save_cache.called
        assert "Topology staleness cache saved successfully" in result.output

    def test_run_success_cache_failure_graceful(self, tmp_path: Path) -> None:
        """SF-4: verifies DependencyHasher exception is logged but doesn't crash."""
        project_dir = tmp_path / "proj_err"
        project_dir.mkdir()
        runner.invoke(app, ["init", "test-proj", "--path", str(project_dir)])

        spec = project_dir / "specs" / "test_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Spec\n## 1. Purpose\nDoes stuff.\n")

        with (
            patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
            patch(
                "specweaver.assurance.graph.hasher.DependencyHasher.save_cache"
            ) as mock_save_cache,
        ):
            from unittest.mock import AsyncMock

            from specweaver.core.flow.engine.state import RunStatus

            mock_runner = mock_runner_class.return_value

            class DummyRun:
                def __init__(self, status: RunStatus) -> None:
                    self.status = status

            mock_runner.run = AsyncMock(return_value=DummyRun(RunStatus.COMPLETED))
            mock_save_cache.side_effect = PermissionError("Cannot write")

            result = runner.invoke(
                app, ["run", "validate_only", str(spec), "--project", str(project_dir)]
            )

        # Pipeline STILL successfully exits with 0 even if caching fails
        if result.exit_code != 0:
            print(result.stdout)
        assert result.exit_code == 0
        assert "Cannot" in result.output
        assert "write" in result.output


# ── sw resume — unit tests ───────────────────────────────────────────────


class TestResumeMocked:
    def test_resume_no_active_project_fails(self) -> None:
        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 1

    def test_resume_unknown_run_id_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _state_path = tmp_path / "pipe_state.db"
        monkeypatch.setattr(
            "specweaver.core.config.paths.state_db_path",
            lambda: _state_path,
        )
        project_dir = tmp_path / "r-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "r-proj", "--path", str(project_dir)])

        result = runner.invoke(app, ["resume", "nonexistent-id"])
        assert result.exit_code == 1

    def test_resume_no_resumable_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _state_path = tmp_path / "pipe_state.db"
        monkeypatch.setattr(
            "specweaver.core.config.paths.state_db_path",
            lambda: _state_path,
        )
        project_dir = tmp_path / "nr-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "nr-proj", "--path", str(project_dir)])

        result = runner.invoke(app, ["resume"])
        if result.exit_code != 0:
            print(result.stdout)
        assert result.exit_code == 0
        assert "no resumable" in result.output.lower()

    def test_resume_success_saves_cache(self, tmp_path: Path, monkeypatch) -> None:
        """SF-4: verifies DependencyHasher is called on Resume COMPLETED."""
        _state_path = tmp_path / "pipe_state.db"
        monkeypatch.setattr(
            "specweaver.core.config.paths.state_db_path",
            lambda: _state_path,
        )
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "test-proj", "--path", str(project_dir)])

        # mock the get_latest_run to return a stub Run
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus

        mock_run_state = PipelineRun(
            run_id="abc1234567890",
            pipeline_name="validate_only",
            project_name="test-proj",
            spec_path=str(project_dir / "specs" / "test_spec.md"),
            status=RunStatus.PARKED,
            started_at="",
            updated_at="",
        )

        with (
            patch("specweaver.interfaces.cli.pipelines._get_state_store") as mock_get_store,
            patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
            patch(
                "specweaver.assurance.graph.hasher.DependencyHasher.save_cache"
            ) as mock_save_cache,
        ):
            mock_store = mock_get_store.return_value
            mock_store.load_run.return_value = mock_run_state

            mock_runner = mock_runner_class.return_value

            class DummyRun:
                pass

            mock_run = DummyRun()
            mock_run.status = RunStatus.COMPLETED

            from unittest.mock import AsyncMock

            mock_runner.resume = AsyncMock(return_value=mock_run)

            result = runner.invoke(app, ["resume", "abc1234567890"])

        if result.exit_code != 0:
            print(result.stdout)
        assert result.exit_code == 0
        assert mock_save_cache.called


# ── sw pipelines ─────────────────────────────────────────────────────────


class TestPipelinesCommand:
    def test_pipelines_output_contains_names(self) -> None:
        result = runner.invoke(app, ["pipelines"])
        if result.exit_code != 0:
            print(result.stdout)
        assert result.exit_code == 0
        # Should list at least validate_only or new_feature
        output_lower = result.output.lower()
        assert "validate" in output_lower or "pipeline" in output_lower
