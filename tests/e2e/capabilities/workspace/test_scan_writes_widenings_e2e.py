# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A declared widening reaches `tach.toml`, so tach agrees with the boundary rule.

Proves: TECH-082 FR-20

`src` forbids `src.infra`; `src.api` consumes it and declares the widening with a reason. The
shared rule allows that import. tach, run as an extra, only knows what `sw scan` wrote, so without
the edge it would fail an import the rule allows.

| Bucket | Case |
|---|---|
| Happy | after `sw scan`, `src.api` depends on `src.infra` in `tach.toml`, and `tach check` passes |
| Boundary | the module that only forbids gets no edge to what it forbids |
| Degradation | — (real `sw init`, `sw scan` and tach; nothing is doubled) |
| Hostile | — (fixed project files) |
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

CLI = [sys.executable, "-c", "from specweaver.interfaces.cli.main import app; app(prog_name='sw')"]

FILES = {
    "CONSTITUTION.md": "# Project Constitution\n",
    "src/util.py": "def helper(): pass\n",
    "src/infra/__init__.py": "",
    "src/infra/db.py": "def connect(): pass\n",
    "src/api/__init__.py": "",
    "src/api/main.py": "import src.infra\n",
    "tests/test_util.py": "import src.util\n",
}
MANIFESTS = {
    "src/context.yaml": "name: src\nlevel: module\narchetype: pure-logic\nforbids: [src.infra]\n",
    "src/infra/context.yaml": "name: src.infra\nlevel: module\narchetype: adapter\n",
    "src/api/context.yaml": (
        "name: src.api\nlevel: module\narchetype: orchestrator\nconsumes: [src.infra]\n"
        "widens:\n  src.infra: runs the database\n"
    ),
}


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")


def _sw(args: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*CLI, *args], env=env, cwd=cwd, check=True, capture_output=True, text=True
    )


def test_scan_writes_the_widened_edge_and_tach_passes(tmp_path: Path) -> None:
    project = tmp_path / "widening-project"
    project.mkdir()
    _write(project, FILES)
    env = {
        **os.environ,
        "SPECWEAVER_DATA_DIR": str(tmp_path / "appdata"),
        "PYTHONIOENCODING": "utf-8",
    }
    _sw(["init", "widening-project", "--path", str(project)], env, tmp_path)
    _write(project, MANIFESTS)

    _sw(["scan"], env, project)

    modules = {
        m["path"]: m["depends_on"]
        for m in tomllib.loads((project / "tach.toml").read_text())["modules"]
    }
    assert "src.infra" in modules["src.api"], modules
    assert "src.infra" not in modules["src"], modules
    tach = subprocess.run(
        [sys.executable, "-m", "tach", "check"], cwd=project, capture_output=True, text=True
    )
    assert tach.returncode == 0, tach.stdout + tach.stderr
