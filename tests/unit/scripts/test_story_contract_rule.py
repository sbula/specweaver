# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The (sub)story integration rule is present in every skill that has to act on it.

Proves: TECH-060 FR-6

`ADR-005` splits one rule across four skills, and a rule written in only three of them is a rule
that fires only when the agent happens to enter through the right door. That is not hypothetical:
during this session's own work every broken rule was already written down somewhere, and the break
came from reading a different document.

`check_skill_references.py` already proves a skill's *references* resolve, and `check_skill_sync.py`
that the two trees agree. Neither asks whether a specific rule is present at all — so a rule silently
deleted from one skill looks identical to a clean tree, which is `TECH-019`'s finding.

Deliberately narrow: each assertion pins the **load-bearing clause**, not prose. A skill may be
rewritten freely as long as the obligation survives; these fail only when the obligation itself goes.

Each clause is also chosen to be **unbreakable by line wrapping**. A first draft pinned
`"must** be named"`, which the skill renders across two lines, so the test failed on formatting
rather than on substance — a brittle assertion is a rule that will be deleted the first time it cries
wolf.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TREES = (".claude", ".agents")

#: skill -> the clauses that skill is responsible for carrying.
#:
#: `ADR-005` retired the `INT-US` family, so the clauses that used to name a separate contract now
#: name the (sub)story. The pins moved with them; the obligation is unchanged in substance — a path
#: nobody can walk with one feature is still written down, still proven red first.
OBLIGATIONS: dict[str, tuple[str, ...]] = {
    "specweaver-feature": (
        "path list",  # the artifact this skill owns
        "may not go green",  # a (sub)story does not close on a compiling feature
        "span",  # ownership decided by span
    ),
    "specweaver-design": (
        "must list its paths",  # the trigger, as a hard stop
        "crosses features",  # only crossing paths become seam FRs
    ),
    "specweaver-implementation-plan": (
        "path list",  # schedule from it
        "interface it exercises first exists",  # interface, not implementation
    ),
    "specweaver-dev": (
        "xfail(strict=True",  # the marker that lets a test go red today
        "blocked on <CAPABILITY-ID>",  # the blocker is contract, not convention
    ),
}


def _skill_text(tree: str, skill: str) -> str:
    path = REPO_ROOT / tree / "skills" / skill / "SKILL.md"
    assert path.is_file(), f"skill not found: {path}"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("tree", TREES)
@pytest.mark.parametrize(("skill", "clauses"), sorted(OBLIGATIONS.items()))
def test_the_skill_carries_its_clauses(tree: str, skill: str, clauses: tuple[str, ...]) -> None:
    text = _skill_text(tree, skill)
    missing = [clause for clause in clauses if clause not in text]
    assert missing == [], f"{tree}/{skill} no longer states: {missing}"


@pytest.mark.parametrize("tree", TREES)
def test_every_skill_names_the_deciding_adr(tree: str) -> None:
    """A clause with no authority behind it gets argued with; `ADR-005` is the authority."""
    for skill in OBLIGATIONS:
        assert "ADR-005" in _skill_text(tree, skill), f"{tree}/{skill} does not cite ADR-005"


def test_the_no_green_rule_names_its_enforcing_gate() -> None:
    """Discipline-only clauses regrow the defect; the skill must point at what actually blocks."""
    text = _skill_text(".claude", "specweaver-feature")
    assert "check_delivered_claims.py" in text


def test_the_marker_rule_names_its_enforcing_gate() -> None:
    text = _skill_text(".claude", "specweaver-dev")
    assert "check_xfail_blockers.py" in text


@pytest.mark.parametrize("tree", TREES)
def test_no_skill_still_tells_anyone_to_mint_an_int_us(tree: str) -> None:
    """`ADR-005` retired the family, and a skill that still offers the shape will see it minted.

    Narrow on purpose: this forbids the *instruction*, not the identifier. A skill may still cite
    `INT-US-21` as the incident it learned from — deleting that would falsify the record — so only
    the minting and referencing verbs are pinned.
    """
    forbidden = ("mint an `INT-US", "mint a new `INT-US", "carries a contract — its `INT-US")
    for skill in OBLIGATIONS:
        text = _skill_text(tree, skill)
        offending = [phrase for phrase in forbidden if phrase in text]
        assert offending == [], f"{tree}/{skill} still instructs: {offending}"
