# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for REST API telemetry wiring (Feature 3.12).

Verifies that API endpoints pass telemetry_project and flush
the TelemetryCollector after operations.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    """Create a test client backed by a temporary DB."""
    from specweaver.interfaces.api.app import create_app
    from specweaver.core.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    app = create_app(db=db)
    return TestClient(app)


@pytest.fixture()
def _project_with_spec(client, tmp_path):
    """Register a project and create a spec file."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "specs").mkdir()
    spec = proj / "specs" / "greeter_spec.md"
    spec.write_text("# Greeter — Component Spec\n", encoding="utf-8")
    client.post(
        "/api/v1/projects",
        json={"name": "testproj", "path": str(proj), "scaffold": False},
    )
    return proj, spec


class TestReviewEndpointTelemetry:
    """POST /review passes telemetry_project and flushes collector."""

    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec", new_callable=AsyncMock)
    def test_review_passes_telemetry_project(
        self,
        mock_review,
        client,
        _project_with_spec,
    ):
        """create_llm_adapter is called with telemetry_project='testproj'."""
        from specweaver.workflows.review.reviewer import ReviewResult

        mock_review.return_value = ReviewResult(
            verdict="accepted",
            summary="OK",
            findings=[],
        )
        proj, spec = _project_with_spec

        with patch(
            "specweaver.infrastructure.llm.factory.create_llm_adapter",
        ) as mock_create:
            mock_adapter = MagicMock()
            mock_create.return_value = (MagicMock(), mock_adapter, MagicMock())

            client.post(
                "/api/v1/review",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        # Verify telemetry_project was passed
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs.get("telemetry_project") == "testproj"

    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec", new_callable=AsyncMock)
    def test_review_flushes_telemetry_collector(
        self,
        mock_review,
        client,
        _project_with_spec,
    ):
        """After review, if adapter is TelemetryCollector, flush() is called."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.workflows.review.reviewer import ReviewResult

        mock_review.return_value = ReviewResult(
            verdict="accepted",
            summary="OK",
            findings=[],
        )
        proj, spec = _project_with_spec

        mock_collector = MagicMock(spec=TelemetryCollector)
        with patch(
            "specweaver.infrastructure.llm.factory.create_llm_adapter",
        ) as mock_create:
            mock_create.return_value = (MagicMock(), mock_collector, MagicMock())

            client.post(
                "/api/v1/review",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        mock_collector.flush.assert_called_once()


class TestImplementEndpointTelemetry:
    """POST /implement passes telemetry_project and flushes collector."""

    def test_implement_passes_telemetry_project(
        self,
        client,
        _project_with_spec,
    ):
        """create_llm_adapter is called with telemetry_project='testproj'."""
        proj, spec = _project_with_spec

        with (
            patch(
                "specweaver.infrastructure.llm.factory.create_llm_adapter",
            ) as mock_create,
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_code",
                new_callable=AsyncMock,
            ),
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_tests",
                new_callable=AsyncMock,
            ),
        ):
            mock_create.return_value = (MagicMock(), MagicMock(), MagicMock())

            client.post(
                "/api/v1/implement",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs.get("telemetry_project") == "testproj"

    def test_implement_flushes_telemetry_collector(
        self,
        client,
        _project_with_spec,
    ):
        """After implement, if adapter is TelemetryCollector, flush() is called."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        proj, spec = _project_with_spec
        mock_collector = MagicMock(spec=TelemetryCollector)

        with (
            patch(
                "specweaver.infrastructure.llm.factory.create_llm_adapter",
            ) as mock_create,
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_code",
                new_callable=AsyncMock,
            ),
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_tests",
                new_callable=AsyncMock,
            ),
        ):
            mock_create.return_value = (MagicMock(), mock_collector, MagicMock())

            client.post(
                "/api/v1/implement",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        mock_collector.flush.assert_called_once()
