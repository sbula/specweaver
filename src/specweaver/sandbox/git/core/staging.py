# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Staging every change and telling whether anything is staged — one way for every commit path."""

from __future__ import annotations

from typing import Any, NamedTuple, Protocol


class _Runs(Protocol):
    def run(self, command: str, *args: str) -> Any: ...


class Staged(NamedTuple):
    """`staged` when changes wait to be committed; `error` when git could not tell."""

    staged: bool
    error: str | None


def stage_all(executor: _Runs) -> Staged:
    """`git add -A`, then `diff --cached --quiet`: 0 is nothing staged, 1 is staged, else an error."""
    added = executor.run("add", "-A")
    if added.exit_code != 0:
        return Staged(staged=False, error=f"git add failed: {_why(added)}")
    diff = executor.run("diff", "--cached", "--quiet")
    if diff.exit_code not in (0, 1):
        return Staged(staged=False, error=f"git diff failed: {_why(diff)}")
    return Staged(staged=diff.exit_code == 1, error=None)


def _why(result: Any) -> str:
    """Git's own words, else the exit code."""
    return (result.stderr or "").strip() or f"exit {result.exit_code}"
