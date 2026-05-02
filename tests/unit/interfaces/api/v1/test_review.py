# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for review API endpoint (POST /review)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    """Create a test client backed by a temporary DB."""
    from specweaver.core.config.database import Database
    from specweaver.interfaces.api.app import create_app
    from specweaver.interfaces.cli._db_utils import bootstrap_database

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


# ---------------------------------------------------------------------------
# POST /api/v1/review
# ---------------------------------------------------------------------------


class TestReviewEndpoint:
    """Tests for POST /api/v1/review."""

    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec", new_callable=AsyncMock)
    def test_review_returns_result(self, mock_review, client, _project_with_spec) -> None:
        """Review a spec → 200 with review result."""
        from specweaver.workflows.review.reviewer import ReviewResult

        mock_review.return_value = ReviewResult(
            verdict="accepted",
            summary="Looks good.",
            findings=[],
        )
        proj, spec = _project_with_spec
        resp = client.post(
            "/api/v1/review",
            json={
                "file": str(spec.relative_to(proj)),
                "project": "testproj",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verdict"] == "accepted"
        assert "summary" in data

    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec", new_callable=AsyncMock)
    def test_review_denied_returns_result(self, mock_review, client, _project_with_spec) -> None:
        """Review that denies spec → 200 with DENIED verdict."""
        from specweaver.workflows.review.reviewer import ReviewFinding, ReviewResult

        mock_review.return_value = ReviewResult(
            verdict="denied",
            summary="Missing sections.",
            findings=[ReviewFinding(severity="error", description="No contract section")],
        )
        proj, spec = _project_with_spec
        resp = client.post(
            "/api/v1/review",
            json={
                "file": str(spec.relative_to(proj)),
                "project": "testproj",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verdict"] == "denied"
        assert len(data["findings"]) > 0

    def test_review_missing_project_returns_404(self, client) -> None:
        """Review with unknown project → 404."""
        resp = client.post(
            "/api/v1/review",
            json={
                "file": "spec.md",
                "project": "unknown",
            },
        )
        assert resp.status_code == 404

    def test_review_missing_file_returns_404(self, client, _project_with_spec) -> None:
        """Review with nonexistent file → 404."""
        resp = client.post(
            "/api/v1/review",
            json={
                "file": "nonexistent.md",
                "project": "testproj",
            },
        )
        assert resp.status_code == 404

    def test_review_path_traversal_rejected(self, client, _project_with_spec) -> None:
        """Paths with .. are rejected → 400."""
        resp = client.post(
            "/api/v1/review",
            json={
                "file": "../../etc/passwd",
                "project": "testproj",
            },
        )
        assert resp.status_code == 400
