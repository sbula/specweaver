#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A retirement is only valid while its target is UNBUILT. `ADR-003`, 2026-08-16 addendum.

Every retirement note `ADR-003` produced carries the same promise:

    The scope above is NOT descoped -- it moves to `X`, which owns its own integration and
    e2e proof as FRs rather than a separate add-on restating them.

**That promise is unsatisfiable when `X` is already delivered.** `finished-stories-immutable`
forbids adding an FR to a closed story, so the scope is retired from one side and never lands on
the other. It then becomes invisible: `check_fr_coverage.py` can only judge an FR somebody wrote,
and nobody can write this one.

Measured on the 2026-08-16 re-audit of `bb789a29`: of 68 deleted ids, 46 named no capability at all
(nothing to restore), 17 pointed only at unbuilt capabilities (correctly retired), and 5 pointed at
a delivered one. Of those 5, `INT-US-03-SF01` -> `D-VAL-03` was live work with nowhere to live:
`resolve_runner` is polyglot, yet `sw implement` hardcodes `src/{stem}.py`. Three of the other four
sat one delivery away from the same fate, which is why the rule is enforced rather than written
down -- a discipline-only clause regrows the defect on the next `✅`.

The remedy for a finding is never to loosen this check: it is to mint a ticket that owns the seam
FR and writes the failing integration/e2e test first, per `specweaver-ticket`'s rule that a defect
in delivered code becomes a NEW ticket rather than an edit to the delivered story.

Usage:
    python scripts/check_retirement_targets.py            # judge the roadmap
    python scripts/check_retirement_targets.py --list     # print every note and its targets
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Authoritative for capability IDs, per `specweaver-ticket` Phase 1. The topic docs repeat these
#: glyphs and drift; the matrix is the one place `check_roadmap_sync.py` already holds to account.
MATRIX = "capability_matrix.md"

#: A capability ID: one DAL letter, a context, a number. Deliberately excludes `ADR-003` (which
#: appears in EVERY note and would flag all of them), `TECH-049`, and the retired `INT-US-NN-SFNN`
#: ids -- none of them match this shape, so the exclusion needs no allow-list to maintain.
_CAPABILITY = re.compile(r"\b([A-E]-[A-Z]+-\d+)\b")

#: `✅ D-VAL-03` inside one code span, which is how the matrix cells are written.
_MATRIX_CELL = re.compile(r"`([^\s`]+)\s+([A-E]-[A-Z]+-\d+)`")

#: The retired entry's own id, taken from the nearest preceding `* **`ID`` bullet (blockquote
#: shape) or from the note line itself (the single-line roadmap shape).
_RETIRED_ID = re.compile(r"`?\b(INT-US-\d+(?:-(?:SF\d+|SUB))?)\b`?")

#: A note line names both, in either order. The lookbehind is load-bearing: `UN-RETIRED` contains
#: `RETIRED`, and a substring match would judge exactly the entries whose retirement was withdrawn
#: -- which name a delivered capability by definition, so every withdrawal would report as a defect.
_IS_NOTE = re.compile(r"(?<![-\w])RETIRED.*ADR-003|ADR-003.*(?<![-\w])RETIRED")

#: The destination clause, and ONLY it. The note's targets are what follows "moves to"; the rest of
#: the block is prose that legitimately names other capabilities -- most importantly a correction
#: explaining which delivered id was dropped and why. Reading the whole block would make writing
#: that correction the offence, so the check would be unfixable by telling the truth.
#:
#: THREE phrasings are in use and all must be read: *"it moves to `X`"*, *"integration owned by
#: `X`"*, and *"what changed is the owner: `X` builds it"*. Reading only the first left six notes
#: resolving to no destination, which the guard then passed in silence -- the failure mode it
#: exists to prevent. Every phrasing added here was found by running `--list` and reading the
#: `(none)` rows, not guessed.
_MOVES_TO = re.compile(
    r"\b(?:mov(?:es?|ed)\s+to|owned\s+by|owner:)\s*(.*?)(?:,\s*which|\.\s|$)",
    re.S,
)

#: Feature design docs are OUT of scope. They record their own sections' history -- `### SF-02: ...
#: RETIRED by ADR-003` -- and name no destination, because the roadmap line already carries it.
#: Judging both would report one retirement twice and demand the destination be written twice.
_REGISTRY = ("master_story_roadmap.md", "topics")

#: Reported as the target of a note that names nobody at all. `INT-US-25-SF01` read *"it moves to
#: the capability that builds it"* -- the unfalsifiable prose `ADR-003` set out to delete, wearing
#: the ADR's own name. Judging only parseable notes would pass every note written that way.
NO_TARGET = "(none named)"

_IS_QUOTE = re.compile(r"^\s*>")

#: A topic-doc entry: `* **`ID` — Name:**` or `* **Name (`ID`)**`. Both shapes are in use.
_ENTRY_BULLET = re.compile(r"^\s*\* \*\*.*INT-US-\d+")

#: Status glyphs that mean "delivered". A retirement pointing at one of these is the defect.
DELIVERED = frozenset({"✅", "🟢"})

#: Reported for a target the matrix does not know. A dangling reference is a finding, not a pass --
#: `TECH-032`'s lesson applied to one row rather than to the whole run.
UNKNOWN = "?"


