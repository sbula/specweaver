#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Verify every FR a design declares is carried into a plan AND cited by a test.

Design documents make promises that quietly evaporate between design → plan → code. INT-US-21
inherited the canonical example: `D-INTL-02` §6.2 promised to write ``<name>_decomposition.yaml``
plus stub component specs. No implementation plan carried it, no test asserted it, and the promise
was simply lost — resurfacing months later as work for the *integration* story, which had assumed
the capability already existed.

Nothing detected that, because a dropped promise leaves no artifact behind. This script closes the
loop by treating the design's FR table as a ledger with two mandatory counterparties:

* every ``FR-N`` in the design's FR table must appear in at least one implementation plan;
* every ``FR-N`` in the design's FR table must be cited by at least one test file.

A test "cites" an FR when the file names the story (e.g. ``INT-US-21``) *and* mentions ``FR-N``.
File-level granularity is deliberate: it makes the design→proof link auditable without forcing a
``<STORY> FR-N`` tag onto every individual test function.

That granularity has one blind spot, and ``FIXTURE_DATA_MARKER`` below covers it: a test *of this
checker* names a story and feeds it ``FR-N`` strings as inputs, which is indistinguishable from a
citation. Marking such a file removes it from the scan. That is not the override this module
refuses to add — see the marker's own note for why it can only ever subtract.

Usage:
    python scripts/check_fr_coverage.py INT-US-21

Exit code 1 blocks the story. There is deliberately no override flag: an overridable gate becomes
a habit. If an FR is genuinely out of scope for this story, remove it from the design's FR table —
that is a design decision, and it should be visible as one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_ROOT = REPO_ROOT / "docs" / "roadmap" / "features"
TESTS_ROOT = REPO_ROOT / "tests"

#: An FR row in the design's Functional Requirements table: `| FR-7 | ... |`.
_FR_TABLE_ROW = re.compile(r"^\s*\|\s*\**(FR-\d+)\**\s*\|", re.MULTILINE)

#: A bare FR mention anywhere in free text. Uppercase only — `fr-1` in prose is not a citation.
_FR_MENTION = re.compile(r"(?<![\w-])(FR-\d+)(?![\w-])")

#: Story ids are used to build glob patterns; refuse anything that is not plainly an id.
_STORY_ID = re.compile(r"^[A-Z0-9-]+$")

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git"}

#: A test file declares itself fixture data with this line, and the citation scan then ignores it.
#:
#: Needed because a test *of this checker* both names a story (explaining why the checker exists)
#: and feeds requirement ids to the function under test. Under the file-level rule below, that
#: combination reads as proof: eight of ``INT-US-21``'s ten requirements were credited to a file
#: asserting nothing about it. Inflated counts hide real gaps.
#:
#: This is not the kind of override this repo refuses to add. The marker can only ever *remove*
#: citations, never grant one, so it cannot be used to make a failing ledger pass -- it makes this
#: gate stricter. Marking a file that carries a genuine ``Proves:`` tag silently discards that
#: proof, so put fixture-heavy tests and real citations in different files.
#:
#: The obvious alternative -- requiring the story id and the requirement id on the *same line* --
#: was measured and rejected: it reopens ``INT-US-24`` (two requirements) and ``TECH-019`` (two
#: more), because the ``Proves:`` convention names the story once while a file's other citations
#: sit on other lines. Do not revisit it without re-running that measurement.
FIXTURE_DATA_MARKER = "# fr-coverage: fixture-data"

#: Lines from the top of a file searched for the marker. Wide enough for the licence header plus a
#: blank line; narrow enough that prose mentioning the marker further down does not silently
#: exclude a real proof.
_MARKER_SCAN_LINES = 10


def normalize_story_id(raw: str) -> str:
    """Upper-case and validate a story id. Raises ValueError on anything glob-unsafe."""
    story = raw.strip().upper()
    if not story or not _STORY_ID.match(story):
        raise ValueError(
            f"invalid story id {raw!r}: expected characters A-Z, 0-9 and '-' only "
            "(the id is interpolated into a glob pattern)"
        )
    return story


def parse_design_frs(text: str) -> list[str]:
    """FR ids from the design's FR *table*, in document order, deduplicated.

    Only table rows count. Prose such as ``**FRs**: [FR-1, FR-2]`` in the sub-feature breakdown, or
    ``see FR-5's correction``, must not invent ledger entries — otherwise the ledger grows by
    citation and can never be satisfied.
    """
    seen: list[str] = []
    for match in _FR_TABLE_ROW.finditer(text):
        fr = match.group(1)
        if fr not in seen:
            seen.append(fr)
    return seen


def collect_frs(text: str) -> set[str]:
    """Every FR id mentioned anywhere in the given text."""
    return set(_FR_MENTION.findall(text))


def is_fixture_data(text: str) -> bool:
    """Whether a file declares its requirement ids to be fixture data rather than citations.

    Matched as a whole line at column 0. Two near-misses this deliberately rejects:
    ``# fr-coverage: fixture-database`` is a different comment, and an *indented* copy is inside
    something else — a docstring documenting the convention, a data literal. Exempting a file is a
    file-level declaration, and the failure mode of getting it wrong is silent: the gate stays
    green while a genuine proof quietly stops counting.
    """
    for line in text.splitlines()[:_MARKER_SCAN_LINES]:
        if line.rstrip() == FIXTURE_DATA_MARKER:
            return True
    return False


