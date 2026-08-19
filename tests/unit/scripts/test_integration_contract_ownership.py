# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A path row is owned by one ticket, and the contract is not a second place to track another's work.

`ADR-003` puts a seam on the capability that creates it: while the consumer is unbuilt, the consumer
declares the FR and nothing is minted elsewhere. A path row that says the *contract* owns it while
its blocker names a capability or a `TECH` ticket contradicts that — the work has an owner, and the
row is a duplicate of it.

Measured before this rule existed: of 36 open path rows across the 28 contracts, **31 named another
ticket as their blocker**. Five contracts read `⬜ Pending` with nothing of their own left to do, and
the registry showed the same work in two places, so a reader could not tell what was outstanding
from what was merely restated.

The rule is one-directional. A row the contract genuinely owns is legitimate and expected — that is
what an integration contract is for — provided nobody else owns the thing it waits on. So the five
survivors all read "needs a product decision" or "needs a scope decision": no ticket can be handed a
decision.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = REPO_ROOT / "docs" / "roadmap" / "topics" / "topic_08_integration"

#: A six-column path-inventory row, `| P-1 | ... |`, at any indentation.
_ROW = re.compile(r"^\s*\|\s*P-\d+\s*\|")

#: A row whose Owner column claims the contract itself, in either phrasing in use.
_SELF_OWNED = re.compile(r"this contract", re.I)

#: Another ticket: a capability id or a technical-debt id. Both can own an FR; a contract row
#: waiting on either is waiting on work that already has a home.
_OTHER_TICKET = re.compile(r"\b(?:[A-E]-[A-Z]+-\d+|TECH-\d{3})\b")


def _rows() -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for path in sorted(CONTRACTS.glob("US-*_integration.md")):
        story = path.stem.split("_")[0]
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not _ROW.match(stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) == 6:
                out.append((story, cells))
    return out


@pytest.fixture(scope="module")
def rows() -> list[tuple[str, list[str]]]:
    found = _rows()
    assert found, "no path-inventory rows found — the parser has stopped matching the tables"
    return found


def test_a_self_owned_row_waits_on_nobody_else(rows: list[tuple[str, list[str]]]) -> None:
    """The duplicate this rule removes: the contract claims a row another ticket already owns."""
    duplicated = [
        f"{story} {cells[0]} — owned by the contract, blocked on "
        f"{', '.join(sorted(set(_OTHER_TICKET.findall(cells[5]))))}"
        for story, cells in rows
        if _SELF_OWNED.search(cells[3]) and _OTHER_TICKET.search(cells[5])
    ]
    assert not duplicated, "path rows tracked twice:\n  " + "\n  ".join(duplicated)


def test_a_retired_row_names_the_ticket_that_took_it(rows: list[tuple[str, list[str]]]) -> None:
    """`retired` and `moved` are claims that someone else owns it, so someone else must be named.

    A row retired to nobody is the unfalsifiable prose `ADR-003` was written to delete — it reads as
    a disposition and discharges no obligation.
    """
    unnamed = [
        f"{story} {cells[0]} ({cells[4]})"
        for story, cells in rows
        if cells[4].lower().startswith(("retired", "moved")) and not _OTHER_TICKET.search(cells[5])
    ]
    assert not unnamed, "retired with no owner named:\n  " + "\n  ".join(unnamed)
