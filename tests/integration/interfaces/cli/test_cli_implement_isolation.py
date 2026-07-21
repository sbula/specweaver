# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-03 SF-03 T4: `sw implement` threads the per-run isolation policy (with DAL-driven
auto-escalation) into its RunContext at the composition root.

Drives the real `sw implement` command through `apply_session_policy(dal_auto_escalate=True)`,
mocking only the LLM adapter and capturing the RunContext handed to `PipelineRunner` (so the
pipeline itself is not executed). Proves: a DAL_B project auto-enables session isolation with
the derived allow-list; a small/low-DAL project stays on host; and `auto_isolate_min_dal="off"`
disables escalation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.core.config.settings import SpecWeaverSettings
from specweaver.interfaces.cli.main import app

runner = CliRunner()
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    from specweaver.core.config.database import Database
    from specweaver.core.config.db_bootstrap import bootstrap_database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    return Database(db_path)


def _scaffold(tmp_path, *, dal: str | None, git: bool = True):
    result = runner.invoke(app, ["init", "iso_proj", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    if dal is not None:
        (tmp_path / "context.yaml").write_text(
            f"operational:\n  dal_level: {dal}\n", encoding="utf-8"
        )
    if git:
        # A `.git` marker is enough for the Q3 git-repo check (the pipeline is mocked, so
        # no real git operations run).
        (tmp_path / ".git").mkdir(exist_ok=True)
    spec = tmp_path / "specs" / "greeter_spec.md"
    spec.write_text("# Greeter\n## 1. Purpose\nGreets.", encoding="utf-8")
    return spec


def _mock_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.available.return_value = True
    adapter.generate = AsyncMock()
    return adapter


def _run_and_capture_context(
    tmp_path, *, dal: str | None, min_dal: str = "DAL_B", git: bool = True
):
    """Invoke `sw implement` with a real settings object; capture the RunContext handed to
    PipelineRunner (mocked, so the pipeline never runs)."""
    from specweaver.core.flow.engine.state import RunStatus

    spec = _scaffold(tmp_path, dal=dal, git=git)
    settings = SpecWeaverSettings(llm={"model": "test-model"})
    settings.sandbox.auto_isolate_min_dal = min_dal  # enforce_session_isolation stays False

    with (
        patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_adapter,
        patch("specweaver.core.flow.engine.runner.PipelineRunner") as mock_runner_class,
    ):
        mock_adapter.return_value = (settings, _mock_adapter(), MagicMock(temperature=0.2))
        run_state = MagicMock()
        run_state.status = RunStatus.COMPLETED
        run_state.step_records = []
        mock_runner_class.return_value.run = AsyncMock(return_value=run_state)
        result = runner.invoke(app, ["implement", str(spec), "--project", str(tmp_path)])
        assert mock_runner_class.called, result.output
        return mock_runner_class.call_args.args[1]


def test_dal_b_project_auto_enables_session_isolation(tmp_path) -> None:
    """[Happy] a DAL_B project → session isolation auto-on + derived allow-list."""
    context = _run_and_capture_context(tmp_path, dal="DAL_B")
    assert context.session_isolation is True
    assert context.allowed_paths == ["src/greeter.py", "tests/test_greeter.py"]


def test_small_project_without_dal_marker_stays_on_host(tmp_path) -> None:
    """[Boundary] no DAL marker (small project) → session off, host mode, allow-list empty."""
    context = _run_and_capture_context(tmp_path, dal=None)
    assert context.session_isolation is False
    assert context.allowed_paths == []


def test_low_dal_project_stays_on_host(tmp_path) -> None:
    """[Boundary] DAL_D is below the DAL_B threshold → session off."""
    context = _run_and_capture_context(tmp_path, dal="DAL_D")
    assert context.session_isolation is False


def test_threshold_off_disables_escalation_even_for_dal_a(tmp_path) -> None:
    """[Boundary] auto_isolate_min_dal='off' → no escalation even for DAL_A."""
    context = _run_and_capture_context(tmp_path, dal="DAL_A", min_dal="off")
    assert context.session_isolation is False


def test_dal_a_but_non_git_project_degrades_to_host(tmp_path) -> None:
    """[Degradation/Q3] a high-DAL but NON-git project degrades to host — auto-escalation
    must never break `sw implement`."""
    context = _run_and_capture_context(tmp_path, dal="DAL_A", git=False)
    assert context.session_isolation is False