def _read(path: Path) -> str | None:
    """Read a text file, or None if it is unreadable/undecodable."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def find_design_doc(features_root: Path, story: str) -> Path | None:
    """The story's design document, wherever its topic directory lives."""
    matches = sorted(features_root.glob(f"*/{story}/{story}_design.md"))
    return matches[0] if matches else None


def find_plans(features_root: Path, story: str) -> list[Path]:
    """Every implementation plan belonging to the story (one per sub-feature, or a single one)."""
    return sorted(features_root.glob(f"*/{story}/{story}*implementation_plan.md"))


def cited_frs_in_tests(tests_root: Path, story: str) -> dict[str, list[str]]:
    """Map ``FR-N`` → the test files citing it for this story.

    A file counts only if it names the story, so an ``FR-2`` belonging to a different story is not
    miscredited. Undecodable files are skipped rather than aborting the sweep — one bad file must
    not be able to hide the state of the whole tree. Files marked ``FIXTURE_DATA_MARKER`` are
    skipped too: their requirement ids are inputs, not claims.
    """
    cited: dict[str, list[str]] = {}
    if not tests_root.is_dir():
        return cited
    for path in sorted(tests_root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        text = _read(path)
        if text is None or story not in text:
            continue
        # After the story check on purpose: this reads a header window, and it matters to roughly
        # one file in a thousand.
        if is_fixture_data(text):
            continue
        relative = path.relative_to(tests_root).as_posix()
        for fr in sorted(collect_frs(text)):
            cited.setdefault(fr, []).append(relative)
    return cited


def declared_frs(features_root: Path, story: str) -> tuple[list[str], str | None]:
    """The story's declared FR ledger, or ``([], reason)`` if it cannot be established."""
    design = find_design_doc(features_root, story)
    if design is None:
        return [], f"no design document found at {features_root}/*/{story}/{story}_design.md"

    text = _read(design)
    if text is None:
        return [], f"design document is unreadable: {design}"

    frs = parse_design_frs(text)
    if not frs:
        return [], (
            f"no FR rows parsed from {design.name}. Either the design has no Functional "
            "Requirements table, or its shape changed and this parser needs updating. Reporting "
            "zero FRs as full coverage would be a vacuous pass, so this blocks."
        )
    print(f"  {len(frs)} FR(s) declared in {design.name}: {', '.join(frs)}")
    return frs, None


def planned_frs(features_root: Path, story: str) -> set[str]:
    """Every FR mentioned by any of the story's implementation plans."""
    plans = find_plans(features_root, story)
    planned: set[str] = set()
    for plan in plans:
        text = _read(plan)
        if text is None:
            print(f"  WARN  implementation plan unreadable: {plan.name}")
            continue
        planned |= collect_frs(text)
    if plans:
        print(f"  {len(plans)} implementation plan(s): {', '.join(p.name for p in plans)}")
    else:
        print("  no implementation plan found")
    return planned


def print_ledger(frs: list[str], planned: set[str], cited: dict[str, list[str]]) -> None:
    """One line per FR: whether a plan owns it and how many test files cite it."""
    for fr in frs:
        in_plan = "plan" if fr in planned else "NO PLAN"
        files = cited.get(fr, [])
        proof = f"{len(files)} test file(s)" if files else "NO TEST"
        print(f"  {fr:<7} {in_plan:<8} {proof}")


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("story_id", help="e.g. INT-US-21")
    ap.add_argument("--features-root", default=str(FEATURES_ROOT), help=argparse.SUPPRESS)
    ap.add_argument("--tests-root", default=str(TESTS_ROOT), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    try:
        story = normalize_story_id(args.story_id)
    except ValueError as exc:
        print(f"FAIL  {exc}")
        return 1

    features_root = Path(args.features_root)
    print(f"FR coverage ledger: {story}\n")

    frs, error = declared_frs(features_root, story)
    if error is not None:
        print(f"FAIL  {error}")
        return 1

    planned = planned_frs(features_root, story)
    cited = cited_frs_in_tests(Path(args.tests_root), story)
    print(f"  {len(cited)} FR(s) cited by tests naming {story}\n")

    missing_from_plan = [fr for fr in frs if fr not in planned]
    missing_from_tests = [fr for fr in frs if fr not in cited]
    print_ledger(frs, planned, cited)

    print()
    if missing_from_plan:
        print(
            "FAIL  declared in the design but carried by no implementation plan: "
            + ", ".join(missing_from_plan)
        )
    if missing_from_tests:
        print(
            "FAIL  declared in the design but cited by no test file: "
            + ", ".join(missing_from_tests)
        )

    if missing_from_plan or missing_from_tests:
        print(
            f"\nBLOCKED: {story} must not be declared finished. Every FR needs a plan that owns it "
            "and a test that proves it. If an FR is genuinely out of scope, delete the row from "
            "the design's FR table so the descoping is visible."
        )
        return 1

    print(f"{story}: every declared FR is planned and cited by at least one test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
