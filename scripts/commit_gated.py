#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Commit the named paths only after the full suite, the `cb` gate and the `doc` gate pass.

    .venv/bin/python scripts/commit_gated.py "<message>" <path> [<path> ...]

The gates run in that order and stop at the first red one, whose whole output is printed. Only the
named paths are staged. Work already staged elsewhere is refused before anything runs, because
`git commit` takes the whole index. The mutation ledger is never committed. Leave the tree alone
while the gates run: a file changed during the suite is committed unverified.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
NEVER_COMMITTED = ("scripts/baselines/mutation_findings.json",)
GATES: tuple[tuple[str, list[str]], ...] = (
    ("suite", [PY, "-m", "pytest", "-n", "auto", "-q", "--tb=short", "-p", "no:cacheprovider"]),
    ("cb", [PY, "scripts/quality.py", "cb"]),
    ("doc", [PY, "scripts/quality.py", "doc"]),
)


class Runner(Protocol):
    def __call__(
        self, cmd: list[str], stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]: ...


def run_in_repo(cmd: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run from the repo root with the venv first on PATH: e2e tests call a bare `python`."""
    path = os.environ.get("PATH", "")
    env = {**os.environ, "PATH": f"{REPO_ROOT / '.venv' / 'bin'}{os.pathsep}{path}"}
    return subprocess.run(
        cmd, cwd=REPO_ROOT, input=stdin, capture_output=True, text=True, check=False, env=env
    )


def _staged(run: Runner) -> list[str]:
    return run(["git", "diff", "--cached", "--name-only"]).stdout.split()


def _inside(path: str, roots: list[str]) -> bool:
    return any(r in (".", path) or path.startswith(r.rstrip("/") + "/") for r in roots)


def _gates_pass(run: Runner) -> bool:
    for name, cmd in GATES:
        proc = run(cmd)
        if proc.returncode != 0:
            print(proc.stdout + proc.stderr)
            print(f"{name.upper()} FAILED (exit {proc.returncode}) — nothing staged")
            return False
        lines = proc.stdout.strip().splitlines()
        print(f"{name}: {lines[-1] if lines else 'ok'}")
    return True


def _git_ok(run: Runner, cmd: list[str], stdin: str | None = None) -> bool:
    proc = run(cmd, stdin=stdin)
    if proc.returncode != 0:
        print(f"{' '.join(cmd[:2])} FAILED (exit {proc.returncode}): {proc.stderr.strip()}")
    return proc.returncode == 0


def commit(message: str, paths: list[str], run: Runner) -> int:
    """0 committed; 1 refused by a gate or the index; 2 called wrongly."""
    if not message.strip() or not paths:
        print('usage: commit_gated.py "<message>" <path> [<path> ...]')
        return 2
    elsewhere = [p for p in _staged(run) if not _inside(p, paths)]
    if elsewhere:
        print(f"already staged outside the named paths: {', '.join(elsewhere)}")
        return 1
    if not _gates_pass(run):
        return 1
    if not _git_ok(run, ["git", "add", "-A", "--", *paths]):
        return 1
    staged = _staged(run)
    protected = [p for p in staged if p in NEVER_COMMITTED]
    if protected:
        run(["git", "restore", "--staged", "--", *protected])
        print(f"never committed: {', '.join(protected)} — unstaged; name the paths you mean")
        return 1
    if not staged:
        print("nothing staged: the named paths have no changes")
        return 1
    if not _git_ok(run, ["git", "commit", "-q", "-F", "-"], stdin=message):
        return 1
    print(run(["git", "log", "--oneline", "-1"]).stdout.strip())
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        return commit("", [], run_in_repo)
    return commit(args[0], args[1:], run_in_repo)


if __name__ == "__main__":
    sys.exit(main())
