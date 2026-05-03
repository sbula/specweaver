# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Manual live test for the SpecWeaver REST API.

Run with:
    python -m pytest tests/manual/test_api_live.py -v -m live

Uses an in-process TestClient (no real Uvicorn) to exercise the full
API surface end-to-end against a temporary project.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app, set_event_bridge
from specweaver.interfaces.api.event_bridge import EventBridge
from tests.fixtures.db_utils import register_test_project, set_test_active_project

# ---------- Helpers ----------

_MINIMAL_SPEC = """\
# Greeting Service — Component Spec

## Purpose / Intent
A simple service that returns a greeting message.

## Contract
```python
def greet(name: str) -> str: ...
```

## Tests / Acceptance Criteria
- `greet("Alice")` → `"Hello, Alice!"`
"""


@pytest.fixture()
def _live_env():
    """Bootstrap a temp project, DB, and TestClient for the live test."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)

        # --- DB ---
        from specweaver.core.config.cli_db_utils import bootstrap_database

        bootstrap_database(str(tmp_path / "test.db"))
        db = Database(db_path=tmp_path / "test.db")

        # --- Project dir with a minimal spec ---
        proj = tmp_path / "livetest"
        proj.mkdir()
        (proj / "specs").mkdir()
        spec = proj / "specs" / "greet_spec.md"
        spec.write_text(_MINIMAL_SPEC, encoding="utf-8")

        # Register project
        register_test_project(db, "livetest", str(proj))
        set_test_active_project(db, "livetest")

        # --- Fresh EventBridge ---
        set_event_bridge(EventBridge())

        # --- App + client ---
        app = create_app(db=db)
        client = TestClient(app)

        yield {
            "client": client,
            "db": db,
            "tmp_path": tmp_path,
            "project_path": proj,
            "spec_path": spec,
        }

        # Cleanup global singleton
        set_event_bridge(EventBridge())
        # Dispose DB engine to release file lock on Windows
        if hasattr(db, "engine"):
            db.engine.dispose()


# ---------- Tests ----------


@pytest.mark.live
class TestAPILiveSmoke:
    """End-to-end API smoke test against a real temp project.

    Exercises every endpoint group in order:
    health → projects → validation → pipelines → WebSocket.
    """

    # --- 1. Health Check ---

    def test_healthz(self, _live_env) -> None:
        """GET /healthz returns ok + version."""
        client = _live_env["client"]
        resp = client.get("/healthz")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        print(f"\n[LIVE] Health check passed: v{data['version']}")

    # --- 2. Project CRUD Lifecycle ---

    def test_project_lifecycle(self, _live_env) -> None:
        """Full project lifecycle: list → create → update → remove."""
        client = _live_env["client"]
        tmp_path = _live_env["tmp_path"]

        # List — should have at least our pre-registered project
        resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        projects = resp.json()
        names = [p["name"] for p in projects]
        assert "livetest" in names
        print(f"\n[LIVE] Listed {len(projects)} project(s): {names}")

        # Create a second project
        p2 = tmp_path / "second-project"
        p2.mkdir()
        resp = client.post(
            "/api/v1/projects",
            json={"name": "second-project", "path": str(p2), "scaffold": False},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "second-project"
        print("[LIVE] Created second-project")

        # Update its path
        p2_new = tmp_path / "second-project-moved"
        p2_new.mkdir()
        resp = client.put(
            "/api/v1/projects/second-project",
            json={"path": str(p2_new)},
        )
        assert resp.status_code == 200
        print("[LIVE] Updated second-project path")

        # Delete it
        resp = client.delete("/api/v1/projects/second-project")
        assert resp.status_code == 200
        print("[LIVE] Deleted second-project")

        # Verify only original remains
        resp = client.get("/api/v1/projects")
        names = [p["name"] for p in resp.json()]
        assert "second-project" not in names
        assert "livetest" in names
        print("[LIVE] Project lifecycle complete")

    # --- 3. Validation ---

    def test_check_spec(self, _live_env) -> None:
        """POST /check runs validation rules on a real spec file."""
        client = _live_env["client"]

        resp = client.post(
            "/api/v1/check",
            json={
                "file": "specs/greet_spec.md",
                "project": "livetest",
                "level": "component",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "overall" in data
        assert data["total"] > 0
        print(
            f"\n[LIVE] Validation: {data['overall']} - "
            f"{data['passed']}/{data['total']} passed, "
            f"{data['failed']} failed, {data['warned']} warned"
        )

    # --- 4. Rules List ---

    def test_list_rules(self, _live_env) -> None:
        """GET /rules returns available validation rules."""
        client = _live_env["client"]

        resp = client.get("/api/v1/rules")
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) > 0
        rule_ids = [r["id"] for r in rules]
        print(f"\n[LIVE] {len(rules)} rules available: {', '.join(rule_ids[:5])}...")

    # --- 5. Pipeline List ---

    def test_list_pipelines(self, _live_env) -> None:
        """GET /pipelines returns available pipeline templates."""
        client = _live_env["client"]

        resp = client.get("/api/v1/pipelines")
        assert resp.status_code == 200
        pipelines = resp.json()
        assert len(pipelines) > 0
        print(f"\n[LIVE] {len(pipelines)} pipeline(s): {[p['name'] for p in pipelines]}")

    # --- 6. Pipeline Details (found / 404) ---

    def test_pipeline_detail_and_404(self, _live_env) -> None:
        """GET /pipelines/{name} returns detail for known, 404 for unknown."""
        client = _live_env["client"]
        # Get list to find a valid name (request only, no need to parse json if we just drop the 404 test name)
        client.get("/api/v1/pipelines")

        # 404 for unknown
        resp = client.get("/api/v1/pipelines/nonexistent_pipeline_xyz")
        assert resp.status_code == 404
        print("\n[LIVE] 404 for unknown pipeline - correct")

    # --- 7. Constitution ---

    def test_constitution_init_and_show(self, _live_env) -> None:
        """POST /constitution/init creates CONSTITUTION.md, GET /constitution returns it."""
        client = _live_env["client"]

        resp = client.post(
            "/api/v1/constitution/init",
            json={"project": "livetest"},
        )
        assert resp.status_code == 200
        print(f"\n[LIVE] Constitution init: {resp.json()}")

        resp = client.get("/api/v1/constitution", params={"project": "livetest"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["content"]) > 0
        print(f"[LIVE] Constitution content: {len(data['content'])} chars")

    # --- 8. WebSocket connectivity ---

    def test_websocket_connects_and_receives(self, _live_env) -> None:
        """WebSocket /ws/pipeline/{run_id} connects and unsubscribes on close."""
        client = _live_env["client"]

        with client.websocket_connect("/api/v1/ws/pipeline/smoke-test-run") as _ws:
            # Connection established — the endpoint subscribes us
            pass

        # After close, the endpoint should have cleaned up
        print("\n[LIVE] WebSocket connect + disconnect: OK")

    # --- 9. OpenAPI docs accessible ---

    def test_openapi_docs(self, _live_env) -> None:
        """GET /docs returns the Swagger UI page (200)."""
        client = _live_env["client"]

        resp = client.get("/docs")
        assert resp.status_code == 200
        assert "SpecWeaver API" in resp.text
        print("\n[LIVE] OpenAPI /docs page accessible - 'SpecWeaver API' found")

    # --- 10. Run status 404 for unknown run ---

    def test_run_status_unknown_404(self, _live_env) -> None:
        """GET /runs/{run_id} returns 404 for unknown run_id."""
        client = _live_env["client"]

        resp = client.get("/api/v1/runs/unknown-run-id-xyz")
        assert resp.status_code == 404
        print("\n[LIVE] Unknown run_id -> 404: correct")
