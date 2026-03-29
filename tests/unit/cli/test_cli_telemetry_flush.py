# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for CLI command telemetry flush (Feature 3.12).

Verifies that CLI commands that use the adapter directly flush
the TelemetryCollector after operations.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch


class TestReviewCommandFlush:
    """sw review flushes TelemetryCollector after review."""

    @patch("specweaver.review.reviewer.Reviewer.review_spec", new_callable=AsyncMock)
    def test_review_flushes_collector(self, mock_review, tmp_path):
        """After sw review, flush() is called on the adapter."""
        from specweaver.llm.collector import TelemetryCollector
        from specweaver.review.reviewer import ReviewResult

        mock_review.return_value = ReviewResult(
            verdict="accepted",
            summary="OK",
            findings=[],
        )

        # Create a spec file to review
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        mock_collector = MagicMock(spec=TelemetryCollector)
        with (
            patch(
                "specweaver.cli._helpers._require_llm_adapter",
                return_value=(MagicMock(), mock_collector, MagicMock()),
            ),
            patch(
                "specweaver.project.discovery.resolve_project_path",
                return_value=tmp_path,
            ),
            patch("specweaver.cli._helpers._load_topology", return_value=None),
            patch("specweaver.cli._helpers._load_constitution_content", return_value=None),
            patch("specweaver.cli._helpers._load_standards_content", return_value=None),
        ):
            from specweaver.cli.review import review

            with contextlib.suppress(SystemExit):
                review(target=str(spec), project=str(tmp_path), spec=None, selector="direct")

        mock_collector.flush.assert_called_once()


class TestImplementCommandFlush:
    """sw implement flushes TelemetryCollector after generation."""

    def test_implement_flushes_collector(self, tmp_path):
        """After sw implement, flush() is called on the adapter."""
        from specweaver.llm.collector import TelemetryCollector

        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        mock_collector = MagicMock(spec=TelemetryCollector)
        with (
            patch(
                "specweaver.cli._helpers._require_llm_adapter",
                return_value=(MagicMock(), mock_collector, MagicMock()),
            ),
            patch(
                "specweaver.project.discovery.resolve_project_path",
                return_value=tmp_path,
            ),
            patch("specweaver.cli._helpers._load_topology", return_value=None),
            patch("specweaver.cli._helpers._load_constitution_content", return_value=None),
            patch("specweaver.cli._helpers._load_standards_content", return_value=None),
            patch(
                "specweaver.implementation.generator.Generator.generate_code",
                new_callable=AsyncMock,
            ),
            patch(
                "specweaver.implementation.generator.Generator.generate_tests",
                new_callable=AsyncMock,
            ),
        ):
            from specweaver.cli.implement import implement

            implement(spec=str(spec), project=str(tmp_path), selector="direct")

        mock_collector.flush.assert_called_once()


class TestDraftCommandFlush:
    """sw draft flushes TelemetryCollector after drafting."""

    @patch("specweaver.drafting.drafter.Drafter.draft", new_callable=AsyncMock)
    def test_draft_flushes_collector(self, mock_draft, tmp_path):
        """After sw draft, flush() is called on the adapter."""
        from specweaver.llm.collector import TelemetryCollector

        mock_draft.return_value = tmp_path / "result.md"

        mock_collector = MagicMock(spec=TelemetryCollector)
        with (
            patch(
                "specweaver.cli._helpers._require_llm_adapter",
                return_value=(MagicMock(), mock_collector, MagicMock()),
            ),
            patch(
                "specweaver.project.discovery.resolve_project_path",
                return_value=tmp_path,
            ),
            patch("specweaver.cli._helpers._load_topology", return_value=None),
        ):
            # Ensure specs dir exists and target doesn't
            (tmp_path / "specs").mkdir(exist_ok=True)

            from specweaver.cli.review import draft

            with contextlib.suppress(SystemExit):
                draft(
                    name="test_component",
                    project=str(tmp_path),
                    selector="direct",
                )

        mock_collector.flush.assert_called_once()
