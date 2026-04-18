# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the UI (Web Dashboard) endpoints."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app


@pytest.fixture()
def client(tmp_path):
    """TestClient for the API."""
    db = Database(db_path=tmp_path / "test.db")
    app = create_app(db=db)
    return TestClient(app)


def test_root_redirects_to_dashboard(client) -> None:
    """GET / redirects to /dashboard."""
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (307, 308, 301, 302)
    assert resp.headers["location"] == "/dashboard"


def test_render_markdown_none() -> None:
    """_render_markdown handles None input."""
    from specweaver.interfaces.api.ui.routes import _render_markdown

    assert _render_markdown(None) == ""


def test_render_markdown_content() -> None:
    """_render_markdown parses basic markdown and sanitizes tags."""
    from specweaver.interfaces.api.ui.routes import _render_markdown

    html = _render_markdown("**Bold** and <script>alert(1)</script>")
    assert "<strong>Bold</strong>" in html
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_get_dashboard(client) -> None:
    """GET /dashboard returns HTML UI."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    text = resp.text
    assert "<!DOCTYPE html>" in text
    assert "SpecWeaver" in text
    assert "Projects" in text


def test_get_dashboard_runs(client) -> None:
    """GET /dashboard/runs returns HTML UI."""
    resp = client.get("/dashboard/runs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    text = resp.text
    assert "Pipeline Runs" in text


def test_get_dashboard_run_detail_404(client) -> None:
    """GET /dashboard/runs/unknown returns 404."""
    resp = client.get("/dashboard/runs/fake-run-id-000")
    assert resp.status_code == 404


def test_get_dashboard_run_detail(client, tmp_path) -> None:
    """GET /dashboard/runs/{id} returns HTML details."""
    from pathlib import Path
    from unittest.mock import patch

    from specweaver.core.flow.engine.state import (
        PipelineRun,
        RunStatus,
        StepRecord,
        StepResult,
        StepStatus,
    )
    from specweaver.core.flow.engine.store import StateStore

    run = PipelineRun(
        run_id="test-run-ui-1",
        pipeline_name="validate_only",
        project_name="myproject",
        spec_path="/fake/spec.md",
        status=RunStatus.PARKED,
        current_step=0,
        step_records=[
            StepRecord(
                step_name="review_code",
                status=StepStatus.WAITING_FOR_INPUT,
                result=StepResult(
                    status=StepStatus.WAITING_FOR_INPUT,
                    output={"comment": "**Please approve**"},
                    started_at="2026-01-01T00:00:00",
                    completed_at="2026-01-01T00:00:01",
                ),
            )
        ],
        started_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:01",
    )

    with patch.object(Path, "home", return_value=tmp_path):
        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")
        store.save_run(run)
        store.log_event("test-run-ui-1", "test_event")

        resp = client.get("/dashboard/runs/test-run-ui-1")
        assert resp.status_code == 200
        text = resp.text
        assert "test-run-ui-1" in text
        assert "Human Action Required" in text
        # Check markdown rendering
        assert "<strong>Please approve</strong>" in text
        assert "test_event" in text


def test_get_dashboard_run_detail_non_parked(client, tmp_path) -> None:
    """GET /dashboard/runs/{id} handles non-parked runs (pending_gate False)."""
    from pathlib import Path
    from unittest.mock import patch

    from specweaver.core.flow.engine.state import PipelineRun, RunStatus
    from specweaver.core.flow.engine.store import StateStore

    run = PipelineRun(
        run_id="test-run-ui-2",
        pipeline_name="validate_only",
        project_name="myproject",
        spec_path="/fake/spec.md",
        status=RunStatus.RUNNING,
        current_step=0,
        step_records=[],
        started_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:01",
    )

    with patch.object(Path, "home", return_value=tmp_path):
        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")
        store.save_run(run)

        resp = client.get("/dashboard/runs/test-run-ui-2")
        assert resp.status_code == 200
        text = resp.text
        assert "test-run-ui-2" in text
        assert "Human Action Required" not in text


def test_get_dashboard_run_detail_string_output(client, tmp_path) -> None:
    """GET /dashboard/runs/{id} handles parked runs with string output."""
    from pathlib import Path
    from unittest.mock import patch

    from specweaver.core.flow.engine.state import (
        PipelineRun,
        RunStatus,
        StepRecord,
        StepResult,
        StepStatus,
    )

    run = PipelineRun(
        run_id="test-run-ui-3",
        pipeline_name="validate_only",
        project_name="myproject",
        spec_path="/fake/spec.md",
        status=RunStatus.PARKED,
        current_step=0,
        step_records=[
            StepRecord(
                step_name="review_code",
                status=StepStatus.WAITING_FOR_INPUT,
                result=StepResult.model_construct(
                    status=StepStatus.WAITING_FOR_INPUT,
                    output="Plain string output requiring attention",
                    started_at="2026-01-01T00:00:00",
                    completed_at="2026-01-01T00:00:01",
                ),
            )
        ],
        started_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:01",
    )

    with (
        patch.object(Path, "home", return_value=tmp_path),
        patch("specweaver.core.flow.engine.store.StateStore") as mock_cls,
    ):
        mock_store = mock_cls.return_value
        mock_store.load_run.return_value = run

        resp = client.get("/dashboard/runs/test-run-ui-3")
        assert resp.status_code == 200
        text = resp.text
        assert "Human Action Required" in text
        assert "Plain string output requiring attention" in text


def test_submit_hitl_gate(tmp_path) -> None:
    """POST /dashboard/runs/{id}/gate resolves gate via EventBridge."""
    from pathlib import Path
    from unittest.mock import patch

    from starlette.testclient import TestClient

    from specweaver.core.config.database import Database
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.interfaces.api import app as api_app
    from specweaver.interfaces.api.app import create_app
    from specweaver.interfaces.api.event_bridge import EventBridge

    # Set up DB and project
    db = Database(db_path=tmp_path / "test.db")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at) VALUES (?, ?, ?, ?)",
            ("myproject", str(tmp_path), "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO active_state (key, value) VALUES (?, ?)",
            ("active_project", "myproject"),
        )

    app = create_app(db=db)
    client = TestClient(app)

    # Set up pipeline definitions to prevent FileNotFoundError
    pipeline_def_dir = tmp_path / "validate_only"
    pipeline_def_dir.mkdir()
    (pipeline_def_dir / "pipeline.yaml").write_text("name: validate_only\nsteps: []")

    # Set up spec
    (tmp_path / "fake_spec.md").write_text("# Spec")

    run = PipelineRun(
        run_id="test-gate-1",
        pipeline_name=str(pipeline_def_dir / "pipeline.yaml"),
        project_name="myproject",
        spec_path="fake_spec.md",
        status=RunStatus.PARKED,
        current_step=0,
        step_records=[],
        started_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:01",
    )

    bridge = EventBridge()

    with (
        patch.object(Path, "home", return_value=tmp_path),
        patch.object(api_app, "get_event_bridge", return_value=bridge),
        patch.object(bridge, "start_run") as mock_start_run,
    ):
        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")
        store.save_run(run)

        # Submit HTMX post
        resp = client.post(
            "/dashboard/runs/test-gate-1/gate",
            data={"action": "approve"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Refresh") == "true"

        # Check audit log
        events = store.get_audit_log("test-gate-1")
        assert len(events) == 1
        assert events[0]["event"] == "gate_approve"

        # Check start_run was called
        mock_start_run.assert_called_once()


def test_submit_hitl_gate_invalid_action(tmp_path) -> None:
    """POST /dashboard/runs/{id}/gate with invalid action returns 400."""
    from pathlib import Path
    from unittest.mock import patch

    from starlette.testclient import TestClient

    from specweaver.core.config.database import Database
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.interfaces.api.app import create_app

    db = Database(db_path=tmp_path / "test.db")
    app = create_app(db=db)
    client = TestClient(app)

    run = PipelineRun(
        run_id="test-gate-error-1",
        pipeline_name="validate_only",
        project_name="myproject",
        spec_path="fake_spec.md",
        status=RunStatus.PARKED,
        current_step=0,
        step_records=[],
        started_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:01",
    )

    with patch.object(Path, "home", return_value=tmp_path):
        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")
        store.save_run(run)

        resp = client.post(
            "/dashboard/runs/test-gate-error-1/gate",
            data={"action": "fake-action"},
        )
        assert resp.status_code == 400
        assert "fake-action" in resp.json()["detail"]
