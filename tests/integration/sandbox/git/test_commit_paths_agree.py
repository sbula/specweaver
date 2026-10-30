# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The checkpoint, the agent commit tool and the worktree commit agree, on real git.

Proves: TECH-087 FR-6, FR-8

All three stage through `staging.stage_all`; each keeps its own meaning of "nothing to commit"
(checkpoint SUCCESS, agent tool error, worktree SUCCESS) and all three fail on a failed add.
Before TECH-087 the worktree commit alone read a failed add as success.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.git.core.atom import GitAtom
from specweaver.sandbox.git.core.executor import GitExecutor
from specweaver.sandbox.git.interfaces.tool import GitTool, whitelist_for_role

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


# --- the three callers agree ---------------------------------------------------------------


def _checkpoint(repo: Path) -> tuple[bool, str]:
    result = GitAtom(cwd=repo).run({"intent": "checkpoint", "message": "chore: cp"})
    return result.status == AtomStatus.SUCCESS, result.message


def _agent_commit(repo: Path) -> tuple[bool, str]:
    executor = GitExecutor(cwd=repo, whitelist=whitelist_for_role("implementer"))
    result = GitTool(executor, role="implementer").commit("feat: change")
    return result.status == "success", result.message


def _worktree_commit(repo: Path) -> tuple[bool, str]:
    result = GitAtom(cwd=repo).run({"intent": "worktree_commit", "path": "."})
    return result.status == AtomStatus.SUCCESS, result.message


_CALLERS = [
    pytest.param(_checkpoint, True, id="checkpoint"),
    pytest.param(_agent_commit, False, id="agent-commit"),
    pytest.param(_worktree_commit, True, id="worktree-commit"),
]


@pytest.mark.integration
@pytest.mark.parametrize(("commit", "clean_is_success"), _CALLERS)
def test_each_caller_keeps_its_own_nothing_to_commit(
    repo: Path, commit, clean_is_success: bool
) -> None:
    ok, message = commit(repo)

    assert ok is clean_is_success
    assert "othing to commit" in message or "No changes to commit" in message


@pytest.mark.integration
@pytest.mark.parametrize(("commit", "clean_is_success"), _CALLERS)
def test_each_caller_commits_a_change(repo: Path, commit, clean_is_success: bool) -> None:
    (repo / "a.py").write_text("a = 3\n", encoding="utf-8")

    ok, _ = commit(repo)

    assert ok is True
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert len(log.splitlines()) == 2


@pytest.mark.integration
@pytest.mark.parametrize(("commit", "clean_is_success"), _CALLERS)
def test_each_caller_fails_on_a_failed_add(repo: Path, commit, clean_is_success: bool) -> None:
    lock = _index_locked(repo)
    try:
        ok, message = commit(repo)
    finally:
        lock.unlink()

    assert ok is False
    assert "index.lock" in message
