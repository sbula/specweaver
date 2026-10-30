# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A worktree kept after a failed commit or merge is marked, and a later run refuses to touch it.

Proves: TECH-087 FR-7
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.flow.engine.kept_worktree import keep, refuse_if_kept

if TYPE_CHECKING:
    from pathlib import Path


def _worktree(tmp_path: Path) -> Path:
    worktree = tmp_path / ".worktrees" / "task-1"
    worktree.mkdir(parents=True)
    return worktree


def test_keep_names_the_path_and_the_remove_command(tmp_path: Path) -> None:
    worktree = _worktree(tmp_path)

    message = keep(worktree, "worktree commit failed: fatal: index.lock exists")

    assert message.startswith("worktree commit failed: fatal: index.lock exists.")
    assert f"kept at {worktree}" in message
    assert f"git worktree remove --force {worktree}" in message
    assert (tmp_path / ".worktrees" / "task-1.kept").read_text(encoding="utf-8") == (
        "worktree commit failed: fatal: index.lock exists"
    )


def test_a_kept_worktree_refuses_the_next_run(tmp_path: Path) -> None:
    worktree = _worktree(tmp_path)
    keep(worktree, "strip-merge failed: conflict")

    refused = refuse_if_kept(worktree)

    assert refused is not None
    assert "strip-merge failed: conflict" in refused
    assert f"git worktree remove --force {worktree}" in refused
    assert worktree.is_dir()


def test_no_marker_is_no_refusal(tmp_path: Path) -> None:
    assert refuse_if_kept(_worktree(tmp_path)) is None


def test_a_marker_whose_worktree_is_gone_is_dropped(tmp_path: Path) -> None:
    worktree = _worktree(tmp_path)
    keep(worktree, "commit failed")
    worktree.rmdir()

    assert refuse_if_kept(worktree) is None
    assert not (tmp_path / ".worktrees" / "task-1.kept").exists()


def test_a_marker_that_cannot_be_written_is_said(tmp_path: Path) -> None:
    worktree = _worktree(tmp_path)
    (tmp_path / ".worktrees" / "task-1.kept").mkdir()  # a folder where the marker goes

    message = keep(worktree, "commit failed")

    assert f"kept at {worktree}" in message
    assert "could not be marked" in message


def test_a_damaged_marker_still_refuses(tmp_path: Path) -> None:
    worktree = _worktree(tmp_path)
    (tmp_path / ".worktrees" / "task-1.kept").write_bytes(b"\xff\xfe broken")

    refused = refuse_if_kept(worktree)

    assert refused is not None
    assert f"git worktree remove --force {worktree}" in refused
