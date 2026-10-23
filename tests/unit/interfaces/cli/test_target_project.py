# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A command works on the project it is pointed at, not on whichever project is active.

Proves: C-FLOW-13 FR-2, C-FLOW-13 FR-9

| Bucket | Case |
|---|---|
| Happy | the project registered at the target folder is the command's project, not the active one |
| Boundary | a folder nobody registered is refused, never run as the active project (`TECH-077` FR-4) |
| Degradation | not applicable — a broken settings file is `test_run_doors.py`'s |
| Hostile | the router reads the target folder's settings while another project is active |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import typer

from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
from specweaver.core.flow.engine.naming import registered_name
from specweaver.interfaces.cli import _core, run_doors
from tests.fixtures.db_utils import register_test_project, set_test_active_project

if TYPE_CHECKING:
    from pathlib import Path

_MACHINE = """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[roles]
default = "m@hosted"

[models."m"]
max_output = 100
usd_per_million_input = 1
usd_per_million_output = 1
thinking_in_output_cap = true

[brake]
hosted_spend_per_run = 100
tokens_per_run = 1000000
agent_turns = 5
"""


@pytest.fixture
def projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    private, other = tmp_path / "priv", tmp_path / "other"
    private.mkdir()
    other.mkdir()
    (private / "specweaver.toml").write_text("[llm]\nprivate_only = true\n", encoding="utf-8")
    db = _core.get_db()
    register_test_project(db, "priv", str(private))
    register_test_project(db, "other", str(other))
    set_test_active_project(db, "other")
    return private, other


def _build(root: Path, action: StepAction = StepAction.VALIDATE) -> object:
    pipeline = PipelineDefinition.create_single_step("one", action, StepTarget.SPEC)
    return run_doors.build_run_or_exit(root, root / "a_spec.md", pipeline)


def test_the_project_registered_at_the_folder_is_the_commands_project(projects) -> None:
    private, _other = projects

    assert registered_name(_build(private)) == "priv"


def test_an_unregistered_folder_is_refused(projects, tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir()

    with pytest.raises(typer.Exit):
        _build(loose)


def test_the_router_reads_the_target_folders_settings(projects) -> None:
    private, _other = projects

    with (
        patch.object(_core, "refuse_settings", side_effect=_reraise),
        pytest.raises(SettingsFileError, match="private servers only"),
    ):
        _build(private, StepAction.REVIEW)


def _reraise(err: Exception) -> None:
    raise err
