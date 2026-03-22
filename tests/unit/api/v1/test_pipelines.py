# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for pipeline execution API endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from specweaver.api.app import create_app
from specweaver.config.database import Database


@pytest.fixture()
def _db(tmp_path):
    """Creates a temp database with a registered project."""
    db = Database(db_path=tmp_path / "test.db")
    return db


@pytest.fixture()
def _project_with_spec(tmp_path, _db):
    """Creates a project directory with a spec file."""
    proj = tmp_path / "myproject"
    proj.mkdir()
    spec = proj / "specs" / "test_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Test Spec\n", encoding="utf-8")
    _db.register_project("myproject", str(proj))
    return proj, spec


@pytest.fixture()
def client(_db):
    """TestClient for the API."""
    app = create_app(db=_db)
    return TestClient(app)


class TestListPipelines:
    """Tests for GET /api/v1/pipelines."""

    def test_list_pipelines_returns_list(self, client) -> None:
        """GET /pipelines returns available pipeline templates."""
        resp = client.get("/api/v1/pipelines")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]
        assert "source" in data[0]
        assert data[0]["source"] == "bundled"


class TestStartRun:
    """Tests for POST /api/v1/pipelines/{name}/run."""

    def test_missing_project_returns_404(self, client) -> None:
        """Run with unknown project → 404."""
        resp = client.post(
            "/api/v1/pipelines/validate_only/run",
            json={"project": "nonexistent", "spec": "test.md"},
        )
        assert resp.status_code == 404

    def test_missing_spec_returns_404(self, client, _project_with_spec) -> None:
        """Run with nonexistent spec → 404."""
        resp = client.post(
            "/api/v1/pipelines/validate_only/run",
            json={"project": "myproject", "spec": "no_such_file.md"},
        )
        assert resp.status_code == 404

    def test_unknown_pipeline_returns_404(self, client, _project_with_spec) -> None:
        """Run with unknown pipeline name → 404."""
        resp = client.post(
            "/api/v1/pipelines/nonexistent_pipeline/run",
            json={"project": "myproject", "spec": "specs/test_spec.md"},
        )
        assert resp.status_code == 404


class TestGetRunStatus:
    """Tests for GET /api/v1/runs/{run_id}."""

    def test_unknown_run_returns_404(self, client) -> None:
        """GET /runs/unknown → 404."""
        resp = client.get("/api/v1/runs/fake-run-id-000")
        assert resp.status_code == 404

    def test_known_run_returns_status(self, client, tmp_path) -> None:
        """GET /runs/{id} with a known run returns status data."""
        from specweaver.flow.state import PipelineRun, RunStatus
        from specweaver.flow.store import StateStore

        # Create a real state store with test data
        store = StateStore(tmp_path / "state.db")
        run = PipelineRun(
            run_id="test-run-1",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.COMPLETED,
            current_step=0,
            step_records=[],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        # Patch Path.home to point to tmp_path so the endpoint finds our store
        with patch.object(Path, "home", return_value=tmp_path):
            # Create the .specweaver dir and symlink/copy the state DB
            state_dir = tmp_path / ".specweaver"
            state_dir.mkdir(exist_ok=True)
            # Re-create store at the expected location
            store2 = StateStore(state_dir / "pipeline_state.db")
            store2.save_run(run)

            resp = client.get("/api/v1/runs/test-run-1")
            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == "test-run-1"
            assert data["status"] == "completed"


class TestGetRunLog:
    """Tests for GET /api/v1/runs/{run_id}/log."""

    def test_unknown_run_log_returns_404(self, client) -> None:
        """GET /runs/unknown/log → 404."""
        resp = client.get("/api/v1/runs/fake-run-id-000/log")
        assert resp.status_code == 404

    def test_known_run_log_returns_events(self, client, tmp_path) -> None:
        """GET /runs/{id}/log returns audit events."""
        from specweaver.flow.state import PipelineRun, RunStatus
        from specweaver.flow.store import StateStore

        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")

        run = PipelineRun(
            run_id="test-run-1",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.COMPLETED,
            current_step=0,
            step_records=[],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)
        store.log_event("test-run-1", "run_started")

        with patch.object(Path, "home", return_value=tmp_path):
            resp = client.get("/api/v1/runs/test-run-1/log")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) >= 1
            assert data[0]["event"] == "run_started"


class TestGateDecision:
    """Tests for POST /api/v1/runs/{run_id}/gate."""

    def test_gate_unknown_run_returns_404(self, client) -> None:
        """POST /runs/unknown/gate → 404."""
        resp = client.post(
            "/api/v1/runs/fake-run-id-000/gate",
            json={"action": "approve"},
        )
        assert resp.status_code == 404

    def test_gate_invalid_action_returns_400(self, client, tmp_path) -> None:
        """POST /runs/{id}/gate with invalid action → 400."""
        from specweaver.flow.state import PipelineRun, RunStatus
        from specweaver.flow.store import StateStore

        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")

        run = PipelineRun(
            run_id="test-run-1",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.PARKED,
            current_step=0,
            step_records=[],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        with patch.object(Path, "home", return_value=tmp_path):
            resp = client.post(
                "/api/v1/runs/test-run-1/gate",
                json={"action": "invalid_action"},
            )
            assert resp.status_code == 400

    def test_gate_reject_marks_failed(self, client, tmp_path) -> None:
        """POST /runs/{id}/gate with reject marks run as failed."""
        from specweaver.flow.state import PipelineRun, RunStatus
        from specweaver.flow.store import StateStore

        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")

        run = PipelineRun(
            run_id="test-run-1",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.PARKED,
            current_step=0,
            step_records=[],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        with patch.object(Path, "home", return_value=tmp_path):
            resp = client.post(
                "/api/v1/runs/test-run-1/gate",
                json={"action": "reject"},
            )
            assert resp.status_code == 200
            assert "rejected" in resp.json()["detail"].lower()
