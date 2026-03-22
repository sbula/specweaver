# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for project management API endpoints (Phase 1 of 3.7)."""

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
def project_dir(tmp_path):
    """Create a project directory with specs/ and src/ subdirs."""
    project = tmp_path / "myproject"
    project.mkdir()
    (project / "specs").mkdir()
    (project / "src").mkdir()
    return project


# ---------------------------------------------------------------------------
# GET /api/v1/projects
# ---------------------------------------------------------------------------


class TestListProjects:
    """Tests for GET /api/v1/projects."""

    def test_empty_list(self, client: TestClient) -> None:
        """No projects registered → empty list."""
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_init(self, client: TestClient, project_dir) -> None:
        """After creating a project, list should return it."""
        client.post(
            "/api/v1/projects",
            json={"name": "testapp", "path": str(project_dir), "scaffold": False},
        )
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        projects = resp.json()
        assert len(projects) == 1
        assert projects[0]["name"] == "testapp"


# ---------------------------------------------------------------------------
# POST /api/v1/projects (init)
# ---------------------------------------------------------------------------


class TestCreateProject:
    """Tests for POST /api/v1/projects."""

    def test_create_project(self, client: TestClient, project_dir) -> None:
        """POST with valid name and path → 201 Created."""
        resp = client.post(
            "/api/v1/projects",
            json={"name": "testapp", "path": str(project_dir), "scaffold": False},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "testapp"
        assert data["path"] == str(project_dir)

    def test_create_project_with_scaffold(self, client: TestClient, project_dir) -> None:
        """POST with scaffold=True creates .specweaver/ directory."""
        resp = client.post(
            "/api/v1/projects",
            json={"name": "scaffolded", "path": str(project_dir), "scaffold": True},
        )
        assert resp.status_code == 201
        assert (project_dir / ".specweaver").exists()

    def test_create_duplicate_fails(self, client: TestClient, project_dir) -> None:
        """Registering the same project name twice → 409 Conflict."""
        client.post(
            "/api/v1/projects",
            json={"name": "dup", "path": str(project_dir), "scaffold": False},
        )
        resp = client.post(
            "/api/v1/projects",
            json={"name": "dup", "path": str(project_dir), "scaffold": False},
        )
        assert resp.status_code == 409
        assert "error_code" in resp.json()

    def test_create_with_missing_name_fails(self, client: TestClient) -> None:
        """POST without name → 422 Validation Error."""
        resp = client.post("/api/v1/projects", json={"path": "/tmp"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{name}
# ---------------------------------------------------------------------------


class TestDeleteProject:
    """Tests for DELETE /api/v1/projects/{name}."""

    def test_delete_existing(self, client: TestClient, project_dir) -> None:
        """Delete an existing project → 200."""
        client.post(
            "/api/v1/projects",
            json={"name": "todel", "path": str(project_dir), "scaffold": False},
        )
        resp = client.delete("/api/v1/projects/todel")
        assert resp.status_code == 200

        # Verify it's gone
        resp = client.get("/api/v1/projects")
        assert len(resp.json()) == 0

    def test_delete_nonexistent(self, client: TestClient) -> None:
        """Delete a project that doesn't exist → 404."""
        resp = client.delete("/api/v1/projects/nope")
        assert resp.status_code == 404
        assert "error_code" in resp.json()


# ---------------------------------------------------------------------------
# PUT /api/v1/projects/{name}
# ---------------------------------------------------------------------------


class TestUpdateProject:
    """Tests for PUT /api/v1/projects/{name}."""

    def test_update_path(self, client: TestClient, project_dir, tmp_path) -> None:
        """Update project path → 200."""
        client.post(
            "/api/v1/projects",
            json={"name": "upd", "path": str(project_dir), "scaffold": False},
        )
        new_path = tmp_path / "newpath"
        new_path.mkdir()
        resp = client.put(
            "/api/v1/projects/upd",
            json={"path": str(new_path)},
        )
        assert resp.status_code == 200

    def test_update_nonexistent(self, client: TestClient, tmp_path) -> None:
        """Update nonexistent project → 404."""
        resp = client.put(
            "/api/v1/projects/nope",
            json={"path": str(tmp_path)},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{name}/use
# ---------------------------------------------------------------------------


class TestUseProject:
    """Tests for POST /api/v1/projects/{name}/use."""

    def test_use_project(self, client: TestClient, project_dir) -> None:
        """Setting active project → 200."""
        client.post(
            "/api/v1/projects",
            json={"name": "active", "path": str(project_dir), "scaffold": False},
        )
        resp = client.post("/api/v1/projects/active/use")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] == "active"

    def test_use_nonexistent(self, client: TestClient) -> None:
        """Use a project that doesn't exist → 404."""
        resp = client.post("/api/v1/projects/nope/use")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Error response format
# ---------------------------------------------------------------------------


class TestErrorFormat:
    """Tests for error response consistency."""

    def test_error_has_detail_and_code(self, client: TestClient) -> None:
        """Error responses should include detail and error_code."""
        resp = client.delete("/api/v1/projects/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "error_code" in data
        assert data["error_code"] == "PROJECT_NOT_FOUND"
