# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-02 (T1): worktree_commit — stage + commit the session worktree.

Commits the accumulated worktree changes onto the session branch BEFORE the reconcile
(strip_merge needs committed changes to merge — fixing TECH-012 Gap 1). Skips an empty
commit when the worktree is clean.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.git.core.atom import GitAtom
from specweaver.sandbox.git.core.worktree_ops import handle_worktree_commit

if TYPE_CHECKING:
    from pathlib import Path


class _FakeExec:
    def __init__(self, results: list) -> None:
        self.calls: list[tuple] = []
        self._results = results
        self._i = 0

    def run(self, *args: str):
        self.calls.append(args)
        res = self._results[self._i] if self._i < len(self._results) else SimpleNamespace(exit_code=0, stderr="")
        self._i += 1
        return res


def _ok() -> SimpleNamespace:
    return SimpleNamespace(exit_code=0, stderr="", stdout="")


def _has_changes() -> SimpleNamespace:
    return SimpleNamespace(exit_code=1, stderr="", stdout="")  # diff --cached --quiet: 1 = changes


# --- Happy: dirty worktree → add + commit ---------------------------------


def test_dirty_worktree_commits() -> None:
    ex = _FakeExec([_ok(), _has_changes(), _ok()])  # add, diff(changes), commit
    res = handle_worktree_commit(ex)
    assert res.status == AtomStatus.SUCCESS
    assert ("add", "-A") in ex.calls
    assert any(c[0] == "commit" for c in ex.calls)


# --- Boundary: clean worktree → skip empty commit -------------------------


def test_clean_worktree_skips_commit() -> None:
    ex = _FakeExec([_ok(), _ok()])  # add, diff(no changes: exit 0)
    res = handle_worktree_commit(ex)
    assert res.status == AtomStatus.SUCCESS
    assert not any(c[0] == "commit" for c in ex.calls)


# --- Graceful degradation: commit failure surfaced ------------------------


def test_commit_failure_is_surfaced() -> None:
    ex = _FakeExec([_ok(), _has_changes(), SimpleNamespace(exit_code=1, stderr="commit boom", stdout="")])
    res = handle_worktree_commit(ex)
    assert res.status == AtomStatus.FAILED
    assert "boom" in res.message


# --- Hostile: intent without a path → FAILED ------------------------------


def test_intent_missing_path_fails(tmp_path: Path) -> None:
    atom = GitAtom(cwd=tmp_path)
    res = atom.run({"intent": "worktree_commit"})  # no 'path'
    assert res.status == AtomStatus.FAILED
    assert "path" in res.message.lower()
