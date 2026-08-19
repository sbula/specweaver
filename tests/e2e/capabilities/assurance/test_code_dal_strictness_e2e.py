# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A module's declared DAL changes the verdict on its code. The same code, twice.

Proves: TECH-041 FR-1

`C-VAL-03` claims a module's DAL injects stricter constraints into validation. At spec level that was
proven twice. At code level every link was tested and the chain was not: the resolver resolves, the
runner injects, the hydrator forwards — and no test drove code through the flow and showed the
verdict move. The test that appeared to prove it asserted `exit_code in (0, 1)` against a command
that had exited 1 on `Spec not found`, so the pipeline was never entered.

**The lenient run is the load-bearing half.** A regression that failed every file under every
`context.yaml` would satisfy a strict-only assertion perfectly. Both runs use one source file, one
pipeline and one project layout; the only difference between them is the `dal_level` line, and the
warning count is asserted equal so the change is strictness rather than content.

`c05_import_direction` is removed from the pipeline the runs share. It fails on a project this small
for reasons that have nothing to do with the DAL, and a rule that FAILs forces exit 1 whatever the
strictness — which would hide the very difference this test exists to show.
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

#: The pipeline both runs share, minus the boundary rule. `extends` keeps every other code rule.
LEAN_PIPELINE = """name: validation_code_lean
type: validation_pipeline
extends: validation_code_default
target: code
remove:
  - c05_import_direction
"""

CONTEXT = """module: widget
purpose: Adds two numbers.
archetype: pure-logic
operational:
  dal_level: {dal}
"""

SOURCE = '''"""A widget."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _project(tmp_path: Path, dal: str) -> Path:
    """A minimal real project whose only variable is the declared DAL."""
    project = tmp_path / f"proj_{dal.lower()}"
    project.mkdir()
    runner.invoke(app, ["init", project.name, "--path", str(project)])

    src = project / "src"
    src.mkdir(exist_ok=True)
    (src / "context.yaml").write_text(CONTEXT.format(dal=dal), encoding="utf-8")
    (src / "widget.py").write_text(SOURCE, encoding="utf-8")

    tests_dir = project / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_widget.py").write_text(
        "def test_add():\n    assert True\n", encoding="utf-8"
    )

    pipelines = project / ".specweaver" / "pipelines"
    pipelines.mkdir(parents=True, exist_ok=True)
    (pipelines / "validation_code_lean.yaml").write_text(LEAN_PIPELINE, encoding="utf-8")
    return project


def _check(project: Path):
    return runner.invoke(
        app,
        [
            "check",
            str(project / "src" / "widget.py"),
            "--level",
            "code",
            "--project",
            str(project),
            "--pipeline",
            "validation_code_lean",
        ],
    )


def _warnings(output: str) -> int:
    match = re.search(r"(\d+) warning\(s\)", _ANSI.sub("", output))
    return int(match.group(1)) if match else -1


@pytest.fixture(scope="module")
def lenient(tmp_path_factory: pytest.TempPathFactory):
    return _check(_project(tmp_path_factory.mktemp("lenient"), "DAL_E"))


@pytest.fixture(scope="module")
def strict(tmp_path_factory: pytest.TempPathFactory):
    return _check(_project(tmp_path_factory.mktemp("strict"), "DAL_A"))


def test_a_lenient_dal_lets_the_warnings_pass(lenient) -> None:
    """The control. Without it, a build that failed everything would read as correct."""
    assert lenient.exit_code == 0, _ANSI.sub("", lenient.output)
    assert "PASSED with warnings" in _ANSI.sub("", lenient.output)


def test_a_strict_dal_fails_the_same_code(strict) -> None:
    assert strict.exit_code == 1, _ANSI.sub("", strict.output)


def test_the_two_runs_differ_only_in_strictness(lenient, strict) -> None:
    """Same warnings, opposite verdicts — which is what "the DAL is enforced" has to mean.

    Asserting the counts match is what separates this from a test that merely found two projects
    behaving differently: if the strict run had produced an extra finding, the exit code would move
    for a reason that is not the DAL at all.
    """
    assert _warnings(strict.output) == _warnings(lenient.output) > 0
    assert "PASSED with warnings" in _ANSI.sub("", strict.output)


def test_each_run_reports_the_dal_it_resolved(lenient, strict) -> None:
    """A verdict a reader cannot attribute is a verdict they cannot act on."""
    assert "DAL: DAL_E" in _ANSI.sub("", lenient.output)
    assert "DAL: DAL_A" in _ANSI.sub("", strict.output)
