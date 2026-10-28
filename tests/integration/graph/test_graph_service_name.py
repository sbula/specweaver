# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A graph build stores its nodes under the project's service name.

Proves: TECH-004 FR-6
Proves: TECH-081 FR-17

`sw graph build` with the real topology loader, the real builder and the real SQLite store: the
command reads the name and hands it to the builder (`TECH-081` FR-17).

| Bucket | Case |
|---|---|
| Happy | a project whose root `context.yaml` is named `billing` stores `billing` |
| Boundary | a build of one sub-folder still uses the project's name |
| Degradation | a project with no root `context.yaml` stores `default` |
| Hostile | a sub-module's name is not taken for the project |
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path


def _project(root: Path, root_name: str | None) -> Path:
    (root / "src" / "a").mkdir(parents=True)
    (root / ".specweaver").mkdir()  # as `sw init` leaves it
    (root / "src" / "a" / "util.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (root / "src" / "a" / "context.yaml").write_text(
        "name: a\nlevel: module\npurpose: Sub.\narchetype: pure-logic\n", encoding="utf-8"
    )
    if root_name:
        (root / "context.yaml").write_text(
            f"name: {root_name}\nlevel: system\npurpose: Root.\narchetype: orchestrator\n",
            encoding="utf-8",
        )
    return root


def _services(root: Path) -> set[str]:
    with sqlite3.connect(root / ".specweaver" / "graph.db") as conn:
        return {row[0] for row in conn.execute("SELECT DISTINCT service_name FROM graph_nodes")}


@pytest.mark.parametrize(("root_name", "expected"), [("billing", {"billing"}), (None, {"default"})])
def test_the_build_stores_the_project_service_name(
    tmp_path: Path, root_name: str | None, expected: set[str]
) -> None:
    root = _project(tmp_path / "p", root_name)

    result = CliRunner().invoke(
        app, ["graph", "build", str(root / "src" / "a"), "--project-path", str(root)]
    )

    assert result.exit_code == 0, result.output
    assert _services(root) == expected
