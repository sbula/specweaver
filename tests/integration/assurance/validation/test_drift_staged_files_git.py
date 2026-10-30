# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw drift check-rot --staged` against real git: the hook's index, and no git at all.

Proves: TECH-087 FR-17

`SubprocessExecutor` keeps only allowlisted variables. Inside a pre-commit hook, `git commit -a` and
`git commit <paths>` point `GIT_INDEX_FILE` at a temporary index. Without it, drift would read the
main index and check other files than the commit's.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
import typer

from specweaver.assurance.validation.interfaces import cli_drift

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> None:
    import os

    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env or os.environ)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "a.py").write_text("A = 1\n", encoding="utf-8")
    _git(root, "add", "a.py")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_the_hook_s_index_is_the_one_read(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    (repo / "b.py").write_text("B = 1\n", encoding="utf-8")
    hook_index = tmp_path / "hook-index"
    env = {**os.environ, "GIT_INDEX_FILE": str(hook_index)}
    _git(repo, "read-tree", "HEAD", env=env)
    _git(repo, "add", "b.py", env=env)
    monkeypatch.chdir(repo)
    assert cli_drift._staged_files() == []  # the main index stages nothing

    monkeypatch.setenv("GIT_INDEX_FILE", str(hook_index))

    assert cli_drift._staged_files() == ["b.py"]


def test_no_git_on_path_is_one_line_and_exit_1(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PATH", str(empty))

    with pytest.raises(typer.Exit) as exited:
        cli_drift._staged_files()

    assert exited.value.exit_code == 1
    assert "Failed to query git index:" in " ".join(capsys.readouterr().out.split())
