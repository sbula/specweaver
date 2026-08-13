# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""One citation grammar, shared by the FR and NFR sweeps. `TECH-017` finding 6.

Before this module a citation was "the file names the story somewhere, and `FR-N` appears
somewhere" — two independent greps over the whole file. Three failure modes came out of that on
2026-08-13, all real:

* **False credit.** A docstring saying *"FR-1, FR-6 and FR-7 are deliberately NOT proven here"*
  marked all three covered. The sweep fell by 3 because a test admitted a gap.
* **Misplacement.** A citation written into the first `\"\"\"` of a file lands in a fixture's
  docstring when the module has none, and still counts.
* **Invisible proof.** `\"\"\"FR-7: Transition to ARCHIVED...\"\"\"` in a file that never names its
  capability is a real attribution the ledger cannot see.

The strict grammar fixes the first two by construction: only `Proves: <ID> FR-N` in the **module**
docstring is authoritative, so prose and fixture data can never credit anything. It does **not** fix
the third — a tag carries its own id, so it was never invisible. What fixes the third is finding the
unattributed attributions and giving them an owner, which `unattributed_requirements` exists to do.

Legacy loose mentions still count. With 26 of 719 test files carrying a tag, making the strict form
mandatory today would drop hundreds of credits and spike both ratchets: pain with no quality gain.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]

