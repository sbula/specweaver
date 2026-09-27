# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw config show` — what each LLM setting is, and where it came from (US-16 paths P4, P7).

Proves: C-FLOW-13 FR-3, FR-4, FR-5

| Bucket | Case |
|---|---|
| Happy | machine and project files → each role with its value and origin |
| Boundary | no settings files at all → the built-in brake values, marked as built-in |
| Degradation | a typo in the machine file → exit 1 naming the file and the line (P4) |
| Hostile | a project file that defines a server → exit 1, told to use the machine file (P7) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
draft = "qwen3-coder-next@gb10"
"""


def _project(tmp_path: Path, llm_section: str = "") -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    if llm_section:
        (project / "specweaver.toml").write_text(llm_section, encoding="utf-8")
    result = runner.invoke(app, ["init", "show-demo", "--path", str(project)])
    assert result.exit_code == 0, result.output
    return project


def test_each_value_shows_where_it_came_from(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path, '[llm.roles]\nimplement = "qwen3-coder-next@gb10"\n')

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "roles.draft = qwen3-coder-next@gb10")
    draft_line = _MACHINE.splitlines().index('draft = "qwen3-coder-next@gb10"') + 1
    assert shows(result.output, f"{_isolate_env / 'settings.toml'}:{draft_line}")
    assert shows(result.output, "roles.implement = qwen3-coder-next@gb10")
    assert shows(result.output, "specweaver.toml:2")


def test_without_files_the_brake_values_are_built_in(tmp_path: Path, _mock_db: Database) -> None:
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "brake.hosted_chf_per_run = 20")
    assert shows(result.output, "built-in default")


def test_a_typo_in_the_machine_file_stops_with_its_line(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(
        _MACHINE.replace("max_parallel = 4", "max_paralel = 4"), encoding="utf-8"
    )
    _project(tmp_path)

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    typo_line = _MACHINE.splitlines().index("max_parallel = 4") + 1
    assert shows(result.output, f"{_isolate_env / 'settings.toml'}:{typo_line}")
    assert shows(result.output, "max_paralel")


def test_a_project_cannot_define_a_server(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path, '[llm.servers.evil]\nkind = "openai-compatible"\nbase_url = "http://evil"\n')

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    assert shows(result.output, "machine settings file")


def test_a_project_without_a_root_path_still_shows_the_machine_settings(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path, monkeypatch
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)
    from specweaver.interfaces.cli import _core

    class _RegistryWithoutRoot:
        def get_active_project(self) -> str:
            return "show-demo"

        def get_project(self, name: str) -> dict:
            return {"name": name, "root_path": None}

    monkeypatch.setattr(_core, "run_repo_op", lambda fn: fn(_RegistryWithoutRoot()))

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "roles.draft = qwen3-coder-next@gb10")
