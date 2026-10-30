# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A worktree whose work could not be committed or merged is kept, and nothing removes it.

A marker beside it (`<worktree>.kept`, holding why) tells the next run that this is kept work, not
a crash leftover, so the run refuses to start rather than tearing it down. Only the user removes it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def _marker(worktree: Path) -> Path:
    return worktree.with_name(f"{worktree.name}.kept")


def _remove_command(worktree: Path) -> str:
    return f"git worktree remove --force {worktree}"


def keep(worktree: Path, reason: str) -> str:
    """Mark `worktree` as kept and return the run's error: why, where it is, how to remove it."""
    message = (
        f"{reason}. The worktree is kept at {worktree} with the run's work. "
        f"Remove it when done: {_remove_command(worktree)}"
    )
    try:
        _marker(worktree).write_text(reason, encoding="utf-8")
    except OSError as exc:
        logger.error("could not mark %s as kept: %s", worktree, exc)
        message += f" (It could not be marked as kept: {exc}; a later run may remove it.)"
    logger.error(message)
    return message


def clear_for_new_run(atom: Any, worktree: Path, wt_path: str, branch: str) -> str | None:
    """Why a new run may not use `worktree` (it holds kept work); else prune a crash leftover."""
    refused = refuse_if_kept(worktree)
    if refused is None:
        # A stale same-named worktree and branch left by a crash would make the add collide.
        atom.run({"intent": "worktree_teardown", "path": wt_path, "branch": branch})
    return refused


def refuse_if_kept(worktree: Path) -> str | None:
    """Why a run may not start on `worktree`: it holds kept work. None when it may."""
    marker = _marker(worktree)
    if not marker.is_file():
        return None
    if not worktree.exists():
        marker.unlink(missing_ok=True)
        return None
    reason = marker.read_text(encoding="utf-8", errors="replace").strip()
    return (
        f"A worktree kept after a failed commit or merge is at {worktree} ({reason}). "
        f"Take what you need from it, then remove it: {_remove_command(worktree)}"
    )
