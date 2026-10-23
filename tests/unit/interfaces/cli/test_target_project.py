# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A command works on the project it is pointed at, not on whichever project is active.

Proves: C-FLOW-13 FR-2, C-FLOW-13 FR-9

| Bucket | Case |
|---|---|
| Happy | the project registered at the target folder is the command's project |
| Boundary | a folder nobody registered falls back to the active project |
| Degradation | not applicable — a missing active project is refused by `_require_active_project` |
| Hostile | the router reads the target folder's settings even when given another project's name |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.core.config.settings_file import SettingsFileError
from specweaver.infrastructure.llm.interfaces.command import command_router
from specweaver.infrastructure.llm.models import TaskType
from specweaver.interfaces.cli import _core
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


def test_the_project_registered_at_the_folder_is_the_commands_project(projects) -> None:
    private, _other = projects

    assert _core.project_name_for(private) == "priv"


def test_an_unregistered_folder_falls_back_to_the_active_project(projects, tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir()

    assert _core.project_name_for(loose) == "other"


def test_the_router_reads_the_target_folders_settings_whatever_name_it_gets(projects) -> None:
    private, _other = projects

    with (
        patch.object(_core, "refuse_settings", side_effect=_reraise),
        pytest.raises(SettingsFileError, match="private servers only"),
    ):
        command_router("other", [TaskType.REVIEW], project_root=private)


def _reraise(err: Exception) -> None:
    raise err
