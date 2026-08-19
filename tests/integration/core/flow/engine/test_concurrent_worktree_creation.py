# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Concurrent worktree creation over a real repository, which nothing exercised.

Proves: TECH-062 FR-1

`C-FLOW-03` declared two FRs for hazards of concurrent fan-out — a port offset injected per sandbox,
and worktree creation serialised behind paused background GC. Neither mechanism existed in the
source. Both rows were deleted from that design so the descope is visible, and the question left was
whether the hazards themselves are real.

**Measured 2026-08-19, and they are not — here.** `run_fan_out` is genuinely concurrent
(`asyncio.gather` over one sub-runner each) and each sub-run can reach `worktree_add`. Driving 32 of
those concurrently against a real repository on **git 2.53.0** produced 32 worktrees and zero
failures. Git takes its own lock around the worktree administrative area; the serialisation FR-4
described would have been a second lock over one that already works.

Port collisions cannot occur at all: nothing in the flow engine allocates or injects a port, so FR-3
described a guard for a mechanism this codebase does not have.

So this is a **guard, not a fix**. It is the concurrent fan-out over real worktrees that no test ran
— the reason a claim about concurrency survived delivery uncontested — and it fails if a future
change, or a git that does contend, breaks what is currently true.
"""

from __future__ import annotations

import asyncio
import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.git.core.atom import GitAtom

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

#: High enough to contend if contention exists, low enough to stay a fast test. The reproduction ran
#: 8 and then 32; both were clean, so the number is about confidence rather than a known threshold.
CONCURRENCY = 16


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A real git repository with one commit — `worktree add` needs a HEAD to branch from."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(command, cwd=repo, check=True)
    (repo / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


async def _add_concurrently(repo: Path, count: int) -> list[object]:
    atom = GitAtom(cwd=repo)

    def add(index: int) -> object:
        return atom.run(
            {
                "intent": "worktree_add",
                "path": str(repo / ".worktrees" / f"w{index}"),
                "branch": f"b{index}",
            }
        )

    return list(await asyncio.gather(*[asyncio.to_thread(add, i) for i in range(count)]))


async def test_concurrent_worktree_creation_does_not_collide(repository: Path) -> None:
    """The hazard FR-4 was written for. It does not occur, and this says so out loud."""
    results = await _add_concurrently(repository, CONCURRENCY)

    failed = [r for r in results if r.status.name != "SUCCESS"]
    assert not failed, [r.message for r in failed]


async def test_every_worktree_actually_exists_afterwards(repository: Path) -> None:
    """SUCCESS from every call is not the claim — the claim is that every worktree is there.

    A guard asserting only the return status would pass an implementation that reported success and
    created nothing, which is the shape this repo keeps finding.
    """
    await _add_concurrently(repository, CONCURRENCY)

    created = sorted(p.name for p in (repository / ".worktrees").iterdir())
    assert created == sorted(f"w{i}" for i in range(CONCURRENCY))


async def test_git_itself_lists_them_all(repository: Path) -> None:
    """The directories existing is not the same as git knowing about them."""
    await _add_concurrently(repository, CONCURRENCY)

    listing = subprocess.run(
        ["git", "worktree", "list"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    for index in range(CONCURRENCY):
        assert f"w{index}" in listing, f"git does not know about w{index}:\n{listing}"
