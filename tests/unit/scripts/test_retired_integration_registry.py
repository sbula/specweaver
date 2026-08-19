# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The retired integration registry stays retired, and its record stays readable.

Proves: TECH-060 FR-2, TECH-060 FR-3

`TECH-060` migrated 27 integration claims into the structure `ADR-004` defined, and `ADR-005` then
retired the structure itself: integration is implicit in the (sub)story, and no `INT-US` identifier
is ever minted again. Two things therefore need pinning, and they pull in opposite directions.

**The record must survive.** The 27 migrations are the log of work done, kept in `TECH-060`'s
delivery record. A log that quietly loses rows is the failure the ticket existed to stop.

**The registry must not come back.** Every previous attempt to retire this family left it one
member and the family regrew: `ADR-003` kept the closed-feature case, `ADR-004` reopened a
`CLOSED EMPTY`, and both times the roadmap ended up with a second place to make claims that no gate
compared against code. So the absence of the entry lines is asserted, not assumed.

Deliberately about **shape and specific claims**, not wording. The documents may be rewritten freely.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ROADMAP = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"
STORIES = REPO_ROOT / "docs" / "roadmap" / "stories"
LEDGER = (
    REPO_ROOT
    / "docs"
    / "roadmap"
    / "features"
    / "topic_07_technical_debt"
    / "TECH-060"
    / "TECH-060_delivery.md"
)

#: A migration row in the frozen ledger, in any of the three states it ever had.
_MIG_ROW = re.compile(r"^\|[^|]*\|\s*`(?:\[ \]|✅|🔵)`\s*`(INT-US-[\w-]+-MIG)`\s*\|", re.M)

#: A roadmap ENTRY line: a checkbox and a bolded identifier. Prose that merely mentions an id is not
#: one, and the distinction is the point — the incident record cites `INT-US-24` and must keep doing
#: so, while an entry line is a registry claim and must not exist.
_ENTRY_LINE = re.compile(r"^\s*\*\s+`(?:\[ \]|✅|🔵|🟢|🟡|🔴)`\s+\*\*INT-US-", re.M)

#: `TECH-060` FR-3 — claims marked delivered while citing no test file, so reopened. `ADR-005` moved
#: their home from a roadmap line to the (sub)story document, and the claim travelled with it.
REOPENED = {
    "US-05": ("Framework Native Understanding",),
    "US-21": ("Recursive Planning",),
}

#: An entry's Status bullet inside a story document.
_ENTRY_STATUS = re.compile(r"\*\*Status:\*\*\s*(\S+)")


@pytest.fixture(scope="module")
def roadmap() -> str:
    return ROADMAP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ledger() -> str:
    return LEDGER.read_text(encoding="utf-8")


# Module-level rather than grouped in classes: R6 in `check_conventions.py` requires a unit test
# class to name the class or function it exercises, and these assert *documents*. There is no unit to
# name, so inventing a class name to satisfy the rule would be the gaming the rule exists to stop.


def test_the_ledger_holds_every_migration_entry(ledger: str) -> None:
    """27, not 26 — the count was corrected by generating the roster instead of tallying it."""
    assert len(_MIG_ROW.findall(ledger)) == 27


def test_every_migration_id_is_unique(ledger: str) -> None:
    rows = _MIG_ROW.findall(ledger)
    assert len(set(rows)) == len(rows)


def test_the_ledger_is_the_only_home_for_them(ledger: str) -> None:
    """One table, not 27 rows scattered under 21 story headings.

    Misfiled registry insertions wrecked three commits on 2026-08-16, which is why they were kept
    together — and why the record stayed together when it left the roadmap.
    """
    section = ledger.split("## The `-MIG` ledger", 1)[1].split("\n## ", 1)[0]
    assert len(_MIG_ROW.findall(section)) == 27


def test_the_roadmap_declares_no_integration_entry(roadmap: str) -> None:
    """`ADR-005`: the family is retired, so the roadmap carries no entry line for it.

    46 lines were removed on 2026-08-19. This fails if one comes back — which is how the family
    regrew the previous two times it was retired.
    """
    found = _ENTRY_LINE.findall(roadmap)
    assert found == [], f"the roadmap declares {len(found)} INT-US entry line(s) again"


def test_the_roadmap_still_names_the_incidents_it_learned_from(roadmap: str) -> None:
    """The guard above forbids the ENTRY, never the citation, and that difference is load-bearing.

    A rule enforced by deleting the evidence for it cannot be checked. `INT-US-24` is why
    `E-VAL-03`'s urgency is what it is, and the routing queue has to be able to say so.
    """
    assert "INT-US-24" in roadmap


@pytest.mark.parametrize(("story", "titles"), sorted(REOPENED.items()))
def test_a_reopened_claim_is_still_open_in_its_story(story: str, titles: tuple[str, ...]) -> None:
    """FR-3 — a `✅` citing no test file is not a delivery, and must not drift back.

    Both of these were flipped on the roadmap in 2026-08 and left `✅` in their own document for
    days: two homes for one fact, needing an edit in both. `ADR-005` removed one of the homes, and
    this asserts the surviving one tells the truth.
    """
    text = (STORIES / f"{story}.md").read_text(encoding="utf-8")
    for title in titles:
        assert f"* **{title}**" in text, f"{story}.md has no entry named {title!r}"
        block = text.split(f"* **{title}**", 1)[1].split("\n* **", 1)[0]
        status = _ENTRY_STATUS.search(block)
        assert status is not None, f"{title} declares no Status, so nothing can judge it"
        assert "✅" not in status.group(1), f"{title} claims delivery again: {status.group(1)}"
