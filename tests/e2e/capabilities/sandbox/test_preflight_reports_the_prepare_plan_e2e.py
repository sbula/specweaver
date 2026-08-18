# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw sandbox preflight` tells a project what the sandbox will do to it, before a run costs anything.

`TECH-031`'s last candidate approach. The three fixes before it each added behaviour a reader would
otherwise meet by surprise, minutes into a containerised run: a project without a lockfile is
resolved fresh and stops reproducing its own pins; tox lines needing substitution are skipped; a
project declaring no runner is given one the sandbox chose.

Driven through the real `sw` CLI in a subprocess, because the claim is about what a developer sees
at a terminal. The plan itself is pure and unit-tested; that it is *reachable* is this test's
subject, and the exit code is part of it — a preflight nobody can gate CI on has only moved the
surprise earlier.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.e2e

_LOCKED_AND_DECLARED = (
    '[project]\nname = "t"\nversion = "0.1.0"\ndependencies = []\n\n'
    '[dependency-groups]\ntests = ["pytest"]\n'
)


def _preflight(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "from specweaver.interfaces.cli.main import app; app(prog_name='sw')",
            "sandbox",
            "preflight",
            str(project),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_a_supported_project_is_reported_ready(tmp_path: Path) -> None:
    """Exit 0 is the half that makes the command usable in CI."""
    project = tmp_path / "supported"
    project.mkdir()
    (project / "pyproject.toml").write_text(_LOCKED_AND_DECLARED, encoding="utf-8")
    (project / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    result = _preflight(project)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "Ready" in result.stdout, result.stdout


def test_a_project_the_sandbox_would_change_is_told_what_changes(tmp_path: Path) -> None:
    """The case worth catching early, and the reason exit is non-zero: this project's QA run will
    neither reproduce its pins nor use a runner it chose, and both facts are recoverable in one
    edit each."""
    project = tmp_path / "silent"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "t"\nversion = "0.1.0"\ndependencies = []\n', encoding="utf-8"
    )

    result = _preflight(project)

    assert result.returncode == 1, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "uv.lock" in result.stdout, result.stdout
    assert "supplied by the sandbox" in result.stdout, result.stdout


def test_a_tree_with_no_manifest_is_told_nothing_can_be_built(tmp_path: Path) -> None:
    """22 of the 150 corpus repositories. Meeting this inside a container is the whole complaint."""
    project = tmp_path / "bare"
    project.mkdir()
    (project / "README.md").write_text("nothing\n", encoding="utf-8")

    result = _preflight(project)

    assert result.returncode == 1
    assert "no environment can be built" in result.stdout, result.stdout


def test_a_path_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    """Distinct from a warning exit: nothing was inspected, so nothing may be inferred."""
    missing = tmp_path / "does-not-exist"

    result = _preflight(missing)

    assert result.returncode == 2, f"stdout={result.stdout}\nstderr={result.stderr}"
