# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-09 CB-1 integration: the full config-resolution chain lands on the run
context. Exercises real `specweaver.toml` -> real `load_settings` -> `RunContext.config`
through the real `sw run` / `sw resume` composition roots (only `PipelineRunner` is
mocked, to capture the context that would be handed to the engine)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch):
    """Redirect the config DB to a per-test dir so `load_settings` reads THIS test's
    project registration + specweaver.toml — not the polluted global ~/.specweaver DB."""
    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    return data_dir


def _init_project(tmp_path: Path, name: str, toml_body: str | None) -> Path:
    project_dir = tmp_path / name  # dir basename == registered name → load_settings resolves it
    project_dir.mkdir()
    runner.invoke(app, ["init", name, "--path", str(project_dir)])
    spec = project_dir / "specs" / "test_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text("# Spec\n## 1. Purpose\nDoes stuff.\n")
    if toml_body is not None:
        (project_dir / "specweaver.toml").write_text(toml_body, encoding="utf-8")
    return project_dir


def _run_and_capture(project_dir: Path):
    from specweaver.core.flow.engine.state import RunStatus

    spec = project_dir / "specs" / "test_spec.md"
    with (
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
        patch("specweaver.assurance.graph.hasher.DependencyHasher.save_cache"),
    ):
        mock_runner_class.return_value.run = AsyncMock(
            return_value=type("R", (), {"status": RunStatus.COMPLETED})()
        )
        result = runner.invoke(
            app, ["run", "validate_only", str(spec), "--project", str(project_dir)]
        )
        assert result.exit_code == 0, result.stdout
        return mock_runner_class.call_args.args[1]


def test_toml_isolation_policy_true_flows_onto_run_context(tmp_path: Path) -> None:
    """[Happy Path] a real specweaver.toml enabling the policy reaches the run context."""
    project_dir = _init_project(
        tmp_path, "int09-toml", "[sandbox]\nenforce_worktree_isolation = true\n"
    )
    context = _run_and_capture(project_dir)
    assert context.enforce_isolation is True
    # container-neutral: the full config is NOT exposed on sw run (B-EXEC-01 dormant).
    assert context.config is None


def test_no_sandbox_section_keeps_policy_off_on_run_context(tmp_path: Path) -> None:
    """[Boundary/backward-compat] absent [sandbox] key → policy stays off on the context."""
    project_dir = _init_project(tmp_path, "int09-notoml", None)
    context = _run_and_capture(project_dir)
    assert context.enforce_isolation is False


def test_container_execution_mode_stays_dormant_on_run(tmp_path: Path) -> None:
    """[Hostile/Scope guard] a [sandbox] execution_mode=container toml must NOT activate
    B-EXEC-01 container QA on sw run — INT-US-09 is strictly container-free. Proven by
    context.config staying None (QA handlers read `context.config.sandbox if context.config
    else None` → None → host mode)."""
    project_dir = _init_project(
        tmp_path, "int09-container", '[sandbox]\nexecution_mode = "container"\n'
    )
    context = _run_and_capture(project_dir)
    assert context.config is None  # container opt-in stays dormant on this path
    assert context.enforce_isolation is False


def test_toml_session_isolation_true_flows_onto_run_context(tmp_path: Path) -> None:
    """[Happy Path — C-EXEC-06 SF-03] a real specweaver.toml enabling per-run isolation
    reaches the run context AND populates the derived allow-list (spec test_spec.md ->
    stem 'test' -> src/test.py + tests/test_test.py)."""
    project_dir = _init_project(
        tmp_path, "cexec06-toml", "[sandbox]\nenforce_session_isolation = true\n"
    )
    context = _run_and_capture(project_dir)
    assert context.session_isolation is True
    assert context.allowed_paths == ["src/test.py", "tests/test_test.py"]


def test_toml_session_allowed_paths_override_used_verbatim(tmp_path: Path) -> None:
    """[Happy Path] a configured session_allowed_paths override is used verbatim (not
    derived) when per-run isolation is on."""
    project_dir = _init_project(
        tmp_path,
        "cexec06-override",
        "[sandbox]\nenforce_session_isolation = true\n"
        'session_allowed_paths = ["src/only.py"]\n',
    )
    context = _run_and_capture(project_dir)
    assert context.session_isolation is True
    assert context.allowed_paths == ["src/only.py"]


def test_toml_per_step_isolation_on_but_session_off_keeps_allowed_paths_empty(
    tmp_path: Path,
) -> None:
    """[Boundary/NFR-2] the regression guard: per-STEP isolation on but per-RUN off must
    NOT populate allowed_paths — the per-step INT-US-09 strip_merge reads it, so a leaked
    allow-list would silently change that path's behavior."""
    project_dir = _init_project(
        tmp_path, "cexec06-nfr2", "[sandbox]\nenforce_worktree_isolation = true\n"
    )
    context = _run_and_capture(project_dir)
    assert context.enforce_isolation is True
    assert context.session_isolation is False
    assert context.allowed_paths == []


