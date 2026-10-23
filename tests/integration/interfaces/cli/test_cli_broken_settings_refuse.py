# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every command that loads project settings stops on a broken one, naming the file and line.

Proves: TECH-076 FR-5, TECH-076 FR-3

The real CLI over a real `sw init` project; only the model is doubled, and no command gets far
enough to call it.

| Bucket | Case |
|---|---|
| Happy | not applicable — each command's working path is proven by its own tests |
| Boundary | a broken DAL file stops a command the same way a broken `[sandbox]` does |
| Degradation | not applicable — other lookup failures are not this requirement's |
| Hostile | `sw implement`, `sw draft`, `sw review`, `sw standards scan`, `sw drift check --analyze` on a misspelt `[sandbox]` key: exit 1, `<file>:<line>: <key>` printed, no traceback |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database

    data = tmp_path / ".specweaver-test"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    assert runner.invoke(app, ["init", "broken", "--path", str(root)]).exit_code == 0
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "greeter.py").write_text("def greet():\n    return 'hi'\n")
    (root / "plan.yaml").write_text("tasks: []\n")
    (root / "specweaver.toml").write_text('[sandbox]\n\nexecution_mod = "container"\n')
    monkeypatch.chdir(root)
    return root


def _invoke(args: list[str]) -> object:
    model = MagicMock()
    model.available.return_value = True
    model.generate = AsyncMock()
    with doubled_llm(model):
        return runner.invoke(app, args)


_COMMANDS = {
    "implement": ["implement", "specs/greeter_spec.md", "--project", "{root}"],
    "draft": ["draft", "orders", "--project", "{root}"],
    "review": ["review", "specs/greeter_spec.md", "--project", "{root}"],
    "standards scan": ["standards", "scan", "--no-review"],
    "drift check": [
        "drift",
        "check",
        "src/greeter.py",
        "--plan",
        "plan.yaml",
        "--analyze",
        "--project",
        "{root}",
    ],
}


@pytest.mark.parametrize("command", sorted(_COMMANDS))
def test_a_broken_sandbox_stops_the_command(project: Path, command: str) -> None:
    result = _invoke([part.format(root=project) for part in _COMMANDS[command]])

    assert result.exit_code == 1, result.output
    assert shows(result.output, "specweaver.toml:3: sandbox.execution_mod")
    assert "Traceback" not in result.output
    assert "SettingsFileError" not in result.output


def test_a_broken_dal_file_stops_a_command_alike(project: Path) -> None:
    (project / "specweaver.toml").write_text("")
    (project / ".specweaver" / "dal_definitions.yaml").write_text("matrx:\n  DAL_E: {}\n")

    result = _invoke(["review", "specs/greeter_spec.md", "--project", str(project)])

    assert result.exit_code == 1, result.output
    assert shows(result.output, "dal_definitions.yaml:1: matrx")
    assert "SettingsFileError" not in result.output
