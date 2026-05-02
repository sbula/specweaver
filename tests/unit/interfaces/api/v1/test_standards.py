# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for standards API endpoints."""

from __future__ import annotations

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
def _project_with_python(client, tmp_path):
    """Register a project with a Python file for scanning."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "src").mkdir()
    (proj / "src" / "example.py").write_text(
        '"""Example module."""\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Greet a user by name."""\n'
        '    return f"Hello {name}!"\n',
        encoding="utf-8",
    )
    client.post(
        "/api/v1/projects",
        json={"name": "testproj", "path": str(proj), "scaffold": False},
    )
    return proj


# ---------------------------------------------------------------------------
# GET /api/v1/standards
# ---------------------------------------------------------------------------


class TestGetStandards:
    """Tests for GET /api/v1/standards."""

    def test_empty_standards(self, client, _project_with_python) -> None:
        """No standards saved → empty list."""
        resp = client.get("/api/v1/standards", params={"project": "testproj"})
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# DELETE /api/v1/standards
# ---------------------------------------------------------------------------


class TestDeleteStandards:
    """Tests for DELETE /api/v1/standards."""

    def test_clear_standards(self, client, _project_with_python) -> None:
        """Delete standards → 200."""
        resp = client.delete("/api/v1/standards", params={"project": "testproj"})
        assert resp.status_code == 200

    def test_clear_nonexistent_project(self, client) -> None:
        """Delete standards for unknown project → 404."""
        resp = client.delete("/api/v1/standards", params={"project": "nope"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/standards/scan
# ---------------------------------------------------------------------------


class TestScanStandards:
    """Tests for POST /api/v1/standards/scan."""

    def test_scan_returns_results(self, client, _project_with_python) -> None:
        """Scan finds Python standards → 200 with results."""
        resp = client.post(
            "/api/v1/standards/scan",
            json={"project": "testproj"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Scan should find at least the Python file conventions
        assert len(data) > 0

    def test_scan_nonexistent_project(self, client) -> None:
        """Scan unknown project → 404."""
        resp = client.post(
            "/api/v1/standards/scan",
            json={"project": "nope"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/standards/accept
# ---------------------------------------------------------------------------


class TestAcceptStandards:
    """Tests for POST /api/v1/standards/accept."""

    def test_accept_saves_standards(self, client, _project_with_python) -> None:
        """Accept scanned standards → 200, then GET shows them."""
        # Step 1: scan
        scan_resp = client.post(
            "/api/v1/standards/scan",
            json={"project": "testproj"},
        )
        assert scan_resp.status_code == 200
        scanned = scan_resp.json()
        if not scanned:
            pytest.skip("No standards detected from test file")

        # Step 2: accept all
        accept_resp = client.post(
            "/api/v1/standards/accept",
            json={
                "project": "testproj",
                "standards": scanned,
            },
        )
        assert accept_resp.status_code == 200

        # Step 3: verify saved
        get_resp = client.get("/api/v1/standards", params={"project": "testproj"})
        assert get_resp.status_code == 200
        assert len(get_resp.json()) > 0
