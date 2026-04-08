# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for implementation API endpoint (POST /implement)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
def _project_with_spec(client, tmp_path):
    """Register a project and create a spec file + output dirs."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "specs").mkdir()
    (proj / "src").mkdir()
    (proj / "tests").mkdir()
    spec = proj / "specs" / "greeter_spec.md"
    spec.write_text("# Greeter — Component Spec\n", encoding="utf-8")
    client.post(
        "/api/v1/projects",
        json={"name": "testproj", "path": str(proj), "scaffold": False},
    )
    return proj, spec


# ---------------------------------------------------------------------------
# POST /api/v1/implement
# ---------------------------------------------------------------------------


class TestImplementEndpoint:
    """Tests for POST /api/v1/implement."""

    @patch("specweaver.implementation.generator.Generator.generate_code", new_callable=AsyncMock)
    @patch("specweaver.implementation.generator.Generator.generate_tests", new_callable=AsyncMock)
    def test_implement_returns_200(
        self,
        mock_tests,
        mock_code,
        client,
        _project_with_spec,
    ) -> None:
        """Implement with mocked LLM → 200 with generated paths."""
        proj, spec = _project_with_spec
        # Create the output files that the mock would normally create
        (proj / "src" / "greeter.py").write_text("# generated", encoding="utf-8")
        (proj / "tests" / "test_greeter.py").write_text("# tests", encoding="utf-8")

        resp = client.post(
            "/api/v1/implement",
            json={
                "file": str(spec.relative_to(proj)),
                "project": "testproj",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "code_path" in data
        assert "test_path" in data

    def test_implement_missing_project_returns_404(self, client) -> None:
        """Implement with unknown project → 404."""
        resp = client.post(
            "/api/v1/implement",
            json={
                "file": "spec.md",
                "project": "unknown",
            },
        )
        assert resp.status_code == 404

    def test_implement_missing_spec_returns_404(self, client, _project_with_spec) -> None:
        """Implement with nonexistent spec → 404."""
        resp = client.post(
            "/api/v1/implement",
            json={
                "file": "nonexistent_spec.md",
                "project": "testproj",
            },
        )
        assert resp.status_code == 404

    def test_implement_path_traversal_rejected(self, client, _project_with_spec) -> None:
        """Paths with .. are rejected → 400."""
        resp = client.post(
            "/api/v1/implement",
            json={
                "file": "../../etc/passwd",
                "project": "testproj",
            },
        )
        assert resp.status_code == 400
