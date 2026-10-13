# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each run on a spec works one memory task, so the next run gets the notes of the last.

Proves: D-INTL-06 FR-10

Real `sw init`, real `sw run` of a bash pipeline, the real database.

| Bucket | Case |
|---|---|
| Happy | a passing run creates the spec's task, saves its handover and marks it DONE |
| Boundary | a second run on the same spec reuses the task |
| Degradation | a failing run marks the task BLOCKED, and the next run reopens it |
| Hostile | a run on another spec gets a task of its own; a review works none |
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e
runner = CliRunner()

_PIPELINE = """name: one_step
version: "1.0"
steps:
  - name: go
    action: bash
    target: script
    params: {script: go.sh}
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    assert runner.invoke(app, ["init", "memory-demo", "--path", str(tmp_path)]).exit_code == 0
    for name in ("a_spec.md", "b_spec.md"):
        (tmp_path / "specs" / name).write_text("# A\n", encoding="utf-8")
    (tmp_path / "one_step.yaml").write_text(_PIPELINE, encoding="utf-8")
    return tmp_path


def _run(project: Path, spec: str, exit_code: int) -> None:
    script = project / ".specweaver" / "scripts" / "go.sh"
    script.write_text(f"#!/usr/bin/env bash\nexit {exit_code}\n", encoding="utf-8")
    runner.invoke(
        app,
        ["run", str(project / "one_step.yaml"), f"specs/{spec}", "--project", str(project)],
    )


def _tasks(data_dir: Path) -> list[tuple[str, str, str | None]]:
    with sqlite3.connect(data_dir / "specweaver.db") as conn:
        return conn.execute(
            "SELECT title, status, handover_context FROM memory_tasks ORDER BY created_at"
        ).fetchall()


def test_a_passing_run_leaves_a_done_task_with_its_handover(
    project: Path, _isolate_env: Path
) -> None:
    _run(project, "a_spec.md", 0)

    [(title, status, handover)] = _tasks(_isolate_env)
    assert (title, status) == ("specs/a_spec.md", "DONE")
    assert json.loads(handover)["metadata"]["pipeline_name"] == "one_step"


def test_the_same_spec_reuses_its_task(project: Path, _isolate_env: Path) -> None:
    _run(project, "a_spec.md", 0)
    _run(project, "a_spec.md", 0)

    assert [t[:2] for t in _tasks(_isolate_env)] == [("specs/a_spec.md", "DONE")]


def test_a_failing_run_blocks_the_task_and_the_next_run_reopens_it(
    project: Path, _isolate_env: Path
) -> None:
    _run(project, "a_spec.md", 3)
    assert [t[:2] for t in _tasks(_isolate_env)] == [("specs/a_spec.md", "BLOCKED")]

    _run(project, "a_spec.md", 0)
    assert [t[:2] for t in _tasks(_isolate_env)] == [("specs/a_spec.md", "DONE")]


def test_another_spec_gets_its_own_task(project: Path, _isolate_env: Path) -> None:
    _run(project, "a_spec.md", 0)
    _run(project, "b_spec.md", 0)

    assert sorted(t[0] for t in _tasks(_isolate_env)) == ["specs/a_spec.md", "specs/b_spec.md"]


def test_the_next_run_reads_the_last_runs_notes(project: Path, _isolate_env: Path) -> None:
    """A failed run's task is a blocker; reopened by the next run, its handover is in the memory."""
    import asyncio

    from specweaver.core.config.database import Database
    from specweaver.core.flow.engine.run_task import open_task
    from specweaver.core.flow.engine.state import PipelineRun
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.workspace.memory.hydrator import MemoryHydrator

    _run(project, "a_spec.md", 3)
    db = Database(_isolate_env / "specweaver.db")

    async def memory() -> dict:
        async with db.async_session_scope() as session:
            block = (await MemoryHydrator(session, "memory-demo").hydrate()).format_prompt_block()
        return json.loads(block.split(">", 1)[1].rsplit("<", 1)[0])

    assert [b["task_title"] for b in asyncio.run(memory())["blockers"]] == ["specs/a_spec.md"]

    context = RunContext(project_path=project, spec_path=project / "specs" / "a_spec.md", db=db)
    run = PipelineRun(
        run_id="next",
        pipeline_name="next",
        project_name="memory-demo",
        spec_path="specs/a_spec.md",
        started_at="2026-10-13T00:00:00Z",
        updated_at="2026-10-13T00:00:00Z",
    )
    asyncio.run(open_task(context, run))

    notes = asyncio.run(memory())["handover_notes"]
    assert notes and "exited 3" in " ".join(notes), notes


def test_a_review_works_no_task(project: Path, _isolate_env: Path) -> None:
    """A review is not work on the spec: it would mark a failed implementation DONE."""
    from specweaver.infrastructure.llm.models import LLMResponse
    from tests.scripted_llm import doubled_llm

    class _Model:
        def available(self) -> bool:
            return True

        async def generate(self, *_a, **_k) -> LLMResponse:
            return LLMResponse(text="VERDICT: ACCEPTED\nFine.", model="m")

        async def generate_with_tools(self, *_a, **_k) -> LLMResponse:
            return await self.generate()

    with doubled_llm(_Model()):
        runner.invoke(
            app, ["review", str(project / "specs" / "a_spec.md"), "--project", str(project)]
        )

    assert _tasks(_isolate_env) == []
