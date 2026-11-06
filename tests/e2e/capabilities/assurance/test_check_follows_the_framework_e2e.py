# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw check` judges a code file by its framework, the answer generation uses.

Proves: TECH-079 FR-9
Proves: TECH-079 FR-10

Real `sw init` project, real build file, real `context.yaml`, the shipped Spring Boot pipeline.

| Bucket | Case |
|---|---|
| Happy | a Spring Boot root with no archetype: a plain class fails C12 |
| Boundary | `framework: spring-boot` in the folder names it with no Spring build file; a role archetype keeps the default checks |
| Degradation | a root that decides no language still checks the file, by its folder's `framework:` |
| Hostile | a Python file in a Spring Boot root gets no Spring Boot rule |
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

_PLAIN = 'package demo;\n\npublic class Hello {\n    public String hi() { return "hi"; }\n}\n'
_BOOT_POM = "<project><parent><groupId>org.springframework.boot</groupId></parent></project>"


def _project(tmp_path: Path, build: dict[str, str], manifest: str | None = None) -> Path:
    assert runner.invoke(app, ["init", "fw-check", "--path", str(tmp_path)]).exit_code == 0
    for name, text in build.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    folder = tmp_path / "svc"
    (folder / "src").mkdir(parents=True)
    if manifest is not None:
        (folder / "context.yaml").write_text(manifest, encoding="utf-8")
    (folder / "src" / "Hello.java").write_text(_PLAIN, encoding="utf-8")
    return folder / "src" / "Hello.java"


def _check(project: Path, target: Path):
    return runner.invoke(app, ["check", str(target), "--level", "code", "--project", str(project)])


def test_a_spring_boot_root_gets_spring_boot_checks(tmp_path: Path) -> None:
    result = _check(tmp_path, _project(tmp_path, {"pom.xml": _BOOT_POM}))

    assert result.exit_code == 1, result.output
    assert shows(result.output, "C12"), result.output


def test_the_framework_key_names_the_framework(tmp_path: Path) -> None:
    code = _project(tmp_path, {"pom.xml": "<project/>"}, "framework: spring-boot\n")

    assert shows(_check(tmp_path, code).output, "C12")


def test_a_role_archetype_keeps_the_default_checks(tmp_path: Path) -> None:
    code = _project(tmp_path, {"pom.xml": "<project/>"}, "archetype: adapter\n")

    assert not shows(_check(tmp_path, code).output, "C12")


def test_an_undecided_root_still_checks_by_the_folder(tmp_path: Path) -> None:
    mixed = {"pyproject.toml": "[project]\nname = 'x'\n", "pom.xml": _BOOT_POM}
    code = _project(tmp_path, mixed, "framework: spring-boot\n")

    result = _check(tmp_path, code)

    assert shows(result.output, "C12"), result.output
    assert not shows(result.output, "specweaver.toml"), result.output


def test_a_python_file_in_a_spring_boot_root_gets_no_spring_rule(tmp_path: Path) -> None:
    _project(tmp_path, {"pom.xml": _BOOT_POM})
    tool = tmp_path / "svc" / "src" / "tool.py"
    tool.write_text("def tool():\n    return 1\n", encoding="utf-8")

    assert not shows(_check(tmp_path, tool).output, "C12")


def test_a_pinned_mixed_root_takes_the_pinned_language_framework(tmp_path: Path) -> None:
    mixed = {"pyproject.toml": "[project]\nname = 'x'\n", "pom.xml": _BOOT_POM}
    code = _project(tmp_path, mixed)
    with (tmp_path / "specweaver.toml").open("a", encoding="utf-8") as settings:
        settings.write('\n[implement]\nlanguage = "java"\n')

    assert shows(_check(tmp_path, code).output, "C12")


def test_a_bad_language_pin_still_checks_by_the_folder(tmp_path: Path) -> None:
    code = _project(tmp_path, {"pom.xml": _BOOT_POM}, "framework: spring-boot\n")
    with (tmp_path / "specweaver.toml").open("a", encoding="utf-8") as settings:
        settings.write('\n[implement]\nlanguage = "cobol"\n')

    assert shows(_check(tmp_path, code).output, "C12")