def test_toml_both_isolation_knobs_true_set_both_flags(tmp_path: Path) -> None:
    """[Boundary] per-step + per-run both enabled -> both flags set on the context
    (execute_run suppresses per-step nesting at runtime; this only asserts wiring)."""
    project_dir = _init_project(
        tmp_path,
        "cexec06-both",
        "[sandbox]\nenforce_worktree_isolation = true\nenforce_session_isolation = true\n",
    )
    context = _run_and_capture(project_dir)
    assert context.enforce_isolation is True
    assert context.session_isolation is True
    assert context.allowed_paths == ["src/test.py", "tests/test_test.py"]


def test_toml_no_sandbox_section_keeps_session_isolation_off(tmp_path: Path) -> None:
    """[Boundary/backward-compat] absent [sandbox] -> per-run isolation off, allow-list
    empty (NFR-2 byte-identical default)."""
    project_dir = _init_project(tmp_path, "cexec06-notoml", None)
    context = _run_and_capture(project_dir)
    assert context.session_isolation is False
    assert context.allowed_paths == []


def test_toml_malformed_sandbox_keeps_session_isolation_off(tmp_path: Path) -> None:
    """[Graceful Degradation] a malformed specweaver.toml must not crash the run and must
    leave per-run isolation off (the composition wiring is best-effort)."""
    project_dir = _init_project(tmp_path, "cexec06-malformed", "not valid toml [[[")
    context = _run_and_capture(project_dir)
    assert context.session_isolation is False
    assert context.allowed_paths == []


def test_toml_isolation_policy_true_flows_onto_resume_context(
    tmp_path: Path, monkeypatch
) -> None:
    """[Happy Path] the same real-toml policy reaches the resume composition root."""
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus

    monkeypatch.setattr(
        "specweaver.core.config.paths.state_db_path", lambda: tmp_path / "pipe_state.db"
    )
    project_dir = _init_project(
        tmp_path, "int09-resume", "[sandbox]\nenforce_worktree_isolation = true\n"
    )
    # resume resolves the project via resolve_project_path(None) → honors SW_PROJECT,
    # so load_settings gets the real project name and reads the real specweaver.toml.
    monkeypatch.setenv("SW_PROJECT", str(project_dir))

    parked = PipelineRun(
        run_id="abc1234567890",
        pipeline_name="validate_only",
        project_name="int09-resume",
        spec_path=str(project_dir / "specs" / "test_spec.md"),
        status=RunStatus.PARKED,
        started_at="",
        updated_at="",
    )
    with (
        patch("specweaver.core.flow.interfaces.cli._get_state_store") as mock_get_store,
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
        patch("specweaver.assurance.graph.hasher.DependencyHasher.save_cache"),
    ):
        mock_get_store.return_value.load_run.return_value = parked
        mock_runner_class.return_value.resume = AsyncMock(
            return_value=type("R", (), {"status": RunStatus.COMPLETED})()
        )
        result = runner.invoke(app, ["resume", "abc1234567890"])
        assert result.exit_code == 0, result.stdout
        context = mock_runner_class.call_args.args[1]

    assert context.enforce_isolation is True


def test_toml_session_isolation_true_flows_onto_resume_context(
    tmp_path: Path, monkeypatch
) -> None:
    """[Happy Path — C-EXEC-06 SF-03] per-run isolation policy + allow-list reach the
    resume composition root too."""
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus

    monkeypatch.setattr(
        "specweaver.core.config.paths.state_db_path", lambda: tmp_path / "pipe_state.db"
    )
    project_dir = _init_project(
        tmp_path, "cexec06-resume", "[sandbox]\nenforce_session_isolation = true\n"
    )
    monkeypatch.setenv("SW_PROJECT", str(project_dir))

    parked = PipelineRun(
        run_id="def4567890123",
        pipeline_name="validate_only",
        project_name="cexec06-resume",
        spec_path=str(project_dir / "specs" / "test_spec.md"),
        status=RunStatus.PARKED,
        started_at="",
        updated_at="",
    )
    with (
        patch("specweaver.core.flow.interfaces.cli._get_state_store") as mock_get_store,
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
        patch("specweaver.assurance.graph.hasher.DependencyHasher.save_cache"),
    ):
        mock_get_store.return_value.load_run.return_value = parked
        mock_runner_class.return_value.resume = AsyncMock(
            return_value=type("R", (), {"status": RunStatus.COMPLETED})()
        )
        result = runner.invoke(app, ["resume", "def4567890123"])
        assert result.exit_code == 0, result.stdout
        context = mock_runner_class.call_args.args[1]

    assert context.session_isolation is True
    assert context.allowed_paths == ["src/test.py", "tests/test_test.py"]
