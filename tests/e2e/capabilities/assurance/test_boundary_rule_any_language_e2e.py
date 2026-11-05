# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check` on a Go file that widens past its parent without `widens` fails and names the fix.

Proves: TECH-082 FR-16, FR-19

The journey (P-9): `sw init` → the user's own `context.yaml` files → `sw check <file>` → C05 → the
shared boundary check → the Go parser and resolver → the effective rule of the folder → the
printed finding and the exit code. Go has no language runner, so before TECH-082 its C05 was
tach's verdict on a Python layout and never looked at the Go file at all.

| Bucket | Case |
|---|---|
| Happy | the same file passes once its `context.yaml` declares the widening with a reason |
| Boundary | the parent's `forbids` binds a child that consumes the forbidden folder |
| Degradation | the exit code is 1, so a script sees the failure |
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

ONLY_C05 = """name: only_c05
type: validation_pipeline
target: code
steps:
  - name: c05_import_direction
    rule: C05
"""
CLI = "name: domain-cli\narchetype: adapter\nconsumes: [src/infra]\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    project = tmp_path / "greet"
    project.mkdir()
    runner.invoke(app, ["init", project.name, "--path", str(project)])
    files = {
        "go.mod": "module example.com/greet\n",
        "src/infra/db.go": "package infra\n\nfunc Open() {}\n",
        "src/domain/context.yaml": "name: domain\narchetype: pure-logic\nforbids: [src/infra]\n",
        "src/domain/cli/context.yaml": CLI,
        "src/domain/cli/main.go": (
            'package cli\n\nimport "example.com/greet/src/infra"\n\nfunc Run() { infra.Open() }\n'
        ),
        ".specweaver/pipelines/only_c05.yaml": ONLY_C05,
    }
    for relative, text in files.items():
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return project


def _check(project: Path) -> tuple[str, int]:
    result = runner.invoke(
        app,
        [
            "check",
            str(project / "src/domain/cli/main.go"),
            "--level",
            "code",
            "--project",
            str(project),
            "--pipeline",
            "only_c05",
        ],
    )
    return " ".join(_ANSI.sub("", result.output).split()), result.exit_code


def test_an_undeclared_widening_fails_and_names_the_fix(project: Path) -> None:
    output, code = _check(project)

    assert "src/domain/cli/main.go" in output, output
    assert "widens" in output, output
    assert code == 1


def test_the_declared_widening_passes(project: Path) -> None:
    (project / "src/domain/cli/context.yaml").write_text(
        CLI + "widens:\n  src/infra: opens the database\n", encoding="utf-8"
    )

    output, code = _check(project)

    assert "ALL PASSED" in output, output
    assert code == 0


def test_a_fresh_projects_tests_may_import_its_code(project: Path) -> None:
    """`sw init` writes the manifests; a test importing the code under test breaks no rule."""
    (project / "src/app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (project / "tests/test_app.py").write_text("from src.app import f\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "check",
            str(project / "tests/test_app.py"),
            "--level",
            "code",
            "--project",
            str(project),
            "--pipeline",
            "only_c05",
        ],
    )

    assert "ALL PASSED" in _ANSI.sub("", result.output), result.output
    assert result.exit_code == 0
