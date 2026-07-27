# mypy: ignore-errors
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

from specweaver.core.flow.interfaces.cli import (
    _create_display,
    _resolve_spec_path,
)
from specweaver.interfaces.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    from specweaver.core.config.database import Database
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(tmp_path / ".sw-test" / "specweaver.db"))
    db = Database(tmp_path / ".sw-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.core.config.db_bootstrap.get_db", lambda: db)
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

        with patch("specweaver.core.flow.interfaces.cli._execute_run") as mock_exec:
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

        with patch("specweaver.core.flow.interfaces.cli._execute_run") as mock_exec:
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

        with patch("specweaver.core.flow.interfaces.cli._execute_run") as mock_exec:
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


# ── INT-US-09 T2: composition-root wires config into RunContext ──────────


class TestRunContextConfigWiring:
    """INT-US-09 T2: the `sw run`/`resume` composition roots must populate
    `RunContext.config` so `context.config.sandbox` (the isolation policy) is
    readable at pipeline runtime — previously it was left None on these paths."""

    def _run_and_capture_context(self, tmp_path: Path):
        from unittest.mock import AsyncMock

        from specweaver.core.flow.engine.state import RunStatus

        # Register the project under its directory basename so load_settings
        # (keyed on project_path.name) resolves it — mirrors real usage where
        # the run's --project resolves to the registered project.
        project_dir = tmp_path / "cfg-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "cfg-proj", "--path", str(project_dir)])
        spec = project_dir / "specs" / "test_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Spec\n## 1. Purpose\nDoes stuff.\n")

        with (
            patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
            patch("specweaver.assurance.graph.hasher.DependencyHasher.save_cache"),
        ):
            mock_runner = mock_runner_class.return_value

            class DummyRun:
                status = RunStatus.COMPLETED

            mock_runner.run = AsyncMock(return_value=DummyRun())
            result = runner.invoke(
                app, ["run", "validate_only", str(spec), "--project", str(project_dir)]
            )
            assert result.exit_code == 0, result.stdout
            # context is positional arg index 1 to PipelineRunner(pipeline_def, context, ...)
            return mock_runner_class.call_args.args[1]

    def test_run_resolves_isolation_policy_default_off(self, tmp_path: Path) -> None:
        context = self._run_and_capture_context(tmp_path)
        # Policy resolved onto a dedicated flag; default off (backward-compatible).
        assert context.enforce_isolation is False

    def test_run_stays_container_neutral(self, tmp_path: Path) -> None:
        # Guard (user decision): we do NOT populate context.config on sw run, so
        # B-EXEC-01 container QA stays dormant on this path — INT-US-09 is
        # strictly container-free. The isolation policy rides on its own flag.
        context = self._run_and_capture_context(tmp_path)
        assert context.config is None

    def test_run_settings_failure_leaves_config_none_and_does_not_crash(
        self, tmp_path: Path
    ) -> None:
        """[Graceful Degradation] a settings-resolution failure must not crash a run —
        config stays None and the sandbox policy falls back to its default (off)."""
        from unittest.mock import AsyncMock

        from specweaver.core.flow.engine.state import RunStatus

        project_dir = tmp_path / "cfg-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "cfg-proj", "--path", str(project_dir)])
        spec = project_dir / "specs" / "test_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Spec\n## 1. Purpose\nDoes stuff.\n")

        with (
            patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
            patch("specweaver.assurance.graph.hasher.DependencyHasher.save_cache"),
            patch(
                "specweaver.core.config.settings_loader.load_settings",
                side_effect=RuntimeError("settings boom"),
            ),
        ):
            mock_runner = mock_runner_class.return_value

            class DummyRun:
                status = RunStatus.COMPLETED

            mock_runner.run = AsyncMock(return_value=DummyRun())
            result = runner.invoke(
                app, ["run", "validate_only", str(spec), "--project", str(project_dir)]
            )

        assert result.exit_code == 0, result.stdout  # run did NOT crash
        context = mock_runner_class.call_args.args[1]
        assert context.enforce_isolation is False  # graceful fallback to default (off)
        assert context.config is None


class TestResumeContextConfigWiring:
    """INT-US-09 T2: the `sw resume` composition root must also populate
    `RunContext.config` (mirrors the run path)."""

    def _resume_and_capture_context(self, tmp_path: Path, monkeypatch):
        from unittest.mock import AsyncMock

        from specweaver.core.flow.engine.state import PipelineRun, RunStatus

        _state_path = tmp_path / "pipe_state.db"
        monkeypatch.setattr(
            "specweaver.core.config.paths.state_db_path", lambda: _state_path
        )
        # dir basename == registered name so load_settings resolves it.
        project_dir = tmp_path / "res-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "res-proj", "--path", str(project_dir)])
        spec = project_dir / "specs" / "test_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Spec\n## 1. Purpose\nDoes stuff.\n")

        mock_run_state = PipelineRun(
            run_id="abc1234567890",
            pipeline_name="validate_only",
            project_name="res-proj",
            spec_path=str(spec),
            status=RunStatus.PARKED,
            started_at="",
            updated_at="",
        )

        from specweaver.core.config.settings import SandboxSettings, SpecWeaverSettings

        sentinel = SpecWeaverSettings(
            llm={"model": "gemini-2.0-flash"},
            sandbox=SandboxSettings(enforce_worktree_isolation=True),
        )

        with (
            patch("specweaver.core.flow.interfaces.cli._get_state_store") as mock_get_store,
            patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
            patch("specweaver.assurance.graph.hasher.DependencyHasher.save_cache"),
            # Patch the loader to a sentinel so we assert the *wiring* (resume assigns
            # load_settings' result to context.config) independent of project resolution.
            patch(
                "specweaver.core.config.settings_loader.load_settings", return_value=sentinel
            ),
        ):
            mock_get_store.return_value.load_run.return_value = mock_run_state
            mock_runner = mock_runner_class.return_value

            class DummyRun:
                status = RunStatus.COMPLETED

            mock_runner.resume = AsyncMock(return_value=DummyRun())
            # resume resolves the active project (no --project flag); init set it active.
            result = runner.invoke(app, ["resume", "abc1234567890"])
            assert result.exit_code == 0, result.stdout
            return mock_runner_class.call_args.args[1]

    def test_resume_resolves_isolation_policy(self, tmp_path: Path, monkeypatch) -> None:
        context = self._resume_and_capture_context(tmp_path, monkeypatch)
        # sentinel settings enable the policy → resume wires it onto the flag,
        # while keeping context.config None (container-neutral).
        assert context.enforce_isolation is True
        assert context.config is None


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
            patch("specweaver.core.flow.interfaces.cli._get_state_store") as mock_get_store,
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
