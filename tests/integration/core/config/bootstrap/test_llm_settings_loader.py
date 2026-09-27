# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The loader reads the real machine file and the real project file, and nothing else.

Proves: C-FLOW-13 FR-1, FR-2

| Bucket | Case |
|---|---|
| Happy | both files on disk are read and layered |
| Boundary | the machine file follows `SPECWEAVER_DATA_DIR` |
| Degradation | no machine file → built-in defaults; no `specweaver.toml` or no `[llm]` → empty choice |
| Hostile | a broken machine file refuses, naming the real path |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.llm_settings import SettingsFileError, resolve_roles

if TYPE_CHECKING:
    from pathlib import Path

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
implement = "qwen3-coder-next@gb10"
"""


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "data"
    home.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(home))
    return home


def test_both_files_are_read_and_layered(data_dir: Path, tmp_path: Path) -> None:
    (data_dir / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    (project / "specweaver.toml").write_text(
        "[standards]\nenabled = true\n\n[llm]\nprivate_only = true\n", encoding="utf-8"
    )

    files = load_llm_settings(project)

    assert files.project.private_only is True
    implement = resolve_roles(files)["implement"]
    line = _MACHINE.splitlines().index('implement = "qwen3-coder-next@gb10"') + 1
    assert implement.origin["model"] == f"{data_dir / 'settings.toml'}:{line}"


def test_no_files_mean_defaults_and_an_empty_choice(data_dir: Path, tmp_path: Path) -> None:
    files = load_llm_settings(tmp_path)

    assert files.machine.servers == {}
    assert files.machine.brake.agent_turns == 10
    assert files.project.roles == {}


def test_no_project_means_an_empty_choice(data_dir: Path) -> None:
    assert load_llm_settings(None).project.private_only is False


def test_a_broken_machine_file_refuses_naming_its_path(data_dir: Path) -> None:
    (data_dir / "settings.toml").write_text("[servers.gb10\n", encoding="utf-8")

    with pytest.raises(SettingsFileError) as caught:
        load_llm_settings(None)

    assert caught.value.source == str(data_dir / "settings.toml")
    assert caught.value.line == 1
