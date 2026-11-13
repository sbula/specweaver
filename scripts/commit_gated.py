#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Commit the named paths only after the full suite, the `cb` gate and the `doc` gate pass.

    .venv/bin/python scripts/commit_gated.py "<message>" <path> [<path> ...]

The gates run in that order and stop at the first red one, whose whole output is printed. Only the
named paths are staged. Work already staged elsewhere is refused before anything runs, because
`git commit` takes the whole index. The mutation ledger is never committed. Leave the tree alone
while the gates run: a file changed during the suite is committed unverified.

Before the commit it prints every `[agreed <date>]` tag the staged diff adds, with file, line and
text. A tag that leaves one line and lands on another is printed as moved, with both rows: moving a
tag can claim approval for a different decision. It reports; it never blocks.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Protocol

#: `(file, line, text)` of one diff row.
Row = tuple[str, int, str]

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
NEVER_COMMITTED = ("scripts/baselines/mutation_findings.json",)
GATES: tuple[tuple[str, list[str]], ...] = (
    ("suite", [PY, "-m", "pytest", "-n", "auto", "-q", "--tb=short", "-p", "no:cacheprovider"]),
    ("cb", [PY, "scripts/quality.py", "cb"]),
    ("doc", [PY, "scripts/quality.py", "doc"]),
)


_AGREED = re.compile(r"\[agreed \d{4}-\d{2}-\d{2}\]")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


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


def _tagged_rows(diff: str) -> tuple[list[tuple[str, Row]], list[tuple[str, Row]]]:
    """`(removed, added)` `(tag, row)` pairs of a `git diff -U0`, read by hunk counts."""
    removed: list[tuple[str, Row]] = []
    added: list[tuple[str, Row]] = []
    old_path, path, old_no, new_no, old_left, new_left = "", "", 0, 0, 0, 0
    for line in diff.splitlines():
        if old_left or new_left:
            if line.startswith("-") and old_left:
                removed += [(tag, (old_path, old_no, line[1:])) for tag in _AGREED.findall(line)]
                old_no, old_left = old_no + 1, old_left - 1
            elif line.startswith("+") and new_left:
                added += [(tag, (path, new_no, line[1:])) for tag in _AGREED.findall(line)]
                new_no, new_left = new_no + 1, new_left - 1
            continue
        if line.startswith("--- "):
            old_path = line[4:].removeprefix("a/")
        elif line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
        elif m := _HUNK.match(line):
            old_no, new_no = int(m[1]), int(m[3])
            old_left = 1 if m[2] is None else int(m[2])
            new_left = 1 if m[4] is None else int(m[4])
    return removed, added


def approvals_claimed(diff: str) -> list[tuple[str, Row | None, Row]]:
    """`("added", None, row)` or `("moved", old_row, row)` for each tag the diff adds."""
    removed, added = _tagged_rows(diff)
    claims: list[tuple[str, Row | None, Row]] = []
    for tag, row in added:
        source = next((r for r in removed if r[0] == tag), None)
        if source is None:
            claims.append(("added", None, row))
        else:
            removed.remove(source)
            claims.append(("moved", source[1], row))
    return claims


def _print_claims(run: Runner) -> None:
    claims = approvals_claimed(run(["git", "diff", "--cached", "-U0", "--no-color"]).stdout)
    print(f"approvals claimed in this commit: {len(claims) or 'none'}")
    for _kind, old, (path, no, text) in claims:
        if old is None:
            print(f"  added  {path}:{no}  {text.strip()}")
        else:
            print(f"  moved  from {old[0]}:{old[1]}  {old[2].strip()}")
            print(f"         to   {path}:{no}  {text.strip()}")


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
    _print_claims(run)
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
