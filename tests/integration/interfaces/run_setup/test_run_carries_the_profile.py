# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run builder decides the project's profile once, with both pins, and the run carries it.

Proves: TECH-079 FR-7, TECH-079 FR-8

A real database, real project folders and settings files; no model step, so no model.

| Bucket | Case |
|---|---|
| Happy | a Python root carries python/uv; a pinned mixed root carries the pin, and its task files and allow-list follow it |
| Boundary | the `build_tool` pin reaches the decision; an undecided root still builds a run that does not need the profile |
| Degradation | the undecided run keeps the refusal, and the first ask raises it |
| Hostile | a door that needs the profile gets the refusal from the builder; session isolation on an undecided root refuses the run instead of running without it |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.project_profile import ProjectProfile, ProjectUndecidedError
from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
from specweaver.core.flow.engine.run_profile import run_profile, run_task_files
from specweaver.interfaces.run_setup.builder import RunRequest, build_run_sync
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_MIXED = {
    "pyproject.toml": "[project]\nname = 'x'\n",
    "package.json": "{}",
    "tsconfig.json": "{}",
}


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    return Database(data / "specweaver.db")


def _project(db: Database, tmp_path: Path, files: dict[str, str], settings: str = "") -> Path:
    root = tmp_path / "proj"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "orders_spec.md").write_text("# Orders\n", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    if settings:
        (root / "specweaver.toml").write_text(settings, encoding="utf-8")
    register_test_project(db, "proj", str(root))
    return root


def _build(db: Database, root: Path, **kw: object):
    pipeline = PipelineDefinition.create_single_step("one", StepAction.VALIDATE, StepTarget.SPEC)
    return build_run_sync(
        RunRequest(
            project_root=root,
            spec_path=root / "specs" / "orders_spec.md",
            pipeline=pipeline,
            project="proj",
            db=db,
            **kw,
        )
    )


def test_a_python_root_carries_python_with_uv(db: Database, tmp_path: Path) -> None:
    root = _project(db, tmp_path, {"pyproject.toml": "[project]\nname = 'x'\n"})

    context = _build(db, root)

    assert context.isolation.profile == ProjectProfile("python", "uv")
    assert context.isolation.undecided is None


def test_a_pinned_mixed_root_carries_the_pin_everywhere(db: Database, tmp_path: Path) -> None:
    settings = (
        '[implement]\nlanguage = "typescript"\n\n[sandbox]\nenforce_session_isolation = true\n'
    )
    root = _project(db, tmp_path, _MIXED, settings)
    (root / ".git").mkdir()

    context = _build(db, root)

    assert run_profile(context) == ProjectProfile("typescript", "npm")
    assert run_task_files(context).code == "src/orders.ts"
    assert "src/orders.ts" in context.isolation.allowed_paths


def test_the_build_tool_pin_reaches_the_decision(db: Database, tmp_path: Path) -> None:
    files = {"pom.xml": "<project/>", "build.gradle": ""}
    root = _project(db, tmp_path, files, '[implement]\nbuild_tool = "maven"\n')

    assert _build(db, root).isolation.profile == ProjectProfile("java", "maven")


def test_an_undecided_root_builds_a_run_that_keeps_the_refusal(
    db: Database, tmp_path: Path
) -> None:
    root = _project(db, tmp_path, _MIXED)

    context = _build(db, root)

    assert context.isolation.profile is None
    assert "set [implement] language" in (context.isolation.undecided or "")
    with pytest.raises(ProjectUndecidedError, match=r"package\.json"):
        run_profile(context)


def test_a_door_that_needs_the_profile_gets_the_refusal(db: Database, tmp_path: Path) -> None:
    root = _project(db, tmp_path, _MIXED)

    with pytest.raises(ProjectUndecidedError, match=r"set \[implement\] language"):
        _build(db, root, needs_profile=True)


def test_session_isolation_on_an_undecided_root_refuses_the_run(
    db: Database, tmp_path: Path
) -> None:
    """Q1 [agreed 2026-11-06]: the run never goes on without the isolation it asked for."""
    root = _project(db, tmp_path, _MIXED, "[sandbox]\nenforce_session_isolation = true\n")
    (root / ".git").mkdir()

    with pytest.raises(ProjectUndecidedError, match=r"set \[implement\] language"):
        _build(db, root)


def test_a_root_that_cannot_be_listed_keeps_a_refusal_naming_it(
    db: Database, tmp_path: Path
) -> None:
    """A registered folder removed since: the run keeps a refusal, never an OS traceback."""
    root = _project(db, tmp_path, {"pyproject.toml": ""})
    for entry in sorted(root.rglob("*"), reverse=True):
        entry.rmdir() if entry.is_dir() else entry.unlink()
    root.rmdir()

    context = _build(db, root)

    assert str(root) in (context.isolation.undecided or "")
