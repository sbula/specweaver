# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check` on a file no rule can judge says so and fails, instead of `ALL PASSED`.

Proves: TECH-082 FR-13

The journey (P-1): `sw check <file>` → the real pipeline → rules → the printed summary and the exit
code. C01 judges Python only, so on a Kotlin file it is a SKIP (`TECH-093`); a project pipeline that
holds only C01 is a run where no rule judged.

| Bucket | Case |
|---|---|
| Happy | a Python file under the same pipeline passes, and its line names no skip |
| Boundary | the Kotlin file prints `NOTHING CHECKED: 1 skipped` |
| Degradation | it exits 1, so a script reading the exit code sees nothing was checked |
| Hostile | — (the input is a real file in a real project) |
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

ONLY_C01 = """name: only_c01
type: validation_pipeline
target: code
steps:
  - name: c01_syntax_valid
    rule: C01
"""


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "greet"
    project.mkdir()
    runner.invoke(app, ["init", project.name, "--path", str(project)])
    src = project / "src"
    src.mkdir(exist_ok=True)
    (src / "Greet.kt").write_text('fun greet(name: String) = "Hello, $name"\n', encoding="utf-8")
    (src / "greet.py").write_text("def greet(name):\n    return name\n", encoding="utf-8")
    pipelines = project / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True, exist_ok=True)
    (pipelines / "only_c01.yaml").write_text(ONLY_C01, encoding="utf-8")
    return project


def _check(project: Path, name: str) -> tuple[str, int]:
    result = runner.invoke(
        app,
        [
            "check",
            str(project / "src" / name),
            "--level",
            "code",
            "--project",
            str(project),
            "--pipeline",
            "only_c01",
        ],
    )
    return _ANSI.sub("", result.output), result.exit_code


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _project(tmp_path_factory.mktemp("nothing_checked"))


def test_a_file_no_rule_judges_is_nothing_checked(project: Path) -> None:
    output, code = _check(project, "Greet.kt")

    assert "NOTHING CHECKED: 1 skipped" in output, output
    assert "ALL PASSED" not in output, output
    assert code == 1


def test_a_file_the_rule_judges_still_passes(project: Path) -> None:
    """The control: the same pipeline on Python is judged and passes."""
    output, code = _check(project, "greet.py")

    assert "ALL PASSED" in output, output
    assert "skipped" not in output.split("ALL PASSED", 1)[1].splitlines()[0], output
    assert code == 0
