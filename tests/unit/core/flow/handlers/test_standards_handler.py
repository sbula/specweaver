# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for EnrichStandardsHandler."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.standards import EnrichStandardsHandler


@pytest.fixture
def mock_context(tmp_path: Path) -> RunContext:
    """Provide a mock RunContext."""
    mock_config = MagicMock()
    mock_config.llm.model = "gemini-2.5-pro"
    mock_config.llm.temperature = 0.5
    mock_config.llm.max_output_tokens = 4096

    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "dummy.md",
        llm=MagicMock(),
        config=mock_config,
    )


def test_enrich_standards_success(mock_context: RunContext) -> None:
    """Test successful execution of EnrichStandardsHandler."""
    handler = EnrichStandardsHandler()
    step = PipelineStep(
        name="test_enrich",
        action=StepAction.ENRICH,
        target=StepTarget.STANDARDS,
        params={
            "scope_files": ["src/main.py"],
            "half_life_days": 90.0,
            "compare": False,
        },
    )

    with (
        patch("specweaver.assurance.standards.scanner.StandardsScanner") as mock_scanner_cls,
        patch("specweaver.assurance.standards.enricher.StandardsEnricher") as mock_enricher_cls,
    ):
        # Mock scanner
        mock_scanner = mock_scanner_cls.return_value
        mock_raw_result = MagicMock()
        mock_raw_result.confidence = 0.8
        mock_scanner.scan.return_value = [mock_raw_result]

        # Mock enricher
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich = AsyncMock()

        result = asyncio.run(handler.execute(step, mock_context))

        assert result.status == StepStatus.PASSED
        mock_scanner.scan.assert_called_once_with(["src/main.py"], 90.0)
        mock_enricher.enrich.assert_called_once_with(
            [mock_raw_result], language="auto", force_compare=False
        )
        assert result.output == {"results": [mock_raw_result]}


def test_enrich_standards_no_results(mock_context: RunContext) -> None:
    """Test execution when scanner finds no results above confidence threshold."""
    handler = EnrichStandardsHandler()
    step = PipelineStep(
        name="test_enrich_empty",
        action=StepAction.ENRICH,
        target=StepTarget.STANDARDS,
        params={"scope_files": [], "compare": False},
    )

    with (
        patch("specweaver.assurance.standards.scanner.StandardsScanner") as mock_scanner_cls,
        patch("specweaver.assurance.standards.enricher.StandardsEnricher") as mock_enricher_cls,
    ):
        mock_scanner = mock_scanner_cls.return_value
        mock_scanner.scan.return_value = []
        mock_enricher = mock_enricher_cls.return_value
        mock_enricher.enrich = AsyncMock()

        result = asyncio.run(handler.execute(step, mock_context))

        assert result.status == StepStatus.PASSED
        mock_enricher.enrich.assert_not_called()
        assert result.output == {"results": []}
