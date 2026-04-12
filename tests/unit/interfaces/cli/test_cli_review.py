# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — CLI review module."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.core.flow.state import PipelineRun, StepRecord, StepResult, StepStatus
from specweaver.interfaces.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    from specweaver.core.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
    return db


def _scaffold(tmp_path: Path) -> Path:
    (tmp_path / ".specweaver").mkdir(exist_ok=True)
    return tmp_path


class TestReviewCommand:
    """Test the review command behavior using PipelineRunner."""

    @patch("specweaver.interfaces.cli._helpers._require_llm_adapter")
    @patch("specweaver.core.flow.runner.PipelineRunner.run", new_callable=AsyncMock)
    def test_review_success_no_exit(self, mock_run, mock_require, tmp_path: Path) -> None:
        """Pipeline returns completed and step PASSED -> exit 0."""
        project = _scaffold(tmp_path)
        spec = project / "test.md"
        spec.write_text("# Spec\n", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (mock_settings, MagicMock(), MagicMock())

        # Mock a successful Pipeline run
        mock_result = StepResult(
            status=StepStatus.PASSED,
            output={"verdict": "accepted", "summary": "Looks good."},
            started_at="2023-01-01T00:00:00Z",
            completed_at="2023-01-01T00:01:00Z",
        )
        mock_run.return_value = PipelineRun(
            run_id="idx",
            pipeline_name="p",
            project_name="proj",
            spec_path="test.md",
            status="completed",
            started_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
            step_records=[
                StepRecord(step_name="review_target", status=StepStatus.PASSED, result=mock_result)
            ],
        )

        result = runner.invoke(app, ["review", str(spec), "--project", str(project)])
        assert result.exit_code == 0
        assert "Looks good." in result.output

    @patch("specweaver.interfaces.cli._helpers._require_llm_adapter")
    @patch("specweaver.core.flow.runner.PipelineRunner.run", new_callable=AsyncMock)
    def test_review_denied_exit_1(self, mock_run, mock_require, tmp_path: Path) -> None:
        """Pipeline PASSED but review verdict DENIED -> exit 1."""
        project = _scaffold(tmp_path)
        spec = project / "test.md"
        spec.write_text("# Spec\n", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (mock_settings, MagicMock(), MagicMock())

        # Mock a pipeline run where review was DENIED
        mock_result = StepResult(
            status=StepStatus.PASSED,
            output={
                "verdict": "denied",
                "summary": "Missing sections.",
                "findings": [{"severity": "high", "message": "No Purpose"}],
            },
            started_at="2023-01-01T00:00:00Z",
            completed_at="2023-01-01T00:01:00Z",
        )
        mock_run.return_value = PipelineRun(
            run_id="idx",
            pipeline_name="p",
            project_name="proj",
            spec_path="test.md",
            status="completed",
            started_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
            step_records=[
                StepRecord(step_name="review_target", status=StepStatus.PASSED, result=mock_result)
            ],
        )

        result = runner.invoke(app, ["review", str(spec), "--project", str(project)])
        assert result.exit_code == 1
        assert "Missing sections." in result.output
        assert "No Purpose" in result.output

    @patch("specweaver.interfaces.cli._helpers._require_llm_adapter")
    @patch("specweaver.core.flow.runner.PipelineRunner.run", new_callable=AsyncMock)
    def test_review_error_exit_1(self, mock_run, mock_require, tmp_path: Path) -> None:
        """Pipeline returns parked or step FAILED -> exit 1."""
        project = _scaffold(tmp_path)
        spec = project / "test.md"
        spec.write_text("# Spec\n", encoding="utf-8")

        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (mock_settings, MagicMock(), MagicMock())

        mock_result = StepResult(
            status=StepStatus.FAILED,
            error_message="API Error",
            started_at="2023-01-01T00:00:00Z",
            completed_at="2023-01-01T00:01:00Z",
        )
        mock_run.return_value = PipelineRun(
            run_id="idx",
            pipeline_name="p",
            project_name="proj",
            spec_path="test.md",
            status="parked",
            started_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z",
            step_records=[
                StepRecord(step_name="review_target", status=StepStatus.FAILED, result=mock_result)
            ],
        )

        result = runner.invoke(app, ["review", str(spec), "--project", str(project)])
        assert result.exit_code == 1
        assert "API Error" in result.output