_KNOWN = frozenset({"B-INTL-09", "D-INTL-06", "TECH-017"})


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_citations.py"
    assert path.exists(), f"module not found: {path}"
    spec = importlib.util.spec_from_file_location("_citations", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_citations"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cit() -> ModuleType:
    return _load()


class TestStrictCitations:
    """`strict_citations` — the authoritative form, and only in the module docstring."""

    def test_a_module_docstring_tag_cites(self, cit: ModuleType) -> None:
        text = '"""Tests for the hydrator.\n\nProves: D-INTL-06 FR-4, FR-5.\n"""\n'
        assert cit.strict_citations(text) == {"D-INTL-06": {"FR-4", "FR-5"}}

    def test_it_reads_nfrs_too(self, cit: ModuleType) -> None:
        text = '"""T.\n\nProves: B-INTL-09 NFR-2, FR-3.\n"""\n'
        assert cit.strict_citations(text) == {"B-INTL-09": {"NFR-2", "FR-3"}}

    def test_two_tags_for_two_stories_are_both_read(self, cit: ModuleType) -> None:
        text = '"""T.\n\nProves: D-INTL-06 FR-4.\n\nProves: B-INTL-09 FR-2.\n"""\n'
        assert cit.strict_citations(text) == {"D-INTL-06": {"FR-4"}, "B-INTL-09": {"FR-2"}}

    def test_a_tag_below_the_module_docstring_does_not_cite(self, cit: ModuleType) -> None:
        """The misplacement failure: a tag in a fixture's docstring is not the module's claim."""
        text = 'import pytest\n\n\ndef fixture():\n    """Proves: D-INTL-06 FR-4."""\n'
        assert cit.strict_citations(text) == {}

    def test_prose_naming_requirements_never_cites(self, cit: ModuleType) -> None:
        """The false-credit failure, verbatim from the docstring that caused it."""
        text = '"""T.\n\nFR-1, FR-6 and FR-7 are deliberately NOT proven here. D-INTL-06.\n"""\n'
        assert cit.strict_citations(text) == {}

    def test_a_file_that_cannot_be_parsed_yields_nothing(self, cit: ModuleType) -> None:
        assert cit.strict_citations("def (((\n") == {}


class TestLooseMentions:
    """`loose_mentions` — the legacy credit, preserved so nothing regresses."""

    def test_it_credits_a_mention_when_the_file_names_the_story(self, cit: ModuleType) -> None:
        assert cit.loose_mentions("D-INTL-06 and FR-4 somewhere", "D-INTL-06") == {"FR-4"}

    def test_it_credits_nothing_when_the_file_omits_the_story(self, cit: ModuleType) -> None:
        assert cit.loose_mentions("FR-4 somewhere", "D-INTL-06") == set()


class TestUnattributedRequirements:
    """`unattributed_requirements` — the invisible-proof detector, which strictness cannot supply."""

    def test_a_requirement_named_with_no_owner_is_reported(self, cit: ModuleType) -> None:
        text = '"""FR-7: Transition to ARCHIVED sets handover_context = None."""\n'
        assert cit.unattributed_requirements(text, _KNOWN) == {"FR-7"}

    def test_a_tagged_file_reports_nothing(self, cit: ModuleType) -> None:
        text = '"""T.\n\nProves: B-INTL-09 FR-7.\n"""\n'
        assert cit.unattributed_requirements(text, _KNOWN) == set()

    def test_a_file_naming_any_story_reports_nothing(self, cit: ModuleType) -> None:
        """It already has an owner the loose rule can find; it is not invisible."""
        text = '"""Covers B-INTL-09 FR-7 loosely."""\n'
        assert cit.unattributed_requirements(text, _KNOWN) == set()

    def test_fixture_data_is_not_mistaken_for_proof(self, cit: ModuleType) -> None:
        """`test_c09_traceability.py` writes requirement ids as INPUT to the thing under test."""
        text = 'spec.write_text("Hello FR-1 and NFR-2")\n'
        assert cit.unattributed_requirements(text, _KNOWN) == set()

    def test_a_round_trip_case_number_is_not_an_owner(self, cit: ModuleType) -> None:
        """Regression: `RT-3` looks like a registry id and is not one.

        A shape-based owner check excused `test_memory_repository_core.py` -- the exact file whose
        `FR-7` docstring is why this detector exists -- because it numbers round-trip cases `RT-3`,
        `RT-8`, `RT-23`. Only the real registry decides.
        """
        text = '"""RT-3: round trip.\n\nFR-7: ARCHIVED clears handover_context.\n"""\n'
        assert cit.unattributed_requirements(text, _KNOWN) == {"FR-7"}


class TestCreditedRequirements:
    """`credited_requirements` — a tagged file's tag is the whole of its claim for that story.

    This exists because the same mistake was made three times in one day, twice after the rule
    against it had been written down. A file explaining *"NFR-2 is deliberately NOT claimed here"*
    credited NFR-2, because the legacy rule reads any id in a file that names the story. The third
    time it hid a real defect: `E-EXEC-01` NFR-2 requires `< 5ms` and its only test asserts
    `< 200ms`, and the requirement read as proven.

    Documentation did not stop it, so the grammar does. Once an author demonstrates they know the
    tag syntax, prose in that file stops being evidence — for that story only. Untagged files keep
    the legacy behaviour untouched.
    """

    def test_a_tag_excludes_requirements_mentioned_only_in_prose(self, cit: ModuleType) -> None:
        text = '"""T.\n\nProves: E-EXEC-01 FR-7.\n\nNFR-2 is deliberately NOT claimed here.\n"""\n'
        assert cit.credited_requirements(text, "E-EXEC-01") == {"FR-7"}

    def test_an_untagged_file_keeps_the_legacy_credit(self, cit: ModuleType) -> None:
        assert cit.credited_requirements("E-EXEC-01 and NFR-2 in prose", "E-EXEC-01") == {"NFR-2"}

    def test_a_tag_for_another_story_does_not_gag_this_one(self, cit: ModuleType) -> None:
        """Exhaustive per story, not per file — a file may tag one capability and legacy-cite another."""
        text = '"""T.\n\nProves: D-INTL-06 FR-4.\n\nB-INTL-09 NFR-2 discussed.\n"""\n'
        # D-INTL-06 is tagged, so its claim is exactly the tag.
        assert cit.credited_requirements(text, "D-INTL-06") == {"FR-4"}
        # B-INTL-09 is not tagged here, so it keeps the legacy credit -- which is deliberately
        # permissive and returns every id in the file, exactly as it did before tags existed.
        assert "NFR-2" in cit.credited_requirements(text, "B-INTL-09")

    def test_a_file_not_naming_the_story_credits_nothing(self, cit: ModuleType) -> None:
        assert cit.credited_requirements("FR-4 alone", "D-INTL-06") == set()


class TestCreditedRequirementsAmbiguity:
    """A bare requirement id in a file naming SEVERAL stories attributes to none of them.

    Requirement ids are only unique WITHIN a story: nine designs declare an `FR-5`. The legacy rule
    credited a bare `FR-5` to every story the file happened to name, which is not a heuristic that
    is sometimes wrong — it is wrong for all but at most one of them, by construction.

    Measured 2026-08-13 across the delivered tree: 37 of 152 credited requirements rested on a bare
    id in a multi-story file. Spot-checks showed the damage plainly — `B-EXEC-01` FR-5 is the
    container executor's exit-code contract, and its credit came from
    `test_headless_run_keeps_provider_none` (*"no TTY -> provider stays None"*), a test about
    interactive drafting that shares only the token `FR-5`.

    So ambiguity yields no credit. The author fixes it by qualifying the mention (`B-EXEC-01 FR-5`)
    or adding a tag — both cheap, both make the claim checkable.
    """

    ONE = frozenset({"B-EXEC-01"})
    TWO = frozenset({"B-EXEC-01", "INT-US-09"})

    def test_a_bare_id_credits_when_only_one_story_is_named(self, cit: ModuleType) -> None:
        text = "B-EXEC-01 behaviour, see FR-5."
        assert cit.credited_requirements(text, "B-EXEC-01", self.ONE) == {"FR-5"}

    def test_a_bare_id_credits_nothing_when_two_stories_are_named(self, cit: ModuleType) -> None:
        # The real shape: both ids in a module header, the requirement named far below in a test.
        text = "Covers B-EXEC-01 and INT-US-09.\n\n" + "x\n" * 20 + "FR-5 is asserted here."
        assert cit.credited_requirements(text, "B-EXEC-01", self.TWO) == set()
        assert cit.credited_requirements(text, "INT-US-09", self.TWO) == set()

    def test_a_qualified_id_still_credits_in_a_multi_story_file(self, cit: ModuleType) -> None:
        text = "Covers INT-US-09 too.\n\nB-EXEC-01 FR-5 is asserted."
        assert cit.credited_requirements(text, "B-EXEC-01", self.TWO) == {"FR-5"}
        assert cit.credited_requirements(text, "INT-US-09", self.TWO) == set()

    def test_a_tag_beats_ambiguity(self, cit: ModuleType) -> None:
        text = '"""T.\n\nProves: B-EXEC-01 FR-5.\n\nINT-US-09 also discussed.\n"""\n'
        assert cit.credited_requirements(text, "B-EXEC-01", self.TWO) == {"FR-5"}

    def test_omitting_the_registry_keeps_the_legacy_behaviour(self, cit: ModuleType) -> None:
        """Back-compatible default: callers that pass no registry cannot detect ambiguity."""
        text = "Covers B-EXEC-01 and INT-US-09.\n\n" + "x\n" * 20 + "FR-5 is asserted here."
        assert cit.credited_requirements(text, "B-EXEC-01") == {"FR-5"}
