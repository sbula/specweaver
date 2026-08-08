#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Assert that every repo-rooted path an instruction file declares actually resolves on disk.

Skill instructions are never checked against the repository they instruct on, so they rot silently
and the agent absorbs the rot as truth. `TECH-008` modularized
`docs/architecture/architecture_reference.md` into `docs/architecture/{01..07}_*/` and deleted the
file; six live instruction sites went on ordering the agent to read it. Every design,
implementation-plan and pre-commit run for the next fortnight was told to load architecture that
could not load -- so the agent either skipped the step its phase depended on, or filled the gap
from training data and reported architecture it had never read. One site was worse: it directed
*new* boundary-violation records into the deleted file, so they were written nowhere.

This is the same invariant class as the handler-reachability test (`f7a0f34f`) -- *a declared
reference must resolve* -- applied to instructions instead of pipeline steps.

WHAT IS ENFORCED, AND WHY SO NARROWLY
-------------------------------------
Only a path-shaped token meeting all five rules in `is_enforced` is checked. The narrowness is the
point: a naive "every path-shaped token must resolve" rule flags 34 distinct references on this
repo, of which 4 are real. An 88% false-positive rate is not a strict checker, it is a checker
somebody switches off within a day, and then nothing is enforced at all.

Rules 4 and 5 were MEASURED into existence, not anticipated. Rules 1-3 alone still produced two
false positives on the live tree: `US-NN_integration.md` (a template whose placeholder is `NN`,
not one of the `[`/`<`/`*` metacharacters) and `tests/unit/test_foo.py` (a stand-in filename in
`specweaver-dev`'s TDD walkthrough, four times). Both are pinned by tests. They are not redundant.

The accepted trade: shorthand (`flow/models.py`) and bare basenames (`check_fr_coverage.py`) are
NOT enforced. Resolving them needs a convention that does not exist, and inventing one costs the
zero-false-positive property that makes this check survivable.

A green run does not mean the instructions are *good*. Repointing a broken reference at any file
that happens to resolve -- `README.md`, say -- passes here while telling the agent nothing. That
cannot be checked mechanically; it is why TECH-019's repairs named a specific document per site.

SCOPE
-----
`.agents/` and every `CLAUDE.md` are scanned. `.claude/` deliberately is NOT: it is byte-identical
to `.agents/`, and `check_skill_sync.py` is what enforces that. Half this check's coverage
therefore leans on `skill_sync` -- deleting that check is also a decision about this one. Scanning
both trees instead would double every real finding, which is the noise that gets checkers ignored.

`docs/roadmap/features/**` is never scanned. Delivered designs and implementation plans mention the
deleted file legitimately: they are records of what was true then, and editing them is what
finished-stories-immutable forbids.

Exit code 1 if any enforced reference does not resolve.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Rule 2 -- real top-level entries of the repo. A first segment outside this set means the token
#: is shorthand (`flow/models.py`), not a claim about a location.
TOP_LEVEL = frozenset({"docs", "src", "tests", "scripts", "specs", ".agents", ".claude"})

#: Rule 3 -- template metacharacters, e.g. `[ID]`, `<skill-name>`, `topic_*.md`.
PLACEHOLDER_CHARS = frozenset("[<*{}]>")

#: Rule 4 -- uppercase stand-in tokens occupying a whole path segment, e.g. `US-NN_integration.md`.
PLACEHOLDER_TOKEN = re.compile(r"(?:^|[/_.-])(?:NN|XX|ID|SFxx|N)(?:[/_.-]|$)")

#: Rule 5 -- repo-rooted paths that are illustrative rather than claims about disk.
#: An entry is a TRACKED exception, not a silent pass: each must state why, and a test asserts it.
EXAMPLE_ALLOWLIST: dict[str, str] = {
    "tests/unit/test_foo.py": (
        "worked example in specweaver-dev's TDD walkthrough -- a stand-in filename, not a file"
    ),
}

#: A path-shaped token. Deliberately not anchored to inline backticks: the site at
#: `phase-1-architecture.md:13` sat inside a ``` fence, and a backtick-only scan missed it.
TOKEN = re.compile(r"[\w./\-\[\]<>*{}]+\.(?:md|py|yaml|yml|toml|json|txt|cfg|ini|html)")

#: Trailing punctuation that belongs to the prose, not the path.
_TRIM = "`.,;:)!?\"'"


def is_enforced(ref: str) -> bool:
    """True when `ref` asserts that a specific file lives at a specific place in this repo."""
    if "/" not in ref:
        return False
    if any(c in ref for c in PLACEHOLDER_CHARS):
        return False
    if ref.split("/", 1)[0] not in TOP_LEVEL:
        return False
    if PLACEHOLDER_TOKEN.search(ref):
        return False
    return ref not in EXAMPLE_ALLOWLIST


def default_scan_scope() -> list[Path]:
    """The live instruction files: `.agents/**/*.md` plus every tracked `CLAUDE.md`."""
    files = sorted((REPO_ROOT / ".agents").rglob("*.md"))
    files += sorted(
        p
        for p in REPO_ROOT.rglob("CLAUDE.md")
        if not any(part in {".venv", ".tmp", ".git", "node_modules"} for part in p.parts)
    )
    return files


def scan_files(files: Iterable[Path], repo_root: Path) -> list[tuple[Path, int, str]]:
    """Return `(file, line number, reference)` for every enforced reference that does not resolve.

    A file that cannot be read is itself a finding rather than a traceback -- an instruction the
    checker cannot read is exactly as unverified as one pointing at a missing file.
    """
    findings: list[tuple[Path, int, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append((path, 0, f"unreadable instruction file ({exc.strerror or exc})"))
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for raw in TOKEN.findall(line):
                ref = raw.strip(_TRIM)
                if is_enforced(ref) and not _resolves_within(repo_root, ref):
                    findings.append((path, lineno, ref))
    return findings


def _resolves_within(repo_root: Path, ref: str) -> bool:
    """True when `ref` names an existing file that is still inside the repository.

    Containment matters as much as existence: a reference that resolves only by climbing out of
    the repo (`docs/../../elsewhere.md`) is unresolvable for anyone who checks this out at a
    different path, which is precisely the breakage this check exists to prevent.
    """
    candidate = (repo_root / ref).resolve()
    if not candidate.exists():
        return False
    return candidate.is_relative_to(repo_root.resolve())


def main(argv: list[str] | None = None) -> int:
    # Optional roots exist so the check is testable against fixtures instead of the live tree.
    args = sys.argv[1:] if argv is None else argv
    if args:
        roots = [Path(a).resolve() for a in args]
        files = [p for root in roots for p in sorted(root.rglob("*.md"))]
        repo_root = roots[0]
    else:
        files, repo_root = default_scan_scope(), REPO_ROOT

    findings = scan_files(files, repo_root)

    for path, lineno, ref in findings:
        rel = path.relative_to(repo_root) if path.is_relative_to(repo_root) else path
        print(f"  ERROR: {rel.as_posix()}:{lineno} -> {ref}")

    print(f"Skill reference check: {len(files)} file(s), {len(findings)} dangling reference(s)")

    if findings:
        print(
            "\nAn instruction points at a file that does not exist, so the agent following it "
            "loads\nnothing where it expects content -- or invents it. Repoint each reference at "
            "the document\nthat now holds what the instruction asked for. Do NOT repoint at "
            "whatever merely resolves:\nthat turns a loud failure into a silent one."
        )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
