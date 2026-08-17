# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The (sub)story-contract rule is present in every skill that has to act on it.

Proves: TECH-060 FR-6

`ADR-004` splits one rule across four skills, and a rule written in only three of them is a rule
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
OBLIGATIONS: dict[str, tuple[str, ...]] = {
    "specweaver-feature": (
        "path inventory",  # the artifact this skill owns
        "may not go green",  # ADR-004 clause 5
        "span",  # clause 3: ownership decided by span
    ),
    "specweaver-design": (
        "contract must exist",  # the trigger, as a hard stop
        "cross a feature boundary",  # only cross-feature paths belong there
    ),
    "specweaver-implementation-plan": (
        "path inventory",  # schedule from it
        "interface it exercises first exists",  # clause 4: interface, not implementation
    ),
    "specweaver-dev": (
        "xfail(strict=True",  # clause 4's marker
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
    """A clause with no authority behind it gets argued with; `ADR-004` is the authority."""
    for skill in OBLIGATIONS:
        assert "ADR-004" in _skill_text(tree, skill), f"{tree}/{skill} does not cite ADR-004"


def test_the_no_green_rule_names_its_enforcing_gate() -> None:
    """Discipline-only clauses regrow the defect; the skill must point at what actually blocks."""
    text = _skill_text(".claude", "specweaver-feature")
    assert "check_delivered_claims.py" in text


def test_the_marker_rule_names_its_enforcing_gate() -> None:
    text = _skill_text(".claude", "specweaver-dev")
    assert "check_xfail_blockers.py" in text
