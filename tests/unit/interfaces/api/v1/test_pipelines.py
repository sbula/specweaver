# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for pipeline execution API endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app
from tests.fixtures.db_utils import register_test_project


@pytest.fixture()
def _db(tmp_path):
    """Creates a temp database with a registered project."""
    from specweaver.interfaces.cli._db_utils import bootstrap_database

    bootstrap_database(str(tmp_path / "test.db"))
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
    register_test_project(_db, "myproject", str(proj))
    return proj, spec


@pytest.fixture()
def client(_db):
    """TestClient for the API."""
    app = create_app(db=_db)
    return TestClient(app)


import anyio


def _set_domain_profile_sync(db, project: str, profile: str) -> None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.set_domain_profile(project, profile)

    anyio.run(_do)


def _get_domain_profile_sync(db, project: str) -> str | None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            return await repo.get_domain_profile(project)

    return anyio.run(_do)


def _create_llm_profile_sync(
    db,
    name: str,
    provider: str,
    model: str,
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
) -> int:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.create_llm_profile(
                name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format="text",
            )

    return anyio.run(_do)


def _link_project_profile_sync(db, project: str, task: str, profile_id: int) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.link_project_profile(project, task, profile_id)

    anyio.run(_do)


def _set_cost_override_sync(db, model: str, in_cost: float, out_cost: float) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.set_cost_override(model, in_cost, out_cost)

    anyio.run(_do)


def _get_cost_overrides_sync(db) -> dict:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.get_cost_overrides()

    return anyio.run(_do)


import asyncio


def _sync_run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio

            nest_asyncio.apply(loop)
            return loop.run_until_complete(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _set_domain_profile_sync(db, project: str, profile: str) -> None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            await repo.set_domain_profile(project, profile)

    _sync_run(_do())


def _get_domain_profile_sync(db, project: str) -> str | None:
    from specweaver.workspace.store import WorkspaceRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            return await repo.get_domain_profile(project)

    return _sync_run(_do())


def _create_llm_profile_sync(
    db,
    name: str,
    provider: str,
    model: str,
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
) -> int:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.create_llm_profile(
                name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_format="text",
            )

    return _sync_run(_do())


def _link_project_profile_sync(db, project: str, task: str, profile_id: int) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.link_project_profile(project, task, profile_id)

    _sync_run(_do())


def _set_cost_override_sync(db, model: str, in_cost: float, out_cost: float) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            await repo.set_cost_override(model, in_cost, out_cost)

    _sync_run(_do())


def _get_cost_overrides_sync(db) -> dict:
    from specweaver.infrastructure.llm.store import LlmRepository

    async def _do():
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            return await repo.get_cost_overrides()

    return _sync_run(_do())


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
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus
        from specweaver.core.flow.engine.store import StateStore

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
            assert data.get("pending_gate") is False

    def test_parked_run_exposes_pending_gate(self, client, tmp_path) -> None:
        """GET /runs/{id} for a RUNNING or PARKED run exposes pending_gate fields."""
        from specweaver.core.flow.engine.state import (
            PipelineRun,
            RunStatus,
            StepRecord,
            StepResult,
            StepStatus,
        )
        from specweaver.core.flow.engine.store import StateStore

        store = StateStore(tmp_path / "state2.db")
        run = PipelineRun(
            run_id="test-run-2",
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
                        output={"comment": "Please approve this spec."},
                        started_at="2026-01-01T00:00:00",
                        completed_at="2026-01-01T00:00:01",
                    ),
                )
            ],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        with patch.object(Path, "home", return_value=tmp_path):
            state_dir = tmp_path / ".specweaver"
            state_dir.mkdir(exist_ok=True)
            store2 = StateStore(state_dir / "pipeline_state.db")
            store2.save_run(run)

            resp = client.get("/api/v1/runs/test-run-2")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "parked"
            assert data["pending_gate"] is True
            assert "Please approve this spec." in data["pending_gate_prompt"]

    def test_parked_run_exposes_pending_gate_string_output(self, client, tmp_path) -> None:
        """GET /runs/{id} correctly handles string outputs when creating pending_gate_prompt."""
        from unittest.mock import patch

        from specweaver.core.flow.engine.state import (
            PipelineRun,
            RunStatus,
            StepRecord,
            StepResult,
            StepStatus,
        )

        run = PipelineRun.model_construct(
            run_id="test-run-3",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.PARKED,
            current_step=0,
            step_records=[
                StepRecord.model_construct(
                    step_name="review_code",
                    status=StepStatus.WAITING_FOR_INPUT,
                    result=StepResult.model_construct(
                        status=StepStatus.WAITING_FOR_INPUT,
                        output="String fallback prompt",
                        started_at="2026-01-01T00:00:00",
                        completed_at="2026-01-01T00:00:01",
                    ),
                )
            ],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )

        from pathlib import Path

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch("specweaver.core.flow.engine.store.StateStore") as mock_cls,
        ):
            mock_store = mock_cls.return_value
            mock_store.load_run.return_value = run
            resp = client.get("/api/v1/runs/test-run-3")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "parked"
            assert data["pending_gate"] is True
            assert "String fallback prompt" in data["pending_gate_prompt"]


