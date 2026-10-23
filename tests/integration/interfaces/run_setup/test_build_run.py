# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One builder sets up every part of a run from one project.

Proves: TECH-077 FR-1, TECH-077 NFR-3

A real database, settings files, rule file, stored standards and `context.yaml`; only the model is
doubled, and no call is made.

| Bucket | Case |
|---|---|
| Happy | a run with a model step gets the rule file, standards, sections, settings, router and topology |
| Boundary | a run with no model step gets no router and no `config` |
| Degradation | `optional` models with no role set give no router instead of a refusal; an unknown project gives no settings but still builds |
| Hostile | a broken `[sandbox]` raises `SettingsFileError` from the builder; it never exits |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
from specweaver.interfaces.run_setup.builder import RunRequest, build_run_sync
from specweaver.workspace.store import WorkspaceRepository
from tests.fixtures.db_utils import _sync_or_async, register_test_project
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_MACHINE = """schema_version = 1

[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "local-model@local", max_output_tokens = 4096 }
"""

_PROJECT_SETTINGS = """[autonomy]
mode = "agentic"

[implement]
language = "python"

[[docs.rule]]
paths = ["docs/**"]
access = "open"
"""


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Database, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    (data / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "proj"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "orders_spec.md").write_text("# Orders\n", encoding="utf-8")
    (root / "CONSTITUTION.md").write_text("# Rules\nKeep it small.\n", encoding="utf-8")
    (root / "specweaver.toml").write_text(_PROJECT_SETTINGS, encoding="utf-8")
    (root / "context.yaml").write_text("name: orders\narchetype: pure-logic\n", encoding="utf-8")
    (root / "billing").mkdir()
    (root / "billing" / "context.yaml").write_text(
        "name: billing\narchetype: pure-logic\nconsumes:\n  - orders\n", encoding="utf-8"
    )
    register_test_project(db, "proj", str(root))

    async def _standard() -> None:
        async with db.async_session_scope() as session:
            await WorkspaceRepository(session).save_standard(
                "proj", ".", "python", "naming", {"style": "snake_case"}, 0.9
            )

    _sync_or_async(_standard())
    return db, root


def _request(db: Database, root: Path, action: StepAction, **kw: object) -> RunRequest:
    pipeline = PipelineDefinition.create_single_step("one", action, StepTarget.SPEC)
    return RunRequest(
        project_root=root,
        spec_path=root / "specs" / "orders_spec.md",
        pipeline=pipeline,
        project="proj",
        db=db,
        **kw,
    )


def test_a_model_run_gets_every_part(world: tuple[Database, Path]) -> None:
    db, root = world

    with doubled_llm(MagicMock()):
        context = build_run_sync(_request(db, root, StepAction.REVIEW))

    assert "Keep it small." in (context.guidance.constitution or "")
    assert "snake_case" in (context.guidance.standards or "")
    assert context.isolation.autonomy.mode == "agentic"
    assert context.isolation.language == "python"
    assert [rule.access for rule in context.isolation.doc_policy.rule] == ["open"]
    assert context.model.config is not None
    assert context.model.llm_router is not None
    assert context.graph.topology is not None


def test_a_run_without_a_model_step_gets_no_router(world: tuple[Database, Path]) -> None:
    db, root = world

    context = build_run_sync(_request(db, root, StepAction.VALIDATE))

    assert context.model.llm_router is None
    assert context.model.config is None
    assert "Keep it small." in (context.guidance.constitution or "")


def test_optional_models_with_no_role_give_no_router(
    world: tuple[Database, Path], tmp_path: Path
) -> None:
    db, root = world
    (tmp_path / "data" / "settings.toml").write_text(_MACHINE.split("[roles]")[0], encoding="utf-8")

    context = build_run_sync(_request(db, root, StepAction.REVIEW, models="optional"))

    assert context.model.llm_router is None


def test_a_broken_setting_raises_from_the_builder(world: tuple[Database, Path]) -> None:
    db, root = world
    (root / "specweaver.toml").write_text('[sandbox]\nexecution_mod = "container"\n')

    with pytest.raises(SettingsFileError, match=r"sandbox\.execution_mod"):
        build_run_sync(_request(db, root, StepAction.VALIDATE))


def test_an_unknown_project_gives_no_settings_but_still_builds(
    world: tuple[Database, Path],
) -> None:
    """TECH-076 decision 5: only a broken settings file stops; an unknown project leaves defaults."""
    db, root = world
    request = _request(db, root, StepAction.VALIDATE)
    ghost = RunRequest(**{**request.__dict__, "project": "ghost"})

    context = build_run_sync(ghost)

    assert context.model.config is None
    assert "Keep it small." in (context.guidance.constitution or "")
