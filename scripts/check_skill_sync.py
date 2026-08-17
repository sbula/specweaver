#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Verify the two skill trees are identical.

`.agents/skills/` is the tool-neutral path (read by Gemini/Antigravity and anything else);
`.claude/skills/` is what Claude Code reads. They hold the same files by CONVENTION ONLY — measured
2026-07-25, all 26 pairs are separate files (`st_nlink == 1`), not hardlinks. Nothing in the repo
keeps them in step; the Claude Code harness appears to mirror them, which means an edit made while
working in a DIFFERENT agent updates only one side and the other silently goes stale.

This check is therefore the only thing standing between you and an agent following an outdated
skill. Run it in the pre-commit gate.

Note on `st_ino`: do NOT use inode equality to detect hardlinks here. On this workspace's
filesystem two distinct files reported the SAME `st_ino` while both had `st_nlink == 1`. Content
comparison is the reliable signal.

**Symlinked skills count as in sync, and the walk must follow them.** One side may point a whole
skill directory at the other -- `.claude/skills/grill-me -> ../../.agents/skills/grill-me` -- which
is a STRONGER guarantee than a copy: the two sides cannot drift, because there is one file.
`Path.rglob` does not descend into symlinked directories, so the naive walk reported every file
under such a link as MISSING and inverted the rule. `os.walk(followlinks=True)` reads through, and
content comparison still judges what it finds -- a link pointing somewhere unrelated is reported as
DIFFERS rather than waved through.

Exit code 1 if the trees differ (missing file on either side, or differing content).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
AGENT_SKILLS = REPO_ROOT / ".agents" / "skills"


def _relative_files(root: Path) -> dict[Path, Path]:
    """Map each file's path relative to `root` -> its absolute path, reading through symlinks.

    `followlinks=True` is what makes a symlinked skill directory visible. It also makes a
    self-referential link walk forever, so every directory is visited at most once by its resolved
    identity -- a cycle then contributes its files and stops rather than hanging the gate.
    """
    if not root.is_dir():
        return {}

    found: dict[Path, Path] = {}
    seen: set[Path] = set()
    for parent, dirs, names in os.walk(root, followlinks=True):
        here = Path(parent)
        real = here.resolve()
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        for name in names:
            path = here / name
            if path.is_file():
                found[path.relative_to(root)] = path
    return dict(sorted(found.items()))


def main(argv: list[str] | None = None) -> int:
    # Optional path overrides exist so this check is testable. Against the live directories it is
    # NOT: while Claude Code is running it mirrors the two trees bidirectionally in real time and
    # silently undoes any drift you try to introduce (verified 2026-07-25 — an appended line was
    # propagated, and deleting one side deleted the other). Point it at fixtures instead.
    args = sys.argv[1:] if argv is None else argv
    left = Path(args[0]).resolve() if len(args) > 0 else CLAUDE_SKILLS
    right = Path(args[1]).resolve() if len(args) > 1 else AGENT_SKILLS

    if not left.is_dir() and not right.is_dir():
        print("Skill sync check: neither skill tree exists — nothing to compare.")
        return 0

    claude = _relative_files(left)
    agents = _relative_files(right)

    errors: list[str] = []

    for rel in sorted(set(claude) | set(agents)):
        in_claude, in_agents = claude.get(rel), agents.get(rel)
        if in_claude is None:
            errors.append(f"MISSING in {left}: {rel.as_posix()}")
        elif in_agents is None:
            errors.append(f"MISSING in {right}: {rel.as_posix()}")
        elif in_claude.read_bytes() != in_agents.read_bytes():
            errors.append(f"DIFFERS: {rel.as_posix()}")

    for msg in errors:
        print(f"  ERROR: {msg}")

    total = len(set(claude) | set(agents))
    print(f"Skill sync check: {total} file(s), {len(errors)} error(s)")

    if errors:
        print(
            "\nThe two skill trees have drifted. Decide which side is correct, then copy it over\n"
            "the other:\n"
            "  cp .agents/skills/<rel> .claude/skills/<rel>   # or the reverse\n"
            "Nothing keeps these in step automatically outside Claude Code, so a skill edited\n"
            "while working in another agent updates only one side."
        )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