@dataclass(frozen=True)
class Note:
    """One retirement note, and the capabilities it claims the scope moves to."""

    path: str
    line: int
    retired_id: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class Offender:
    """A note whose target cannot accept the scope it was handed."""

    retired_id: str
    target: str
    status: str
    path: str
    line: int


def capability_status(roadmap: Path) -> dict[str, str]:
    """Map capability ID -> status glyph, read from the capability matrix.

    Raises:
        FileNotFoundError: the matrix is absent. A checker that cannot find its subject must say
            so rather than return `{}` and pass every note by accident.
    """
    matrix = roadmap / MATRIX
    text = matrix.read_text(encoding="utf-8")
    return {cid: glyph for glyph, cid in _MATRIX_CELL.findall(text)}


def _note_block(lines: list[str], index: int) -> tuple[str, str]:
    """Return `(note text, the id being retired)` for the note starting at `index`.

    Two shapes exist and both are load-bearing: the topic docs indent a multi-line `>` blockquote
    under the entry bullet, while `master_story_roadmap.md` writes the whole note on the bullet
    itself. Reading only one shape would silently skip half the notes.
    """
    start = index
    if _IS_QUOTE.match(lines[index]):
        end = index + 1
        while end < len(lines) and _IS_QUOTE.match(lines[end]):
            end += 1
        # The ENTRY BULLET above the blockquote carries the retired id; the note itself rarely
        # repeats it. Scanning back for any id instead picks up whatever the entry's own prose
        # mentions -- two live notes were labelled with the base contract (`INT-US-03`,
        # `INT-US-25`) rather than the add-on retired, sending the reader to the wrong entry.
        back = index - 1
        while back >= 0 and not _ENTRY_BULLET.match(lines[back]):
            back -= 1
        if back < 0:
            back = index - 1
            while back >= 0 and not _RETIRED_ID.search(lines[back]):
                back -= 1
        start = max(back, 0)
        body = "\n".join(lines[index:end])
    else:
        body = lines[index]

    owner = _RETIRED_ID.search(lines[start]) or _RETIRED_ID.search(body)
    return body, owner.group(1) if owner else "(unnamed)"


def retirement_notes(roadmap: Path) -> list[Note]:
    """Every `RETIRED ... by ADR-003` note under `roadmap`, with the targets it moves scope to."""
    found: list[Note] = []
    for path in sorted(roadmap.rglob("*.md")):
        rel = path.relative_to(roadmap)
        if rel.parts[0] not in _REGISTRY:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if not _IS_NOTE.search(line):
                continue
            body, retired_id = _note_block(lines, i)
            clause = "".join(_MOVES_TO.findall(body))
            targets = tuple(sorted(set(_CAPABILITY.findall(clause))))
            found.append(
                Note(
                    path=path.relative_to(roadmap).as_posix(),
                    line=i + 1,
                    retired_id=retired_id,
                    targets=targets,
                )
            )
    return found


def offenders(roadmap: Path) -> list[Offender]:
    """Every (note, target) pair where the target cannot own the seam the note handed it."""
    status = capability_status(roadmap)
    out: list[Offender] = []
    for note in retirement_notes(roadmap):
        if not note.targets:
            out.append(
                Offender(
                    retired_id=note.retired_id,
                    target=NO_TARGET,
                    status=UNKNOWN,
                    path=note.path,
                    line=note.line,
                )
            )
            continue
        for target in note.targets:
            glyph = status.get(target, UNKNOWN)
            if glyph in DELIVERED or glyph == UNKNOWN:
                out.append(
                    Offender(
                        retired_id=note.retired_id,
                        target=target,
                        status=glyph,
                        path=note.path,
                        line=note.line,
                    )
                )
    return out


def _print_findings(found: list[Offender]) -> None:
    print(f"ADR-003 -- retirement notes pointing at a delivered capability ({len(found)}):\n")
    for o in found:
        if o.target == NO_TARGET:
            where = "the note names no capability at all"
        elif o.status == UNKNOWN:
            where = "not in the capability matrix"
        else:
            where = f"is {o.status}"
        print(f"  {o.path}:{o.line}  {o.retired_id} -> {o.target} ({where})")
    print(
        "\nA retirement is valid only while EVERY capability it names is unbuilt. A delivered "
        "target cannot accept the scope: finished-stories-immutable forbids adding an FR to a "
        "closed story, so the scope lands nowhere and no gate can see it.\n"
        "The fix is a NEW ticket that owns the seam FR and writes its integration/e2e test first "
        "-- red because the wiring does not exist -- not a looser check and not an edit to the "
        "delivered story. See the 2026-08-16 addendum to ADR-003."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(REPO_ROOT), help="repository root to judge")
    ap.add_argument("--list", action="store_true", help="print every note and its targets")
    args = ap.parse_args(argv)

    roadmap = Path(args.root) / "docs" / "roadmap"
    if not (roadmap / MATRIX).is_file():
        print(f"could not run: capability matrix not found under {roadmap}", file=sys.stderr)
        return 2

    if args.list:
        for note in retirement_notes(roadmap):
            targets = ", ".join(note.targets) or "(none)"
            print(f"  {note.path}:{note.line}  {note.retired_id} -> {targets}")
        return 0

    found = offenders(roadmap)
    if found:
        _print_findings(found)
        return 1

    total = len(retirement_notes(roadmap))
    print(f"ADR-003: {total} retirement note(s), every target still unbuilt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
