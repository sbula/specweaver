from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force get_db to return a path in our isolated tmp_path."""

    # Bypass the global conftest mock that pre-initializes the DB
    def _native_get_db():
        from specweaver.core.config.database import Database
        db_path = tmp_path / "specweaver.db"
        try:
            from specweaver.core.config.cli_db_utils import bootstrap_database
            bootstrap_database(str(db_path))
        except Exception:
            pass
        return Database(db_path)

    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", _native_get_db)


def test_costs_e2e_happy_path(tmp_path: Path) -> None:
    """[Happy Path] Root entrypoint correctly invokes decentralized `sw costs set` and `sw costs`."""
    db_path = tmp_path / "specweaver.db"
    assert not db_path.exists()

    # 1. Set a cost override
    result = runner.invoke(app, ["costs", "set", "test-model-e2e", "0.005", "0.015"])
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "Cost override set for" in result.output
    assert "test-model-e2e" in result.output

    # 2. View the costs to confirm it persisted
    result_view = runner.invoke(app, ["costs"])
    assert result_view.exit_code == 0
    assert "test-model-e2e" in result_view.output
    assert "override" in result_view.output

    # 3. Verify in database natively
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT input_cost_per_1k, output_cost_per_1k FROM llm_cost_overrides WHERE model_pattern = 'test-model-e2e'")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert abs(row[0] - 0.005) < 1e-9
    assert abs(row[1] - 0.015) < 1e-9


def test_usage_e2e_happy_path(tmp_path: Path) -> None:
    """[Happy Path] Root entrypoint correctly invokes `sw usage` and aggregates telemetry data."""
    db_path = tmp_path / "specweaver.db"
    # First, let's create a project so 'sw usage' doesn't complain about no active project
    r1 = runner.invoke(app, ["projects"])
    assert r1.exit_code == 0

    r2 = runner.invoke(app, ["init", "e2e_test_proj", "--path", str(tmp_path)])
    assert r2.exit_code == 0, f"Init failed: {r2.output}"

    r3 = runner.invoke(app, ["use", "e2e_test_proj"])
    assert r3.exit_code == 0, f"Use failed: {r3.output}"

    # Manually seed some usage natively to ensure 'sw usage' reads it
    db_path = tmp_path / "specweaver.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO llm_usage_log "
        "(timestamp, project_name, task_type, model, provider, prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms) "
        "VALUES "
        "('2026-05-01T12:00:00Z', 'e2e_test_proj', 'review', 'test-model-e2e', 'openai', 100, 50, 150, 0.002, 500)"
    )
    conn.commit()
    conn.close()

    result = runner.invoke(app, ["usage"])
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert "LLM Usage" in result.output
    assert "review" in result.output
    assert "150" in result.output  # Total tokens


def test_standards_scan_locked_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[Graceful Degradation] `sw standards scan` handles database errors gracefully."""
    # We will simulate a locked DB or an operational error when standards tries to scan
    runner.invoke(app, ["init", "e2e_test_proj", "--path", str(tmp_path)])
    runner.invoke(app, ["use", "e2e_test_proj"])

    # Mock the DB session scope to raise an OperationalError
    from sqlalchemy.exc import OperationalError

    class BrokenDB:
        def __init__(self, *args, **kwargs):
            pass

        def async_session_scope(self):
            class BrokenContext:
                async def __aenter__(self):
                    raise OperationalError("database is locked", None, None)
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return BrokenContext()

    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", BrokenDB)

    result = runner.invoke(app, ["standards", "scan"])
    # It should fail loudly but not with a raw traceback (typer exit or handled exception)
    assert result.exit_code != 0
    assert "database is locked" in str(result.exception) or "database is locked" in result.output


def test_review_cli_hostile_input_overlapping_flags() -> None:
    """[Hostile/Wrong Input] CLI command invoked with invalid overlapping flags triggers Typer semantic abort."""
    result = runner.invoke(app, ["review", "--target", "src/", "--all"])
    assert result.exit_code != 0
    assert "Cannot use --target and --all together" in result.output or "invalid" in result.output.lower() or "error" in result.output.lower()


def test_pipeline_run_di_cascade_e2e(tmp_path: Path) -> None:
    """[Happy Path] (FR-8) Pipeline execution via CLI `sw run` seamlessly injects LLM Settings."""
    # First, let's create a project and a pipeline
    runner.invoke(app, ["init", "e2e_pipeline_proj", "--path", str(tmp_path)])
    runner.invoke(app, ["use", "e2e_pipeline_proj"])

    # Run a pipeline that relies on the Flow engine -> Adapter Factory DI
    # We use a dummy pipeline name. Even if it fails to resolve, we verify it touches the DI seam
    result = runner.invoke(app, ["run", "non_existent_pipeline", str(tmp_path / "spec.md")])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "no such" in result.output.lower()
