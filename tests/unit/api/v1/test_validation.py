# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for validation API endpoints (POST /check, GET /rules)."""

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
def _project_with_spec(client, tmp_path):
    """Register a project and create a spec file."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "specs").mkdir()
    spec = proj / "specs" / "greeter_spec.md"
    spec.write_text(
        "# Greeter — Component Spec\n\n"
        "> **Status**: DRAFT\n\n---\n\n"
        "## 1. Purpose\n\nGreets users.\n\n---\n\n"
        "## 2. Contract\n\n```python\ndef greet(name: str) -> str: ...\n```\n\n---\n\n"
        "## 3. Protocol\n\n1. Validate name.\n2. Return greeting.\n\n---\n\n"
        "## 4. Policy\n\n| Error | Behavior |\n|:---|:---|\n| Empty | Raise ValueError |\n\n---\n\n"
        "## 5. Boundaries\n\n| Concern | Owned By |\n|:---|:---|\n| Auth | AuthService |\n\n---\n\n"
        "## Done Definition\n\n- [ ] Unit tests pass\n",
        encoding="utf-8",
    )
    client.post(
        "/api/v1/projects",
        json={"name": "testproj", "path": str(proj), "scaffold": False},
    )
    return proj, spec


# ---------------------------------------------------------------------------
# POST /api/v1/check
# ---------------------------------------------------------------------------


class TestCheckEndpoint:
    """Tests for POST /api/v1/check."""

    def test_check_spec_returns_results(self, client, _project_with_spec) -> None:
        """Check a valid spec → 200 with results envelope."""
        proj, spec = _project_with_spec
        resp = client.post(
            "/api/v1/check",
            json={
                "file": str(spec.relative_to(proj)),
                "level": "component",
                "project": "testproj",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "overall" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) > 0

    def test_check_code_returns_results(self, client, _project_with_spec) -> None:
        """Check a Python file at code level."""
        proj, _ = _project_with_spec
        code = proj / "clean.py"
        code.write_text(
            "def greet(name: str) -> str:\n"
            '    return f"Hello {name}!"\n',
            encoding="utf-8",
        )
        resp = client.post(
            "/api/v1/check",
            json={
                "file": "clean.py",
                "level": "code",
                "project": "testproj",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert any(r["rule_id"].startswith("C") for r in data["results"])

    def test_check_missing_file_returns_404(self, client, _project_with_spec) -> None:
        """Check with nonexistent file → 404."""
        resp = client.post(
            "/api/v1/check",
            json={
                "file": "nonexistent.md",
                "level": "component",
                "project": "testproj",
            },
        )
        assert resp.status_code == 404

    def test_check_missing_project_returns_404(self, client) -> None:
        """Check with unknown project → 404."""
        resp = client.post(
            "/api/v1/check",
            json={
                "file": "test.md",
                "level": "component",
                "project": "nope",
            },
        )
        assert resp.status_code == 404

    def test_check_path_traversal_rejected(self, client, _project_with_spec) -> None:
        """Paths with .. are rejected → 400."""
        resp = client.post(
            "/api/v1/check",
            json={
                "file": "../../../etc/passwd",
                "level": "component",
                "project": "testproj",
            },
        )
        assert resp.status_code == 400
        assert "traversal" in resp.json()["detail"].lower()

    def test_check_absolute_path_rejected(self, client, _project_with_spec) -> None:
        """Absolute paths are rejected → 400."""
        resp = client.post(
            "/api/v1/check",
            json={
                "file": "/etc/passwd",
                "level": "component",
                "project": "testproj",
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/v1/rules
# ---------------------------------------------------------------------------


class TestListRulesEndpoint:
    """Tests for GET /api/v1/rules."""

    def test_list_rules_returns_spec_rules(self, client) -> None:
        """GET /rules → list of validation rules."""
        resp = client.get("/api/v1/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Each rule has id, name, level
        first = data[0]
        assert "id" in first
        assert "name" in first
        assert "level" in first

    def test_list_rules_has_spec_and_code(self, client) -> None:
        """Rules list contains both spec and code rules."""
        resp = client.get("/api/v1/rules")
        data = resp.json()
        levels = {r["level"] for r in data}
        assert "spec" in levels
        assert "code" in levels
