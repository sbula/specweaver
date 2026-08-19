# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The integration-migration registry says what `ADR-004` requires it to say.

Proves: TECH-060 FR-2, TECH-060 FR-3

The 27 migration entries are the work list for `ADR-004`'s backlog. A section that quietly loses rows,
or a delivery claim that quietly comes back, is the failure this whole ticket exists to stop — so the
registry facts are pinned rather than trusted to a reader.

Deliberately about **shape and specific claims**, not wording: the row count, the identifiers that
must exist, and the three checkboxes that must stay open. The section can be rewritten freely.

These are also the only assertions standing behind FR-2 and FR-3. Without them the FR sweep counts
both as uncited, which is honest: a registry change nothing reads is a change nothing protects.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ROADMAP = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"
LEDGER = (
    REPO_ROOT
    / "docs"
    / "roadmap"
    / "features"
    / "topic_07_technical_debt"
    / "TECH-060"
    / "TECH-060_delivery.md"
)

#: A migration row in the `## 🚚 Integration Migration` table, in ANY of its three states.
#:
#: A first draft matched `` `[ ]` `` only, so discharging the first entry to `✅` dropped the count
#: from 27 to 26 and failed this file. The registry holds 27 entries whose STATE varies; the section
#: is deleted once, when they are all discharged, not row by row.
#:
#: `🔵` (on hold) joined `[ ]` and `✅` when `INT-US-09-SF01-MIG` was held: its proof needs container
#: execution actually exercised, which `TECH-031` owns. Held is not open — an open row invites someone
#: to pick it up, and this one cannot be finished until a prerequisite lands.
_MIG_ROW = re.compile(r"^\|[^|]*\|\s*`(?:\[ \]|✅|🔵)`\s*`(INT-US-[\w-]+-MIG)`\s*\|", re.M)

#: A held row, which must name what it waits on rather than simply stalling.
_HELD_ROW = re.compile(r"^\|[^|]*\|\s*`🔵`\s*`(INT-US-[\w-]+-MIG)`\s*\|(.*)$", re.M)

#: The contract ids `TECH-060` FR-2 minted, which had no roadmap line before it.
MINTED_CONTRACTS = (
    "INT-US-10-SF01",
    "INT-US-11-SF01",
    "INT-US-15-SF01",
    "INT-US-19-SF01",
    "INT-US-25-SF01",
)

#: `TECH-060` FR-3 — marked delivered while citing no test file, so reopened.
REOPENED = ("INT-US-05-SF03", "INT-US-05-SF04", "INT-US-21-SUB")

#: Which contract document holds each reopened id's `ADR-004` section.
CONTRACTS = Path("docs") / "roadmap" / "stories"

#: A path to a real test file, which is the evidence FR-3 requires behind a `✅`.
_TEST_CITATION = re.compile(r"`?tests/[\w./-]+\.py`?")


@pytest.fixture(scope="module")
def roadmap() -> str:
    return ROADMAP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ledger() -> str:
    return LEDGER.read_text(encoding="utf-8")


# Module-level rather than grouped in classes: R6 in `check_conventions.py` requires a unit test
# class to name the class or function it exercises, and these assert a *document*. There is no unit
# to name, so inventing a class name to satisfy the rule would be the gaming the rule exists to stop.


def test_the_migration_section_exists(roadmap: str) -> None:
    assert "## 🚚 Integration Migration" in roadmap


def test_the_ledger_holds_every_migration_entry(ledger: str) -> None:
    """27, not 26 — the count was corrected by generating the roster instead of tallying it.

    Entries, not open entries: a discharged migration stays listed until the whole batch is done.
    """
    assert len(_MIG_ROW.findall(ledger)) == 27


def test_every_migration_id_is_unique(ledger: str) -> None:
    rows = _MIG_ROW.findall(ledger)
    assert len(set(rows)) == len(rows)


def test_the_ledger_is_the_only_home_for_them(ledger: str) -> None:
    """Scattering the entries into their stories means 27 placement edits in and 27 out.

    Misfiled registry insertions wrecked three commits on 2026-08-16, which is why they live in one
    table instead of under 21 story headings.
    """
    section = ledger.split("## The `-MIG` ledger", 1)[1].split("\n## ", 1)[0]
    assert len(_MIG_ROW.findall(section)) == 27


