# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run` on a high-DAL project runs inside a per-run worktree, and stops cleanly without git.

Proves: TECH-077 FR-3

Real `sw` processes, a real git repository and real `git worktree`; no model (`validate_only`).

| Bucket | Case |
|---|---|
| Happy | a DAL_B project's run goes through `.worktrees/session-<id>`, and no worktree is left after |
| Boundary | not applicable — the DAL threshold itself is `test_build_run.py`'s |
| Degradation | the same project without git stops at the worktree, exit 1, no traceback |
| Hostile | not applicable — no input reaches the isolation decision |
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        check=False,
        timeout=300,
        env={**os.environ, "COLUMNS": "400"},
    )


def _sw(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return _run(sys.executable, "-m", "specweaver.interfaces.cli.main", *args, cwd=cwd)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "dalb"
    root.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@e.x"], ["config", "user.name", "t"]):
        assert _run("git", *args, cwd=root).returncode == 0
    assert _sw("init", "dalb", "--path", str(root), cwd=tmp_path).returncode == 0
    (root / "context.yaml").write_text(
        "name: dalb\narchetype: pure-logic\noperational:\n  dal_level: DAL_B\n", encoding="utf-8"
    )
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n\n## 1. Purpose\nGreets.\n")
    assert _run("git", "add", "-A", cwd=root).returncode == 0
    assert _run("git", "commit", "-qm", "init", cwd=root).returncode == 0
    return root


def test_a_high_dal_run_goes_through_a_worktree(project: Path) -> None:
    result = _sw("run", "validate_only", "specs/greeter_spec.md", "--verbose", cwd=project)

    assert "worktrees/session-" in "".join((result.stdout + result.stderr).split()), result.stderr
    assert _run("git", "worktree", "list", cwd=project).stdout.count("\n") == 1


def test_without_git_the_run_stops_at_the_worktree(project: Path) -> None:
    (project / ".git").rename(project / ".git-off")

    result = _sw("run", "validate_only", "specs/greeter_spec.md", cwd=project)

    assert result.returncode == 1, result.stdout
    assert "could not start" in " ".join(result.stdout.split())
    assert "Traceback" not in result.stdout + result.stderr
