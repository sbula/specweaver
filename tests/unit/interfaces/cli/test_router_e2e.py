from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from specweaver.interfaces.cli.pipelines import _execute_run, resume


@pytest.fixture
def mock_active_db(tmp_path: Path) -> MagicMock:
    """Provides a mocked DB that says 'test-proj' is active."""
    db = MagicMock()
    project_dir = tmp_path / "test-proj"
    project_dir.mkdir(exist_ok=True)
    db.get_active_project.return_value = {"name": "test-proj", "path": str(project_dir)}
    return db


def test_cli_pipelines_injects_model_router_in_run(
    mock_active_db: MagicMock, tmp_path: Path
) -> None:
    """T10 (Run): Pipeline wiring verification for 'sw run' injecting ModelRouter into RunContext."""
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Spec\n")
    project_dir = tmp_path / "test-proj"
    project_dir.mkdir(exist_ok=True)

    with (
        patch("specweaver.interfaces.cli.pipelines._core.get_db", return_value=mock_active_db),
        patch("specweaver.interfaces.cli.pipelines.resolve_project_path", return_value=project_dir),
        patch("specweaver.core.flow.runner.PipelineRunner") as mock_runner_cls,
    ):
        mock_runner = mock_runner_cls.return_value
        mock_runner.run = AsyncMock()

        # Execute run command internals
        _execute_run(
            pipeline="validate_only",
            spec_or_module=str(spec_path),
            verbose=False,
            json_output=False,
            selector="direct",
            project=None,
            resume_id=None,
        )

        # Assert runner instantiated
        mock_runner_cls.assert_called_once()
        args, _ = mock_runner_cls.call_args

        # Extract context
        context = args[1]

        # Verify the ModelRouter was successfully instantiated and attached
        assert context.llm_router is not None
        assert context.llm_router._db is mock_active_db
        assert context.llm_router._project_name == "test-proj"


def test_cli_pipelines_injects_model_router_in_resume(
    mock_active_db: MagicMock, tmp_path: Path
) -> None:
    """T10 (Resume): Pipeline wiring verification for 'sw resume' injecting ModelRouter."""
    mock_state_db = MagicMock()
    # Mock get_resumable_runs to return our fake run
    mock_state_db.get_resumable_runs.return_value = [
        {"run_id": "run-123", "pipeline_name": "validate_only"}
    ]
    # Mock load_state
    mock_state = MagicMock()
    mock_state.run_id = "run-123"
    project_dir = tmp_path / "test-proj"
    project_dir.mkdir(exist_ok=True)
    mock_state.spec_path = "spec.md"
    mock_state.project_path = str(project_dir)
    mock_state.pipeline_name = "validate_only"
    mock_state_db.load_run.return_value = mock_state

    with (
        patch("specweaver.interfaces.cli.pipelines._core.get_db", return_value=mock_active_db),
        patch("specweaver.interfaces.cli.pipelines.resolve_project_path", return_value=project_dir),
        patch("specweaver.interfaces.cli.pipelines._get_state_store", return_value=mock_state_db),
        patch("specweaver.core.flow.runner.PipelineRunner") as mock_runner_cls,
    ):
        mock_runner = mock_runner_cls.return_value
        mock_runner.resume = AsyncMock()

        # Execute resume command
        resume(run_id="run-123", verbose=False, json_output=False)

        # Assert resume triggered
        mock_runner_cls.assert_called_once()
        args, _ = mock_runner_cls.call_args

        # Extract context
        context = args[1]

        # Verify ModelRouter was attached to the resurrected context
        assert context.llm_router is not None
        assert context.llm_router._db is mock_active_db
        assert context.llm_router._project_name == "test-proj"


def test_empty_pipeline_spec_edgecase(mock_active_db: MagicMock, tmp_path: Path) -> None:
    """T14: Execution intercepts empty routing targets dynamically."""
    # Create an empty spec file
    spec_path = tmp_path / "empty.md"
    spec_path.touch()

    with patch("specweaver.interfaces.cli.pipelines._core.get_db", return_value=mock_active_db):
        # We don't mock runner here; we let it execute up to the empty file exception
        with pytest.raises(typer.Exit) as exc_info:
            _execute_run(
                pipeline="validate_only",
                spec_or_module=str(spec_path),
                project=None,
                resume_id=None,
                verbose=False,
                json_output=False,
                selector="direct",
            )

        assert exc_info.value.exit_code == 1
