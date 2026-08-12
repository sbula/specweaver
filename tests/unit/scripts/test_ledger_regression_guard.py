# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every ledger recorded as closed is still closed, and no story has an orphaned requirement.

Three ledgers were closed by hand and nothing stopped them reopening. A citation is a line in a
docstring: deleting the test that carries it silently reopens the ledger it closed, and the next
person to run the gate discovers it months later.

**Why the story ids live in data rather than here.** The citation scan credits a story every
requirement id in any file under `tests/` that names it. Listing the closed stories as literals in
this module would hand each of them *this module's* requirement tokens — the exact defect the ticket
this guard belongs to exists to remove. They are read from
`scripts/baselines/fr_traceability_closed.txt` at run time, so this file names one story and no
other, which `test_this_module_names_one_story_only` pins.

Proves: TECH-025 FR-1.
Proves: TECH-025 FR-2.
Proves: TECH-025 FR-3.
Proves: TECH-025 FR-4.
Proves: TECH-025 FR-5.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "scripts" / "baselines" / "fr_traceability_closed.txt"
FEATURES_ROOT = REPO_ROOT / "docs" / "roadmap" / "features"


#: Requirement ids are assembled rather than written out. A literal one outside the tags above
#: would be counted by the very scan this module is careful about.
def _token(n: int) -> str:
    return f"FR-{n}"


def _load_gate() -> ModuleType:
    """Import `check_fr_coverage` by path — `scripts/` is not an importable package."""
    path = REPO_ROOT / "scripts" / "check_fr_coverage.py"
    spec = importlib.util.spec_from_file_location("check_fr_coverage", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_fr_coverage"] = module
    spec.loader.exec_module(module)
    return module


def read_manifest(path: Path) -> list[str]:
    """Story ids listed in `path`, ignoring blanks and `#` comments.

    A missing manifest raises with the path named. The alternative — returning `[]` — would turn
    every assertion below into a loop over nothing, which is how a guard becomes an ornament.
    """
    if not path.is_file():
        msg = f"ledger manifest not found: {path}"
        raise FileNotFoundError(msg)
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            entries.append(line)
    return entries


# ---------------------------------------------------------------------------
# The guard that stops the loop below passing over an empty list
# ---------------------------------------------------------------------------


def test_the_manifest_lists_stories() -> None:
    """An empty manifest would make every assertion below iterate over nothing and pass.

    Absence is what a missing or emptied file returns, so the count is asserted before it is used.
    """
    entries = read_manifest(MANIFEST)

    assert entries, "manifest is empty — the guard below would assert nothing"
    assert len(entries) >= 4, f"expected at least the four seeded ids, found {entries}"
    assert all(re.fullmatch(r"[A-Z][A-Z0-9-]*-\d+", e) for e in entries), entries


# ---------------------------------------------------------------------------
# The live guarantees
# ---------------------------------------------------------------------------


def test_every_recorded_ledger_is_still_closed() -> None:
    """Each story in the manifest still passes its own FR-traceability gate.

    Run in-process: the gate's `main` returns an int and only `__main__` calls `sys.exit`, so this
    needs no subprocess and cannot fail for the environmental reasons a shell-out can.
    """
    gate = _load_gate()

    reopened = [story for story in read_manifest(MANIFEST) if gate.main([story]) != 0]

    assert reopened == [], f"ledger(s) reopened: {reopened}"


def test_no_recorded_story_has_an_orphaned_requirement() -> None:
    """Every requirement a design declares is assigned to one of its sub-features.

    A requirement that belongs to no sub-feature is delivered by nobody and reviewed by nobody, and
    the coverage gate cannot see the gap because it only asks whether *something* cites it.

    Stated generally rather than about one story, which is what lets it be asserted at all: the ids
    come from the manifest, so this file names none of them.
    """
    gate = _load_gate()
    orphans: dict[str, list[str]] = {}

    for story in read_manifest(MANIFEST):
        design = gate.find_design_doc(FEATURES_ROOT, story)
        assert design is not None, f"no design document for {story}"
        text = design.read_text(encoding="utf-8")

        declared = set(gate.parse_design_frs(text))
        assigned: set[str] = set()
        for row in re.findall(r"^- \*\*FRs\*\*: \[([^\]]*)\]", text, re.M):
            assigned |= set(re.findall(r"FR-\d+", row))

        missing = sorted(declared - assigned, key=lambda x: int(x.split("-")[1]))
        if missing:
            orphans[story] = missing

    assert orphans == {}, f"requirements assigned to no sub-feature: {orphans}"


# ---------------------------------------------------------------------------
# Synthetic probes — these prove the LOGIC and read no real manifest
# ---------------------------------------------------------------------------


def test_comments_and_blank_lines_are_ignored(tmp_path: Path) -> None:
    """Boundary: a commented id must not be read as a story, or a reviewer cannot park one."""
    path = tmp_path / "manifest.txt"
    path.write_text("# a heading\n\nSAMPLE-1\n\n# SAMPLE-9 parked\nSAMPLE-2  # trailing\n")

    assert read_manifest(path) == ["SAMPLE-1", "SAMPLE-2"]


def test_a_missing_manifest_names_the_path(tmp_path: Path) -> None:
    """Degradation: the failure says which file is missing rather than returning an empty list."""
    with pytest.raises(FileNotFoundError, match=r"ledger manifest not found"):
        read_manifest(tmp_path / "absent.txt")


def test_the_gate_can_fail(tmp_path: Path) -> None:
    """Hostile: the guard above asserts `!= 0` never happens — so prove the gate CAN return non-zero.

    Without this the loop could be comparing `0 == 0` against a gate that always succeeds, and the
    guard would be the vacuous proof it exists to prevent. A story id with no design document is the
    cheapest genuine failure, and it uses a synthetic id so no real ledger is touched.
    """
    gate = _load_gate()

    assert gate.main(["SAMPLE-404"]) != 0


# ---------------------------------------------------------------------------
# This module guards its own citation footprint
# ---------------------------------------------------------------------------


def test_this_module_names_one_story_only() -> None:
    """The whole design of this file rests on it naming no story but its own.

    If a later contributor writes a real story id into a comment here — explaining which ledgers are
    covered, say — that story silently gains all five requirement tokens above.
    """
    source = Path(__file__).read_text(encoding="utf-8")

    tokens = re.findall(r"FR-\d+", source)
    assert sorted(set(tokens)) == [_token(n) for n in (1, 2, 3, 4, 5)], f"unexpected: {tokens}"

    stories = set(re.findall(r"\b(?:TECH|INT-US)-\d+\b", source))
    assert stories == {"TECH-025"}, f"this file must name one story only, found: {stories}"
