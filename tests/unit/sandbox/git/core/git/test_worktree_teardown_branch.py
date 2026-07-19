# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-01 (T2): handle_worktree_teardown deletes the branch when passed.

The per-run session names a unique branch and must delete it at teardown (fixing
the INT-US-09 orphan-branch defect). Backward-compatible: no `branch` key → no delete.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.git.core.worktree_ops import handle_worktree_teardown

if TYPE_CHECKING:
    from pathlib import Path


class _FakeExec:
    """Records .run(*args) calls; returns queued results (default exit_code 0)."""

    def __init__(self, results: list | None = None) -> None:
        self.calls: list[tuple] = []
        self._results = results or []
        self._i = 0

    def run(self, *args: str):
        self.calls.append(args)
        res = (
            self._results[self._i]
            if self._i < len(self._results)
            else SimpleNamespace(exit_code=0, stderr="")
        )
        self._i += 1
        return res


def _branch_delete_calls(ex: _FakeExec) -> list[tuple]:
    return [c for c in ex.calls if c[:2] == ("branch", "-D")]


# --- Happy: branch deleted after clean worktree removal -------------------


def test_branch_deleted_when_present(tmp_path: Path) -> None:
    ex = _FakeExec([SimpleNamespace(exit_code=0, stderr="")])  # worktree remove OK
    res = handle_worktree_teardown(ex, tmp_path, {"path": ".worktrees/session-x", "branch": "sf-session-x"})
    assert res.status == AtomStatus.SUCCESS
    assert _branch_delete_calls(ex) == [("branch", "-D", "sf-session-x")]


# --- Boundary: no branch key → backward-compatible (no delete) ------------


def test_no_branch_key_does_not_delete(tmp_path: Path) -> None:
    ex = _FakeExec([SimpleNamespace(exit_code=0, stderr="")])
    res = handle_worktree_teardown(ex, tmp_path, {"path": ".worktrees/session-x"})
    assert res.status == AtomStatus.SUCCESS
    assert _branch_delete_calls(ex) == []


# --- Graceful degradation: branch-delete failure is logged, not raised ----


def test_branch_delete_failure_is_best_effort(tmp_path: Path) -> None:
    ex = _FakeExec(
        [
            SimpleNamespace(exit_code=0, stderr=""),  # worktree remove OK
            SimpleNamespace(exit_code=1, stderr="branch not fully merged"),  # branch -D fails
        ]
    )
    res = handle_worktree_teardown(ex, tmp_path, {"path": ".worktrees/session-x", "branch": "sf-session-x"})
    # teardown still succeeds; the failed branch-delete was attempted and swallowed
    assert res.status == AtomStatus.SUCCESS
    assert _branch_delete_calls(ex) == [("branch", "-D", "sf-session-x")]


def test_branch_deleted_on_fallback_path(tmp_path: Path) -> None:
    """[Graceful degradation] When the primary `worktree remove` fails (Windows lock),
    the branch is still deleted on the rmtree/prune fallback path."""
    ex = _FakeExec(
        [
            SimpleNamespace(exit_code=1, stderr="locked"),  # worktree remove FAILS → fallback
            SimpleNamespace(exit_code=0, stderr=""),  # worktree prune
            SimpleNamespace(exit_code=0, stderr=""),  # branch -D
        ]
    )
    # The worktree path does not exist under tmp_path → rmtree block is skipped.
    res = handle_worktree_teardown(ex, tmp_path, {"path": ".worktrees/session-x", "branch": "sf-session-x"})
    assert res.status == AtomStatus.SUCCESS
    assert _branch_delete_calls(ex) == [("branch", "-D", "sf-session-x")]
