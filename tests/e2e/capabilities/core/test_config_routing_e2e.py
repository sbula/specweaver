# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests — routing a task to a model with `sw config set-role` (C-FLOW-13).

Replaces the `sw config routing set/show/clear` journey: routing now lives in the LLM settings
files, a role per task, written by `sw config set-role` and read back by `sw config show`.

Exercises:
    sw config set-role <role> <model@server>              (machine file)
    sw config set-role <role> <model@server> --project    (the project's specweaver.toml)
    sw config show
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
"""


def _project(tmp_path: Path, name: str) -> Path:
    project = tmp_path / name
    project.mkdir()
    result = runner.invoke(app, ["init", name, "--path", str(project)])
    assert result.exit_code == 0, result.output
    return project


class TestConfigRoutingE2E:
    """E2E tests for routing roles to models."""

    def test_full_routing_lifecycle(
        self, tmp_path: Path, _mock_db: Database, _isolate_env: Path
    ) -> None:
        """Set a machine role, a project role, overwrite one, and show where each came from."""
        machine = _isolate_env / "settings.toml"
        machine.write_text(_MACHINE, encoding="utf-8")
        project = _project(tmp_path, "route-lifecycle")

        # 1. SET on the machine
        result = runner.invoke(app, ["config", "set-role", "plan", "o1-mini@gb10"])
        assert result.exit_code == 0, result.output
        assert shows(result.output, "roles.plan = o1-mini@gb10")
        assert 'plan = "o1-mini@gb10"' in machine.read_text(encoding="utf-8")

        # 2. SET for the project only
        result2 = runner.invoke(
            app, ["config", "set-role", "implement", "claude-sonnet@gb10", "--project"]
        )
        assert result2.exit_code == 0, result2.output
        project_file = (project / "specweaver.toml").read_text(encoding="utf-8")
        assert 'implement = "claude-sonnet@gb10"' in project_file
        assert "implement" not in machine.read_text(encoding="utf-8")

        # 3. SHOW — both roles, each with the file it came from
        show_result = runner.invoke(app, ["config", "show"])
        assert show_result.exit_code == 0, show_result.output
        assert shows(show_result.output, "o1-mini@gb10")
        assert shows(show_result.output, "claude-sonnet@gb10")
        assert shows(show_result.output, str(machine))
        assert shows(show_result.output, "specweaver.toml")

        # 4. SET again replaces the role rather than adding a second one
        result3 = runner.invoke(app, ["config", "set-role", "plan", "qwen3@gb10"])
        assert result3.exit_code == 0, result3.output
        text = machine.read_text(encoding="utf-8")
        assert 'plan = "qwen3@gb10"' in text
        assert "o1-mini" not in text
        show_result2 = runner.invoke(app, ["config", "show"])
        assert shows(show_result2.output, "qwen3@gb10")
        assert "o1-mini" not in show_result2.output

    def test_role_on_an_undefined_server_is_refused(
        self, tmp_path: Path, _mock_db: Database, _isolate_env: Path
    ) -> None:
        """A role pointing at a server nobody defined is refused and the file stays untouched."""
        machine = _isolate_env / "settings.toml"
        machine.write_text(_MACHINE, encoding="utf-8")
        _project(tmp_path, "route-orphan")

        result = runner.invoke(app, ["config", "set-role", "review", "gemini-1.5-pro@nowhere"])
        assert result.exit_code != 0
        assert shows(result.output, "nowhere")
        assert machine.read_text(encoding="utf-8") == _MACHINE

    def test_invalid_terminal_inputs(
        self, tmp_path: Path, _mock_db: Database, _isolate_env: Path
    ) -> None:
        """Invalid commands exit with non-zero exit codes and write nothing."""
        machine = _isolate_env / "settings.toml"
        machine.write_text(_MACHINE, encoding="utf-8")
        _project(tmp_path, "route-invalid")

        # 1. Invalid role name
        res1 = runner.invoke(app, ["config", "set-role", "fly", "o1-mini@gb10"])
        assert res1.exit_code != 0, res1.output
        assert shows(res1.output, "roles.fly")

        # 2. Not model@server
        res2 = runner.invoke(app, ["config", "set-role", "draft", "o1-mini"])
        assert res2.exit_code != 0, res2.output
        assert shows(res2.output, "model@server")

        assert machine.read_text(encoding="utf-8") == _MACHINE
