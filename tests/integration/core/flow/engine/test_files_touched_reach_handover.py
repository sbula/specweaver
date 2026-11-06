# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file a generate step writes reaches the run's saved handover.

Proves: TECH-082 FR-8

The seam: the code generator's output (`files_touched`) → the engine's handover → the memory bank.
Before FR-8 nothing wrote the key, so every saved handover listed no files. Only the model is
doubled; the registry, the handler, the runner and the database are real.

| Bucket | Case |
|---|---|
| Happy | the generated file is in the task's handover, relative to the project |
| Boundary | the path is relative, never absolute, and names a file that exists |
| Degradation | a failed generation records no file |
| Hostile | — (the path comes from the handler, not from input) |
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any

from sqlalchemy import create_engine

from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus
from specweaver.core.flow.handlers.base import ModelAccess
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.run_state.run_context import RunContext, RunHandle
from specweaver.workspace.memory.store import Task, TaskStatus
from specweaver.workspace.store import Base
from tests.scripted_llm import FixedRouter

_CODE = "def greet(name: str) -> str:\n    return f'Hello, {name}'\n"


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text
        self.content = text


class _FakeLLM:
    """Stands in for the paid API only."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def generate(self, messages: Any, config: Any = None) -> _Response:
        if not self._text:
            msg = "model unavailable"
            raise RuntimeError(msg)
        return _Response(self._text)


def _database(tmp_path: Path) -> tuple[Database, uuid.UUID]:
    db_path = tmp_path / "memory.db"
    sync_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(sync_engine)
    now = datetime.now(UTC)
    with sync_engine.begin() as conn:
        conn.execute(
            Base.metadata.tables["workspace_projects"]
            .insert()
            .values(name="greet", root_path=str(tmp_path), created_at=now, last_used_at=now)
        )
    sync_engine.dispose()
    db = Database(db_path)
    task_id = uuid.uuid4()

    async def _task() -> None:
        async with db.async_session_scope() as session:
            session.add(
                Task(
                    id=task_id,
                    title="Greet",
                    project_name="greet",
                    status=TaskStatus.IN_PROGRESS,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_task())
    return db, task_id


def _run(tmp_path: Path, model_text: str) -> tuple[Any, dict[str, Any]]:
    project = tmp_path / "greet"
    (project / "specs").mkdir(parents=True)
    (project / "pyproject.toml").write_text('[project]\nname = "x"\n')
    spec = project / "specs" / "greet_spec.md"
    spec.write_text("# Greet\n\n## 1. Purpose\n\nGreets a user by name.\n", encoding="utf-8")
    db, task_id = _database(tmp_path)
    context = RunContext(
        project_path=project,
        spec_path=spec,
        db=db,
        run=RunHandle(task_id=str(task_id)),
        model=ModelAccess(llm_router=FixedRouter(_FakeLLM(model_text))),
    )
    pipeline = PipelineDefinition(
        name="generate_only",
        steps=[
            PipelineStep(name="generate_code", action=StepAction.GENERATE, target=StepTarget.CODE)
        ],
    )
    run = asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())

    async def _handover() -> dict[str, Any]:
        async with db.async_session_scope() as session:
            task = await session.get(Task, task_id)
            assert task is not None
            assert task.handover_context is not None
            return dict(json.loads(task.handover_context))

    return run, asyncio.run(_handover())


def test_the_generated_file_reaches_the_handover(tmp_path: Path) -> None:
    run, handover = _run(tmp_path, _CODE)

    assert run.status == RunStatus.COMPLETED
    files = handover["files_touched"]
    assert len(files) == 1
    assert not PurePath(files[0]).is_absolute()
    written = tmp_path / "greet" / files[0]
    assert written.read_text(encoding="utf-8").startswith("def greet")


def test_a_failed_generation_records_no_file(tmp_path: Path) -> None:
    run, handover = _run(tmp_path, "")

    assert run.status == RunStatus.FAILED
    assert handover["files_touched"] == []
