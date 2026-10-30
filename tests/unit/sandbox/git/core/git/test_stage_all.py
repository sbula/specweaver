# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One stage-and-check for every commit path, and the three callers agree on it.

Proves: TECH-087 FR-6, FR-8

`git add -A` can fail; `diff --cached --quiet` answers 0 (nothing staged), 1 (staged) or anything
else (git failed). Before TECH-087 the worktree commit ignored a failed add and read it as "Nothing
to commit", after which the engine deleted the worktree.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.git.core.atom import GitAtom
from specweaver.sandbox.git.core.engine_executor import EngineGitExecutor
from specweaver.sandbox.git.core.staging import stage_all

if TYPE_CHECKING:
    from pathlib import Path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "a.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _index_locked(repo: Path) -> Path:
    """Another git process holds the index, so `git add -A` fails for any user."""
    (repo / "new.py").write_text("x = 1\n", encoding="utf-8")
    lock = repo / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    return lock


def _engine(repo: Path) -> EngineGitExecutor:
    return EngineGitExecutor(cwd=repo, whitelist=set(GitAtom._ENGINE_WHITELIST))


class _Scripted:
    """An executor answering each git call with the next scripted result."""

    def __init__(self, *results: SimpleNamespace) -> None:
        self._results = list(results)
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> SimpleNamespace:
        self.calls.append(args)
        return self._results.pop(0)


def _r(code: int, stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(exit_code=code, stdout="", stderr=stderr)


# --- stage_all ----------------------------------------------------------------------------


def test_a_changed_file_is_staged(repo: Path) -> None:
    (repo / "a.py").write_text("a = 2\n", encoding="utf-8")

    assert stage_all(_engine(repo)) == (True, None)


def test_a_clean_tree_has_nothing_staged(repo: Path) -> None:
    assert stage_all(_engine(repo)) == (False, None)


def test_a_deleted_file_is_staged(repo: Path) -> None:
    (repo / "a.py").unlink()

    assert stage_all(_engine(repo)) == (True, None)


def test_a_failed_add_is_an_error_with_gits_words(repo: Path) -> None:
    lock = _index_locked(repo)
    try:
        staged, error = stage_all(_engine(repo))
    finally:
        lock.unlink()

    assert staged is False
    assert error is not None
    assert "index.lock" in error


def test_a_directory_that_is_no_repository_is_an_error(tmp_path: Path) -> None:
    staged, error = stage_all(_engine(tmp_path))

    assert (staged, bool(error)) == (False, True)


def test_a_diff_that_failed_is_an_error_not_staged() -> None:
    executor = _Scripted(_r(0), _r(128, "fatal: bad index"))

    assert stage_all(executor) == (False, "git diff failed: fatal: bad index")
    assert executor.calls == [("add", "-A"), ("diff", "--cached", "--quiet")]


def test_a_failed_add_runs_no_diff() -> None:
    executor = _Scripted(_r(128, "fatal: unable to index"))

    assert stage_all(executor) == (False, "git add failed: fatal: unable to index")
    assert executor.calls == [("add", "-A")]


def test_a_failure_with_no_error_text_still_says_which_step() -> None:
    executor = _Scripted(SimpleNamespace(exit_code=1, stdout="", stderr=None))

    assert stage_all(executor) == (False, "git add failed: exit 1")