class TestGetRunLog:
    """Tests for GET /api/v1/runs/{run_id}/log."""

    def test_unknown_run_log_returns_404(self, client) -> None:
        """GET /runs/unknown/log → 404."""
        resp = client.get("/api/v1/runs/fake-run-id-000/log")
        assert resp.status_code == 404

    def test_known_run_log_returns_events(self, client, tmp_path) -> None:
        """GET /runs/{id}/log returns audit events."""
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus
        from specweaver.core.flow.engine.store import StateStore

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
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus
        from specweaver.core.flow.engine.store import StateStore

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
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus
        from specweaver.core.flow.engine.store import StateStore

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

    # --- Gap #38: gate on non-parked run → 409 ---

    def test_gate_non_parked_run_returns_409(self, client, tmp_path) -> None:
        """POST /runs/{id}/gate on a running (non-parked) run → 409."""
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus
        from specweaver.core.flow.engine.store import StateStore

        state_dir = tmp_path / ".specweaver"
        state_dir.mkdir(exist_ok=True)
        store = StateStore(state_dir / "pipeline_state.db")

        run = PipelineRun(
            run_id="test-run-1",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.RUNNING,
            current_step=0,
            step_records=[],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        with patch.object(Path, "home", return_value=tmp_path):
            resp = client.post(
                "/api/v1/runs/test-run-1/gate",
                json={"action": "approve"},
            )
            assert resp.status_code == 409


def _make_state_store(tmp_path: Path) -> tuple:
    """Helper: create StateStore + .specweaver dir at tmp_path."""
    from specweaver.core.flow.engine.store import StateStore

    state_dir = tmp_path / ".specweaver"
    state_dir.mkdir(exist_ok=True)
    return StateStore(state_dir / "pipeline_state.db"), state_dir


def _make_parked_run(
    store,
    run_id: str = "test-run-1",
    project: str = "myproject",
    spec: str = "/fake/spec.md",
):
    """Helper: create and save a PARKED PipelineRun."""
    from specweaver.core.flow.engine.state import PipelineRun, RunStatus

    run = PipelineRun(
        run_id=run_id,
        pipeline_name="validate_only",
        project_name=project,
        spec_path=spec,
        status=RunStatus.PARKED,
        current_step=0,
        step_records=[],
        started_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:01",
    )
    store.save_run(run)
    return run


class TestGetRunStatusModes:
    """Tests for GET /runs/{run_id} detail modes (#33, #34)."""

    def test_summary_mode_strips_output(self, client, tmp_path) -> None:
        """detail=summary strips output from step result records."""
        from specweaver.core.flow.engine.state import (
            PipelineRun,
            RunStatus,
            StepRecord,
            StepResult,
            StepStatus,
        )

        store, _state_dir = _make_state_store(tmp_path)
        run = PipelineRun(
            run_id="run-detail-1",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.COMPLETED,
            current_step=1,
            step_records=[
                StepRecord(
                    step_name="validate",
                    result=StepResult(
                        status=StepStatus.PASSED,
                        output={"big": "payload"},
                        started_at="2026-01-01T00:00:00",
                        completed_at="2026-01-01T00:00:01",
                    ),
                ),
            ],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        with patch.object(Path, "home", return_value=tmp_path):
            resp = client.get("/api/v1/runs/run-detail-1?detail=summary")
            assert resp.status_code == 200
            data = resp.json()
            # output should be stripped in summary mode
            result = data["step_records"][0]["result"]
            assert "output" not in result

    def test_full_mode_includes_output(self, client, tmp_path) -> None:
        """detail=full includes output in step result records."""
        from specweaver.core.flow.engine.state import (
            PipelineRun,
            RunStatus,
            StepRecord,
            StepResult,
            StepStatus,
        )

        store, _state_dir = _make_state_store(tmp_path)
        run = PipelineRun(
            run_id="run-detail-2",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.COMPLETED,
            current_step=1,
            step_records=[
                StepRecord(
                    step_name="validate",
                    result=StepResult(
                        status=StepStatus.PASSED,
                        output={"big": "payload"},
                        started_at="2026-01-01T00:00:00",
                        completed_at="2026-01-01T00:00:01",
                    ),
                ),
            ],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        with patch.object(Path, "home", return_value=tmp_path):
            resp = client.get("/api/v1/runs/run-detail-2?detail=full")
            assert resp.status_code == 200
            data = resp.json()
            result = data["step_records"][0]["result"]
            assert result["output"] == {"big": "payload"}


class TestResumeRun:
    """Tests for POST /api/v1/runs/{run_id}/resume (#35-37, #41)."""

    def test_resume_unknown_run_returns_404(self, client) -> None:
        """POST /runs/unknown/resume → 404."""
        resp = client.post("/api/v1/runs/fake-run-id-000/resume")
        assert resp.status_code == 404

    def test_resume_non_parked_run_returns_409(self, client, tmp_path) -> None:
        """POST /runs/{id}/resume on a running run → 409."""
        from specweaver.core.flow.engine.state import PipelineRun, RunStatus

        store, _state_dir = _make_state_store(tmp_path)
        run = PipelineRun(
            run_id="test-run-1",
            pipeline_name="validate_only",
            project_name="myproject",
            spec_path="/fake/spec.md",
            status=RunStatus.RUNNING,
            current_step=0,
            step_records=[],
            started_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:01",
        )
        store.save_run(run)

        with patch.object(Path, "home", return_value=tmp_path):
            resp = client.post("/api/v1/runs/test-run-1/resume")
            assert resp.status_code == 409


class TestMaxConcurrent:
    """Tests for 429 (max concurrent) on start, resume, and gate-approve (#32, #41, #42)."""

    def test_start_run_max_concurrent_returns_429(
        self, client, _project_with_spec, tmp_path
    ) -> None:
        """POST /pipelines/{name}/run at max concurrent → 429."""
        from specweaver.interfaces.api.app import set_event_bridge
        from specweaver.interfaces.api.event_bridge import EventBridge

        bridge = EventBridge(max_concurrent=0)
        set_event_bridge(bridge)

        try:
            with (
                patch.object(Path, "home", return_value=tmp_path),
                patch("specweaver.core.flow.engine.parser.load_pipeline") as mock_load,
            ):
                mock_load.return_value = type("P", (), {"name": "test", "steps": []})()
                resp = client.post(
                    "/api/v1/pipelines/validate_only/run",
                    json={"project": "myproject", "spec": "specs/test_spec.md"},
                )
                assert resp.status_code == 429
        finally:
            set_event_bridge(EventBridge())


class TestStartRunResponse:
    """Tests for POST /pipelines/{name}/run response (#62)."""

    def test_start_run_returns_run_id_and_detail(
        self, client, _project_with_spec, tmp_path
    ) -> None:
        """Successful pipeline start returns run_id and detail in body."""
        from unittest.mock import MagicMock

        from specweaver.interfaces.api.event_bridge import EventBridge

        mock_bridge = MagicMock(spec=EventBridge)
        mock_bridge.start_run = MagicMock()
        mock_bridge.make_event_callback = MagicMock(return_value=lambda *a, **kw: None)

        with (
            patch.object(Path, "home", return_value=tmp_path),
            patch(
                "specweaver.interfaces.api.app.get_event_bridge",
                return_value=mock_bridge,
            ),
            patch("specweaver.core.flow.engine.parser.load_pipeline") as mock_load,
        ):
            mock_load.return_value = type("P", (), {"name": "test", "steps": []})()

            resp = client.post(
                "/api/v1/pipelines/validate_only/run",
                json={"project": "myproject", "spec": "specs/test_spec.md"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "run_id" in data
            assert "detail" in data
            assert len(data["run_id"]) > 0
            mock_bridge.start_run.assert_called_once()
