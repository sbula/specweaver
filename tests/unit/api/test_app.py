# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

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

    def test_cors_env_var_single_origin(self, tmp_path, monkeypatch) -> None:
        """CORS_ORIGINS env var adds origins to allowed list."""
        from specweaver.api.app import create_app
        from specweaver.config.database import Database

        monkeypatch.setenv("CORS_ORIGINS", "http://192.168.1.100:8000")
        db = Database(tmp_path / ".sw-cors" / "specweaver.db")
        app = create_app(db=db)
        c = TestClient(app)

        resp = c.options(
            "/healthz",
            headers={
                "Origin": "http://192.168.1.100:8000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://192.168.1.100:8000"

    def test_cors_env_var_comma_separated(self, tmp_path, monkeypatch) -> None:
        """CORS_ORIGINS with multiple comma-separated origins."""
        from specweaver.api.app import create_app
        from specweaver.config.database import Database

        monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
        db = Database(tmp_path / ".sw-cors2" / "specweaver.db")
        app = create_app(db=db)
        c = TestClient(app)

        resp = c.options(
            "/healthz",
            headers={
                "Origin": "http://b.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://b.com"

    def test_cors_env_var_empty_no_effect(self, tmp_path, monkeypatch) -> None:
        """Empty CORS_ORIGINS env var has no effect."""
        from specweaver.api.app import create_app
        from specweaver.config.database import Database

        monkeypatch.setenv("CORS_ORIGINS", "")
        db = Database(tmp_path / ".sw-cors3" / "specweaver.db")
        app = create_app(db=db)
        c = TestClient(app)

        # Non-localhost origin should be rejected when env is empty
        resp = c.options(
            "/healthz",
            headers={
                "Origin": "http://external.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") != "http://external.example.com"

    def test_cors_env_var_whitespace_handling(self, tmp_path, monkeypatch) -> None:
        """CORS_ORIGINS with extra whitespace and empty entries."""
        from specweaver.api.app import create_app
        from specweaver.config.database import Database

        monkeypatch.setenv("CORS_ORIGINS", "  , http://clean.com ,  ")
        db = Database(tmp_path / ".sw-cors4" / "specweaver.db")
        app = create_app(db=db)
        c = TestClient(app)

        resp = c.options(
            "/healthz",
            headers={
                "Origin": "http://clean.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://clean.com"

    def test_cors_programmatic_and_env_merge(self, tmp_path, monkeypatch) -> None:
        """Programmatic cors_origins and CORS_ORIGINS env var are merged."""
        from specweaver.api.app import create_app
        from specweaver.config.database import Database

        monkeypatch.setenv("CORS_ORIGINS", "http://env.example.com")
        db = Database(tmp_path / ".sw-cors5" / "specweaver.db")
        app = create_app(db=db, cors_origins=["http://prog.example.com"])
        c = TestClient(app)

        # Env origin allowed
        resp1 = c.options(
            "/healthz",
            headers={
                "Origin": "http://env.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp1.headers.get("access-control-allow-origin") == "http://env.example.com"

        # Programmatic origin also allowed
        resp2 = c.options(
            "/healthz",
            headers={
                "Origin": "http://prog.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp2.headers.get("access-control-allow-origin") == "http://prog.example.com"

    def test_cors_allows_127_0_0_1(self, client: TestClient) -> None:
        """127.0.0.1 origin should be allowed by regex."""
        resp = client.options(
            "/healthz",
            headers={
                "Origin": "http://127.0.0.1:5000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5000"
