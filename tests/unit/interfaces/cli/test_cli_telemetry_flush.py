# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for CLI command telemetry flush (Feature 3.12).

Verifies that CLI commands that use the adapter directly flush
the TelemetryCollector after operations.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch


class TestReviewCommandFlush:
    """sw review flushes TelemetryCollector after review."""

    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec", new_callable=AsyncMock)
    def test_review_flushes_collector(self, mock_review, tmp_path):
        """After sw review, flush() is called on the adapter."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.workflows.review.reviewer import ReviewResult

        mock_review.return_value = ReviewResult(
            verdict="accepted",
            summary="OK",
            findings=[],
        )

        # Create a spec file to review
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_settings = MagicMock()
        mock_settings.llm.model = "gemini-2.5-pro"

        with (
            patch(
                "specweaver.interfaces.cli._helpers._require_llm_adapter",
                return_value=(mock_settings, mock_collector, MagicMock()),
            ),
            patch(
                "specweaver.workspace.project.discovery.resolve_project_path",
                return_value=tmp_path,
            ),
            patch("specweaver.interfaces.cli._helpers._load_topology", return_value=None),
            patch("specweaver.interfaces.cli._helpers._load_constitution_content", return_value=None),
            patch("specweaver.interfaces.cli._helpers._load_standards_content", return_value=None),
        ):
            from specweaver.interfaces.cli.review import review

            with contextlib.suppress(SystemExit):
                review(target=str(spec), project=str(tmp_path), spec=None, selector="direct")

        mock_collector.flush.assert_called_once()


class TestImplementCommandFlush:
    """sw implement flushes TelemetryCollector after generation."""

    def test_implement_flushes_collector(self, tmp_path):
        """After sw implement, flush() is called on the adapter."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_settings = MagicMock()
        mock_settings.llm.model = "gemini-2.5-pro"

        with (
            patch(
                "specweaver.interfaces.cli._helpers._require_llm_adapter",
                return_value=(mock_settings, mock_collector, MagicMock()),
            ),
            patch(
                "specweaver.workspace.project.discovery.resolve_project_path",
                return_value=tmp_path,
            ),
            patch("specweaver.interfaces.cli._helpers._load_topology", return_value=None),
            patch("specweaver.interfaces.cli._helpers._load_constitution_content", return_value=None),
            patch("specweaver.interfaces.cli._helpers._load_standards_content", return_value=None),
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_code",
                new_callable=AsyncMock,
            ),
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_tests",
                new_callable=AsyncMock,
            ),
        ):
            from specweaver.interfaces.cli.implement import implement

            implement(spec=str(spec), project=str(tmp_path), selector="direct")

        mock_collector.flush.assert_called_once()


class TestDraftCommandFlush:
    """sw draft flushes TelemetryCollector after drafting."""

    @patch("specweaver.workflows.drafting.drafter.Drafter.draft", new_callable=AsyncMock)
    def test_draft_flushes_collector(self, mock_draft, tmp_path):
        """After sw draft, flush() is called on the adapter."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        mock_draft.return_value = tmp_path / "result.md"

        mock_collector = MagicMock(spec=TelemetryCollector)
        mock_settings = MagicMock()
        mock_settings.llm.model = "gemini-2.5-pro"

        with (
            patch(
                "specweaver.interfaces.cli._helpers._require_llm_adapter",
                return_value=(mock_settings, mock_collector, MagicMock()),
            ),
            patch(
                "specweaver.workspace.project.discovery.resolve_project_path",
                return_value=tmp_path,
            ),
            patch("specweaver.interfaces.cli._helpers._load_topology", return_value=None),
        ):
            # Ensure specs dir exists and target doesn't
            (tmp_path / "specs").mkdir(exist_ok=True)
            (tmp_path / "result.md").write_text("# content", encoding="utf-8")

            from specweaver.interfaces.cli.review import draft

            with contextlib.suppress(SystemExit):
                draft(
                    name="test_component",
                    project=str(tmp_path),
                    selector="direct",
                )

        mock_collector.flush.assert_called_once()
