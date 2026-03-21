# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for CLI to pipeline runner wiring."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from specweaver.cli import app
from specweaver.flow.runner import PipelineRunner
from specweaver.flow.state import RunStatus


runner = CliRunner()


def test_cli_run_command_wires_to_runner(tmp_path: Path) -> None:
    """Verifies that `sw run` constructs the pipeline, context, and runner correctly."""
    
    # We will mock the PipelineRunner.run method to prevent actual execution,
    # but we will let the CLI build it and call it.
    (tmp_path / "spec.md").write_text("# Test Spec")
    
    with patch("specweaver.flow.runner.PipelineRunner.run") as mock_run:
        from specweaver.flow.state import PipelineRun
        
        # Mute adapter creation and pipeline loading
        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_adapter, \
             patch("specweaver.flow.parser.load_pipeline") as mock_load_pipeline:
            # Fake the return
            fake_pr = MagicMock(spec=PipelineRun)
            fake_pr.status = RunStatus.COMPLETED
            fake_pr.run_id = "fake-123"
            mock_run.return_value = fake_pr
            
            mock_adapter.return_value = (MagicMock(), MagicMock(), MagicMock())
            mock_pipeline = MagicMock()
            mock_pipeline.name = "dummy"
            mock_load_pipeline.return_value = mock_pipeline
            
            result = runner.invoke(app, ["run", "dummy", str(tmp_path / "spec.md"), "--project", str(tmp_path)])
            
            # Should invoke without crashing
            if result.exit_code != 0:
                print(result.stdout)
            assert result.exit_code == 0
            mock_run.assert_called_once()
            
            # Wait, typer.testing invokes synchronously, and PipelineRunner.run is async.
            # actually `specweaver.cli` handles the `asyncio.run` loop inside of it.
