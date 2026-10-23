# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw resume` continues a run in the project the run recorded, from whatever folder it is typed.

Proves: TECH-077 FR-5

Real `sw` processes over two registered projects; no model. The run's pipeline is a YAML file and
its steps are scripts inside project B, so a resume set up for any other folder cannot find them.

| Bucket | Case |
|---|---|
| Happy | a run of project B, resumed from project A's folder while A is active, finishes in B |
| Boundary | not applicable — the run's own folder is the case the older resume e2e covers |
| Degradation | not applicable — a run with no worktree is covered by the CLI door tests |
| Hostile | the run's project unregistered → the resume stops naming it, no traceback |
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

PIPELINE = textwrap.dedent("""\
    name: away_journey
    version: "1.0"
    steps:
      - name: gate
        action: bash
        target: script
        params:
          script: gate.sh
        gate:
          type: auto
          condition: all_passed
          on_fail: abort
    """)


def _sw(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "specweaver.interfaces.cli.main", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env={**os.environ, "COLUMNS": "200"},
        check=False,
        timeout=300,
    )


@pytest.fixture
def two_projects(tmp_path: Path) -> tuple[Path, Path, str]:
    """Project B holds a failed run; project A is active and is where `sw resume` is typed."""
    b = tmp_path / "bee"
    a = tmp_path / "ay"
    for root, name in ((b, "bee"), (a, "ay")):
        root.mkdir()
        init = _sw("init", name, "--path", str(root), cwd=tmp_path)
        assert init.returncode == 0, init.stdout + init.stderr
    scripts = b / ".specweaver" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    gate = scripts / "gate.sh"
    gate.write_text(
        f'#!/usr/bin/env bash\ntest -f "{b}/unblock" || exit 3\necho ok >> "{b}/gates.txt"\n',
        encoding="utf-8",
    )
    gate.chmod(0o755)
    (b / "away_journey.yaml").write_text(PIPELINE, encoding="utf-8")
    (b / "specs" / "subject.md").write_text("# Subject\n", encoding="utf-8")

    first = _sw("run", "away_journey.yaml", "specs/subject.md", cwd=b)
    assert first.returncode != 0, first.stdout
    assert _sw("use", "ay", cwd=a).returncode == 0
    return a, b, _run_id("bee")


def _run_id(project: str) -> str:
    from specweaver.core.config.paths import state_db_path
    from specweaver.core.flow.engine.store import StateStore

    run = StateStore(state_db_path()).get_latest_resumable_run(project)
    assert run is not None
    return run.run_id


def test_a_run_resumes_in_its_own_project(two_projects: tuple[Path, Path, str]) -> None:
    a, b, run_id = two_projects
    (b / "unblock").touch()

    resumed = _sw("resume", run_id, cwd=a)

    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert (b / "gates.txt").exists(), resumed.stdout
    assert not (a / "gates.txt").exists()


def test_an_unregistered_project_stops_the_resume(two_projects: tuple[Path, Path, str]) -> None:
    a, _b, run_id = two_projects
    assert _sw("remove", "bee", "--force", cwd=a).returncode == 0

    resumed = _sw("resume", run_id, cwd=a)

    assert resumed.returncode == 1, resumed.stdout + resumed.stderr
    assert "bee" in resumed.stdout
    assert "Traceback" not in resumed.stdout + resumed.stderr
