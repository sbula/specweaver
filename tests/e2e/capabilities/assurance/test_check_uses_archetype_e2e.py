# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check` applies the archetype of the folder a file sits in, as `sw run` does.

Proves: B-INTL-01 FR-1
Proves: B-INTL-01 FR-6
Proves: B-INTL-01 NFR-2

| Bucket | Case |
|---|---|
| Happy | a Java controller in a spring-boot folder passes C12 under `sw check --level code` |
| Boundary | `--pipeline` still wins over the archetype; a project's own archetype is found |
| Degradation | not applicable — a folder without an archetype is the default path |
| Hostile | a spec missing a required section fails S12 under `sw check`, naming it |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e
runner = CliRunner()

_JAVA = 'package demo;\n\n@RestController\npublic class Hello {\n    public String hi() { return "hi"; }\n}\n'


@pytest.fixture
def svc(tmp_path: Path) -> Path:
    assert runner.invoke(app, ["init", "arch-check", "--path", str(tmp_path)]).exit_code == 0
    folder = tmp_path / "svc"
    (folder / "src").mkdir(parents=True)
    (folder / "context.yaml").write_text("archetype: spring-boot\n", encoding="utf-8")
    (folder / "src" / "Hello.java").write_text(_JAVA, encoding="utf-8")
    (folder / "svc_spec.md").write_text("# Svc\n\n## 1. Purpose\n\nGreets.\n", encoding="utf-8")
    return tmp_path


def _check(project: Path, *args: str):
    return runner.invoke(app, ["check", *args, "--project", str(project)])


def test_a_java_controller_passes_the_archetype_rule(svc: Path) -> None:
    result = _check(svc, str(svc / "svc" / "src" / "Hello.java"), "--level", "code")

    assert result.exit_code == 0, result.output
    assert shows(result.output, "C12"), result.output
    assert not shows(result.output, "Syntax Valid"), result.output


def test_a_spec_missing_a_section_fails_s12(svc: Path) -> None:
    result = _check(svc, str(svc / "svc" / "svc_spec.md"))

    assert shows(result.output, "Missing required <h2> header: '2. Boundaries'"), result.output


def test_an_explicit_pipeline_wins(svc: Path) -> None:
    result = _check(svc, str(svc / "svc" / "svc_spec.md"), "--pipeline", "validation_spec_default")

    assert not shows(result.output, "2. Boundaries"), result.output


def test_a_projects_own_archetype_is_used(svc: Path) -> None:
    """An archetype SpecWeaver does not ship lives in the project's `.specweaver/pipelines/`."""
    (svc / "svc" / "context.yaml").write_text("archetype: in-house\n", encoding="utf-8")
    (svc / ".specweaver" / "pipelines").mkdir(parents=True, exist_ok=True)
    (svc / ".specweaver" / "pipelines" / "validation_code_in-house.yaml").write_text(
        "name: validation_code_in-house\nlanguages: [java]\nsteps:\n"
        "  - name: c12\n    rule: C12\n    params:\n      required_markers: ['@Service']\n",
        encoding="utf-8",
    )

    result = _check(svc, str(svc / "svc" / "src" / "Hello.java"), "--level", "code")

    assert result.exit_code == 1, result.output
    assert shows(result.output, "'@Service'"), result.output


def test_an_archetype_without_its_own_pipeline_prints_no_error(tmp_path: Path) -> None:
    """`sw init` declares `orchestrator`, which ships no pipeline: the default applies, silently."""
    assert runner.invoke(app, ["init", "plain", "--path", str(tmp_path)]).exit_code == 0
    spec = tmp_path / "specs" / "a_spec.md"
    spec.write_text("# A\n\n## 1. Purpose\n\nGreets.\n", encoding="utf-8")

    result = runner.invoke(app, ["check", str(spec), "--project", str(tmp_path)])

    assert "not found" not in result.output and "ERROR" not in result.output, result.output
