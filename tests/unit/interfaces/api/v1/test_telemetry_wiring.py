# mypy: ignore-errors
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

from tests.scripted_llm import FixedRouter, doubled_llm


def _flushable() -> MagicMock:
    """An adapter whose flush the endpoint can await."""
    adapter = MagicMock()
    adapter.flush_async = AsyncMock()
    return adapter


@pytest.fixture()
def client(tmp_path):
    """Create a test client backed by a temporary DB."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app

    bootstrap_database(str(tmp_path / ".specweaver-test" / "specweaver.db"))
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

    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec")
    def test_review_passes_telemetry_project(
        self,
        mock_review,
        client,
        _project_with_spec,
    ):
        """The router is built to record usage against project 'testproj'."""
        from specweaver.workflows.review.reviewer import ReviewResult

        mock_review.return_value = ReviewResult(
            verdict="accepted",
            summary="OK",
            findings=[],
        )
        proj, spec = _project_with_spec

        with patch(
            "specweaver.interfaces.api.v1._llm.build_router",
            return_value=FixedRouter(_flushable()),
        ) as mock_build:
            client.post(
                "/api/v1/review",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        # Verify the router records usage against the project
        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs.get("project") == "testproj"

    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec")
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
        with doubled_llm(mock_collector):
            client.post(
                "/api/v1/review",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        mock_collector.flush_async.assert_called_once()


class TestImplementEndpointTelemetry:
    """POST /implement passes telemetry_project and flushes collector."""

    def test_implement_passes_telemetry_project(
        self,
        client,
        _project_with_spec,
    ):
        """The router is built to record usage against project 'testproj'."""
        proj, spec = _project_with_spec

        with (
            patch(
                "specweaver.interfaces.api.v1._llm.build_router",
                return_value=FixedRouter(_flushable()),
            ) as mock_build,
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_code",
            ),
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_tests",
            ),
        ):
            client.post(
                "/api/v1/implement",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs.get("project") == "testproj"

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
            doubled_llm(mock_collector),
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_code",
            ),
            patch(
                "specweaver.workflows.implementation.generator.Generator.generate_tests",
            ),
        ):
            client.post(
                "/api/v1/implement",
                json={
                    "file": str(spec.relative_to(proj)),
                    "project": "testproj",
                },
            )

        mock_collector.flush_async.assert_called_once()
