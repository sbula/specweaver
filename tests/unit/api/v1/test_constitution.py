# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for constitution API endpoints."""

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


@pytest.fixture()
def _project(client, tmp_path):
    """Register a project."""
    proj = tmp_path / "proj"
    proj.mkdir()
    client.post(
        "/api/v1/projects",
        json={"name": "testproj", "path": str(proj), "scaffold": True},
    )
    return proj


# ---------------------------------------------------------------------------
# GET /api/v1/constitution
# ---------------------------------------------------------------------------


class TestGetConstitution:
    """Tests for GET /api/v1/constitution."""

    def test_get_constitution(self, client, _project) -> None:
        """Get constitution for project with scaffold → 200."""
        resp = client.get("/api/v1/constitution", params={"project": "testproj"})
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_get_constitution_unknown_project(self, client) -> None:
        """Get constitution for unknown project → 404."""
        resp = client.get("/api/v1/constitution", params={"project": "nope"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/constitution/init
# ---------------------------------------------------------------------------


class TestInitConstitution:
    """Tests for POST /api/v1/constitution/init."""

    def test_init_constitution(self, client, tmp_path) -> None:
        """Init constitution for project without scaffold → 200."""
        proj = tmp_path / "noscaffold"
        proj.mkdir()
        client.post(
            "/api/v1/projects",
            json={"name": "bare", "path": str(proj), "scaffold": False},
        )
        resp = client.post(
            "/api/v1/constitution/init",
            json={"project": "bare"},
        )
        assert resp.status_code == 200
        # Verify file was created
        assert (proj / "CONSTITUTION.md").exists()