def test_the_roadmap_quotes_only_the_rows_still_open(roadmap: str) -> None:
    """A discharged row is a record of work done, and the roadmap carries open state.

    All 27 sat on the roadmap while the batch was the active work list. What stays is the ledger's
    open remainder, so the section shrinks as rows discharge and disappears when none are left.
    """
    rows = _MIG_ROW.findall(roadmap)
    assert rows, "the roadmap has stopped naming the open migrations"
    for row in rows:
        line = next(ln for ln in roadmap.splitlines() if f"`{row}`" in ln)
        assert "`✅`" not in line, f"{row} is discharged and belongs in the ledger, not the roadmap"


@pytest.mark.parametrize("contract", MINTED_CONTRACTS)
def test_each_minted_contract_has_a_line(roadmap: str, contract: str) -> None:
    assert f"**{contract}:**" in roadmap


@pytest.mark.parametrize("contract", REOPENED)
def test_a_reopened_claim_is_green_only_behind_a_named_test(roadmap: str, contract: str) -> None:
    """FR-3 — a `✅` citing no test file is not a delivery.

    The rule is one-directional, and the first draft got that wrong: it required `` `[ ]` `` outright,
    which no amount of proof could ever discharge. `INT-US-05-SF03` then earned its `✅` by an e2e
    naming a three-language monorepo, and the guard fired on the delivery it was written to permit.

    Citing a test is necessary, not sufficient — `INT-US-05-SF04` cites one and stays open, because
    half of its path is a defect (`TECH-065`). What is pinned here is only that a green claim cannot
    be unevidenced.
    """
    line = next(ln for ln in roadmap.splitlines() if f"**{contract}:**" in ln)
    if "`✅`" not in line:
        return
    story = contract.split("-SF")[0].replace("INT-US-", "US-").replace("-SUB", "")
    doc = (REPO_ROOT / CONTRACTS / f"{story}.md").read_text(encoding="utf-8")
    # `ADR-005` removed the id from the story document, so the roadmap line's title is the key.
    name = line.split(f"**{contract}:**", 1)[1].strip()
    assert f"**{name}" in doc, f"{contract}: no section named {name!r} in {story}.md"
    section = doc.split(f"**{name}", 1)[-1].split("\n* **", 1)[0]
    assert _TEST_CITATION.search(section), f"{contract} claims `✅` and its story names no test"


@pytest.mark.parametrize("contract", REOPENED)
def test_a_reopened_claim_carries_a_real_name(roadmap: str, contract: str) -> None:
    """Two of them read "Sub-Story Integration (Complete)" — a label, not a subject."""
    line = next(ln for ln in roadmap.splitlines() if f"**{contract}:**" in ln)
    assert "Sub-Story Integration (Complete)" not in line


def test_a_held_migration_names_what_it_waits_on(roadmap: str) -> None:
    """`🔵` is a claim that the work cannot proceed, so it must say why.

    A held row with no named blocker is indistinguishable from an abandoned one, and the whole point of
    the migration registry is that nothing stalls invisibly.
    """
    held = _HELD_ROW.findall(roadmap)
    for mig, rest in held:
        assert "TECH-" in rest or "C-" in rest or "E-" in rest, (
            f"{mig} is held without naming a blocker: {rest.strip()}"
        )


def test_the_held_container_migration_is_recorded(roadmap: str) -> None:
    """`INT-US-09-SF01-MIG` waits on `B-EXEC-01`'s FRs being cited against the container path.

    Pinned explicitly because it is the first entry to be held rather than discharged, and a hold
    that quietly becomes a discharge would be the registry lying about proof that does not exist.

    **The hold outlived its original blocker.** It was held on container execution being genuinely
    exercised, which `TECH-031` delivered — the executor now runs four toolchains against live
    podman. What it was really waiting for is the proof, and `check_fr_coverage.py B-EXEC-01` still
    exits 1 with all nine FRs uncited. So the row stays held and now names the citation, which is
    what the hold was always about.
    """
    held = dict(_HELD_ROW.findall(roadmap))
    assert "INT-US-09-SF01-MIG" in held, "the container migration is no longer held"
    assert "B-EXEC-01" in held["INT-US-09-SF01-MIG"]
