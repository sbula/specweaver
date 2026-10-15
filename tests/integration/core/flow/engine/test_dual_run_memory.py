# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A dual run's memory stays out of every coder prompt; a coder's memory stays out of the scenarios.

Proves: B-FLOW-01 FR-12

A real database with the project, its task and memory; the real handover and the real scenario
handler, with a scripted model that records its prompts.

| Bucket | Case |
|---|---|
| Happy | a failed dual run's handover lands in the scenario store, with its errors |
| Boundary | the task memory a coder prompt reads gets nothing from the dual run |
| Degradation | not applicable — a dual run of an unregistered project never starts (FR-18) |
| Hostile | a coder's handover note never reaches the scenario generator's prompt |
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine

from specweaver.core.config.database import Database
from specweaver.core.flow.engine.handover import save_handover_context
from specweaver.core.flow.engine.models import PipelineStep
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.handlers.run_context import (
    AnalysisContext,
    GraphContext,
    GuidanceContent,
    ModelAccess,
    RunContext,
    RunHandle,
)
from specweaver.core.flow.handlers.scenario import GenerateScenarioHandler
from specweaver.workspace.memory.store import Task, TaskStatus
from specweaver.workspace.store import Base
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_SECRET = "coder-note-7f3k"


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Database, Path, uuid.UUID]:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "greeter"
    (root / "specs").mkdir(parents=True)
    db = Database(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(
            Base.metadata.tables["workspace_projects"]
            .insert()
            .values(name="greeter", root_path=str(root), created_at=now, last_used_at=now)
        )
    engine.dispose()
    task_id = uuid.uuid4()
    return db, root, task_id


async def _add_task(db: Database, task_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    async with db.async_session_scope() as session:
        session.add(
            Task(
                id=task_id,
                title="specs/greet_spec.md",
                project_name="greeter",
                status=TaskStatus.IN_PROGRESS,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


def _failed_dual_run() -> PipelineRun:
    now = datetime.now(UTC).isoformat()
    run = PipelineRun(
        run_id=str(uuid.uuid4()),
        pipeline_name="scenario_integration",
        project_name="greeter",
        spec_path="specs/greet_spec.md",
        started_at=now,
        updated_at=now,
        status=RunStatus.FAILED,
    )
    run.step_records.append(
        StepRecord(
            step_name="arbitrate_verdict",
            result=StepResult(
                status=StepStatus.FAILED,
                error_message="Arbiter assigned: the scenario expects 'hi' for an empty name",
                started_at=now,
                completed_at=now,
            ),
        )
    )
    return run


@pytest.mark.asyncio
async def test_a_dual_runs_handover_goes_to_the_store_not_to_memory(
    world: tuple[Database, Path, uuid.UUID], tmp_path: Path
) -> None:
    db, root, task_id = world
    await _add_task(db, task_id)
    run = _failed_dual_run()
    context = RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_spec.md",
        db=db,
        run=RunHandle(task_id=str(task_id), dual_side="parent"),
    )

    await save_handover_context(context, run)

    async with db.async_session_scope() as session:
        task = await session.get(Task, task_id)
    assert task is not None and task.handover_context is None
    kept = (
        tmp_path
        / "data"
        / "projects"
        / "greeter"
        / "scenarios"
        / "handovers"
        / f"{run.run_id}.json"
    )
    assert "Arbiter assigned" in kept.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_a_coders_note_never_reaches_the_scenario_prompt(
    world: tuple[Database, Path, uuid.UUID], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, root, task_id = world
    await _add_task(db, task_id)
    async with db.async_session_scope() as session:
        task = await session.get(Task, task_id)
        assert task is not None
        task.handover_context = json.dumps(
            {"summary": _SECRET, "files_touched": [], "errors_encountered": []}
        )
        await session.commit()
    (root / "specs" / "greet_spec.md").write_text(
        "# Greet\n\n## Functional Requirements\n\n| FR-1 | hi |\n"
    )
    llm = AsyncMock()
    llm.generate.return_value = json.dumps(
        {"spec_path": "specs/greet_spec.md", "contract_path": "c.py", "scenarios": []}
    )
    context = MagicMock(spec=RunContext)
    context.run = RunHandle(task_id=str(task_id))
    context.analysis, context.graph, context.guidance = (
        AnalysisContext(),
        GraphContext(),
        GuidanceContent(),
    )
    context.model = ModelAccess(llm_router=FixedRouter(llm), config=None)
    context.project_path, context.spec_path, context.db = root, root / "specs" / "greet_spec.md", db
    context.feedback, context.project_metadata = {}, None

    await GenerateScenarioHandler().execute(
        PipelineStep(name="generate_scenarios", action="generate", target="scenario"), context
    )

    prompts = " ".join(str(call) for call in llm.generate.call_args_list)
    assert llm.generate.call_count >= 1
    assert _SECRET not in prompts
