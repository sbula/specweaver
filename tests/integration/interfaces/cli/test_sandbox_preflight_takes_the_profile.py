# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw sandbox preflight` reports the plan for the project's one build tool, or refuses to guess.

Proves: TECH-079 FR-7
Proves: TECH-079 FR-8

The real CLI over real folders; nothing is built.

| Bucket | Case |
|---|---|
| Happy | a root with pyproject.toml and Cargo.toml pinned to Rust reports the cargo plan |
| Boundary | `[implement] build_tool` reaches the report: pom.xml with build.gradle pinned to Maven |
| Degradation | a broken `[implement]` stops the command naming its line |
| Hostile | a mixed root without a setting is refused, naming the setting; no plan is shown |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration
runner = CliRunner()


def _root(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def _preflight(root: Path):
    return runner.invoke(app, ["sandbox", "preflight", str(root)])


def test_a_rust_pin_reports_the_cargo_plan(tmp_path: Path) -> None:
    root = _root(
        tmp_path,
        {
            "pyproject.toml": "[project]\nname = 'x'\n",
            "Cargo.toml": '[package]\nname = "p"\n',
            "Cargo.lock": "",
            "specweaver.toml": '[implement]\nlanguage = "rust"\n',
        },
    )

    result = _preflight(root)

    assert shows(result.output, "Cargo.toml"), result.output
    assert shows(result.output, "fetched now"), result.output


def test_the_build_tool_setting_reaches_the_report(tmp_path: Path) -> None:
    root = _root(
        tmp_path,
        {
            "pom.xml": "<project/>",
            "build.gradle": "",
            "specweaver.toml": '[implement]\nbuild_tool = "maven"\n',
        },
    )

    result = _preflight(root)

    assert shows(result.output, "pom.xml"), result.output
    assert not shows(result.output, "Gradle projects cannot be prepared"), result.output


def test_a_broken_setting_stops_naming_its_line(tmp_path: Path) -> None:
    root = _root(
        tmp_path, {"pyproject.toml": "", "specweaver.toml": '[implement]\nlanguag = "x"\n'}
    )

    result = _preflight(root)

    assert result.exit_code == 1, result.output
    assert shows(result.output, "specweaver.toml:2: implement.languag")


def test_a_mixed_root_is_refused_without_a_plan(tmp_path: Path) -> None:
    root = _root(tmp_path, {"pyproject.toml": "", "Cargo.toml": '[package]\nname = "p"\n'})

    result = _preflight(root)

    assert result.exit_code == 1, result.output
    assert shows(result.output, "set [implement] language in specweaver.toml")
    assert not shows(result.output, "Environment")
