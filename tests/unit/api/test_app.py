# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for the FastAPI app factory and health endpoint."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient


@pytest.fixture()
def client(tmp_path):
    """Create a test client backed by a temporary DB."""
    from specweaver.api.app import create_app
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    app = create_app(db=db)
    return TestClient(app)


class TestAppFactory:
    """Tests for create_app()."""

    def test_app_has_openapi_title(self, client: TestClient) -> None:
        """OpenAPI docs should use SpecWeaver branding."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["info"]["title"] == "SpecWeaver API"

    def test_app_has_version(self, client: TestClient) -> None:
        """OpenAPI docs should include a version."""
        resp = client.get("/openapi.json")
        data = resp.json()
        assert "version" in data["info"]
        assert data["info"]["version"]  # not empty


class TestHealthEndpoint:
    """Tests for GET /healthz."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health check should return 200."""
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_health_returns_status_ok(self, client: TestClient) -> None:
        """Health check should return status=ok."""
        resp = client.get("/healthz")
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_returns_version(self, client: TestClient) -> None:
        """Health check should include a version string."""
        resp = client.get("/healthz")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


class TestCORSHeaders:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_localhost(self, client: TestClient) -> None:
        """Localhost origin should be allowed by default."""
        resp = client.options(
            "/healthz",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
