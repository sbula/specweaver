# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a mutant taught us, and who is allowed to say a requirement is covered.

Mirrors `scripts/_mutation_verdict.py`. Split from the session tests when they crossed the size
ceiling, and the split follows the source: deciding what a run means needs no sandbox, no
subprocess and no scheduling.
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


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mutation", REPO_ROOT / "scripts" / "mutation.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mutation"] = module
    spec.loader.exec_module(module)
    return module


class TestVerdictOfVocabulary:
    """One vocabulary, naming what we learned rather than the mutant's fate.

    `KILLED`/`SURVIVED` describe what happened to the mutant, and they invert against test
    semantics: "5 killed" is the success line and "1 survived" is the alarm. Read quickly by a
    tired human at 08:00 they mean the opposite of how they sound, and this session confused them
    twice while designing the replacement.

    The three below say what the run taught us about our own code, so good news reads as good.
    Every verdict that is not `PROTECTED` is a finding and needs a human's answer --- including
    `UNMEASURED`, which used to pass the gate in two of its three forms.
    """

    def _run(self, mutation: ModuleType, **kwargs: object) -> object:
        base = {
            "derived_id": "F FR-1 m",
            "outcome": "KILL",
            "killers": ["tests/a.py::test_x"],
            "detail": "",
            "drift": "OK",
        }
        return mutation.MutantRun(**{**base, **kwargs})

    def test_an_in_scope_confirmed_kill_is_protected(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(self._run(mutation), scope=["tests/a.py"], confirmed=True)

        assert v.verdict == "PROTECTED"
        assert v.reason is None, "a clean pass has no `why`"

    def test_nothing_objecting_is_unprotected_with_a_code(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(
            self._run(mutation, outcome="NO_KILL", killers=[]), scope=["tests/a.py"]
        )

        assert (v.verdict, v.reason) == ("UNPROTECTED", "no-killer")

    def test_an_out_of_scope_killer_is_unprotected_not_protected(
        self, mutation: ModuleType
    ) -> None:
        """A bystander test dying proves something noticed, never that this requirement is
        covered."""
        v = mutation.verdict_of(
            self._run(mutation, killers=["tests/elsewhere.py::test_y"]),
            scope=["tests/a.py"],
            confirmed=True,
        )

        assert (v.verdict, v.reason) == ("UNPROTECTED", "out-of-scope-killer")

    def test_an_unconfirmed_kill_is_unmeasured(self, mutation: ModuleType) -> None:
        """The killer fails without the mutant too, so the run measured the test, not the code."""
        v = mutation.verdict_of(self._run(mutation), scope=["tests/a.py"], confirmed=False)

        assert (v.verdict, v.reason) == ("UNMEASURED", "killer-already-failing")

    def test_collecting_nothing_is_unmeasured_not_unprotected(self, mutation: ModuleType) -> None:
        """A scope naming no tests is a broken campaign, not a gap in the code."""
        v = mutation.verdict_of(
            self._run(mutation, outcome="NOTHING_RAN", killers=[]), scope=["tests/a.py"]
        )

        assert (v.verdict, v.reason) == ("UNMEASURED", "nothing-collected")

    def test_a_red_scope_is_unmeasured(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(
            self._run(mutation),
            scope=["tests/a.py"],
            baseline_failures=["tests/a.py::test_other"],
            confirmed=True,
        )

        assert (v.verdict, v.reason) == ("UNMEASURED", "scope-already-red")

    def test_a_broken_run_keeps_its_specific_reason(self, mutation: ModuleType) -> None:
        """`bad-anchor` and `timed-out` need telling apart: one is a campaign someone wrote
        wrong, the other is a test that hangs. Both are UNMEASURED and the fixes differ."""
        v = mutation.verdict_of(
            self._run(mutation, outcome="BROKEN", detail="timed out after 900s", killers=[]),
            scope=["tests/a.py"],
        )

        assert (v.verdict, v.reason) == ("UNMEASURED", "timed-out")

    def test_a_bad_anchor_is_told_apart_from_a_hang(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(
            self._run(
                mutation, outcome="BROKEN", detail="anchor appears 3 times in x.py", killers=[]
            ),
            scope=["tests/a.py"],
        )

        assert (v.verdict, v.reason) == ("UNMEASURED", "bad-anchor")

    def test_every_verdict_carries_a_human_explanation(self, mutation: ModuleType) -> None:
        """The code is for machines; a human still has to read the morning summary."""
        v = mutation.verdict_of(
            self._run(mutation, outcome="NO_KILL", killers=[]), scope=["tests/a.py"]
        )

        assert v.explanation and " " in v.explanation

    def test_only_protected_is_not_a_finding(self, mutation: ModuleType) -> None:
        """The control on the whole vocabulary: exactly one of the three is good news."""
        assert mutation.is_finding("UNPROTECTED") is True
        assert mutation.is_finding("UNMEASURED") is True
        assert mutation.is_finding("PROTECTED") is False


class TestScopeKillers:
    """Each killer says whether the campaign asked for it.

    The verdict already refuses a kill that only bystanders noticed, but it says so once, at the
    top, in prose. A reader looking at three killers cannot tell which of them the campaign
    actually named — so `out-of-scope-killer` has to be taken on trust, and a campaign whose scope
    is subtly wrong looks the same as one that is right.
    """

    def test_a_killer_the_campaign_named_is_in_scope(self, mutation: ModuleType) -> None:
        records = mutation.scope_killers(
            [{"nodeid": "tests/a.py::test_x", "message": "boom"}], scope=["tests/a.py"]
        )

        assert records == [{"nodeid": "tests/a.py::test_x", "in_scope": True, "message": "boom"}]

    def test_a_bystander_is_marked_rather_than_dropped(self, mutation: ModuleType) -> None:
        """Dropping it would hide the evidence that something noticed — which is the fact a
        human needs to fix the scope."""
        records = mutation.scope_killers(
            [{"nodeid": "tests/elsewhere.py::test_y", "message": None}], scope=["tests/a.py"]
        )

        assert records[0]["in_scope"] is False
        assert records[0]["nodeid"] == "tests/elsewhere.py::test_y"

    def test_scoping_is_by_file_not_by_prefix(self, mutation: ModuleType) -> None:
        """[Hostile] `tests/a.py` must not match `tests/a_helpers.py`, which a prefix check would
        wave through and quietly widen every campaign's scope."""
        records = mutation.scope_killers(
            [{"nodeid": "tests/a_helpers.py::test_x", "message": None}], scope=["tests/a.py"]
        )

        assert records[0]["in_scope"] is False

    def test_an_empty_scope_makes_nothing_in_scope(self, mutation: ModuleType) -> None:
        """The control: a campaign that names no files has not named these."""
        records = mutation.scope_killers(
            [{"nodeid": "tests/a.py::test_x", "message": None}], scope=[]
        )

        assert records[0]["in_scope"] is False


class TestScopeKillersHostileInput:
    """Story 2 — a node id that is not shaped like one must not widen the scope.

    `in_scope` decides whether a kill counts. Splitting on `::` and taking the head means anything
    without a separator becomes its own "file", and a campaign whose scope happened to contain
    that string would accept it. The failure is silent and in the permissive direction, which is
    the one that certifies unprotected code.
    """

    def test_a_nodeid_without_a_separator_is_not_in_scope(self, mutation: ModuleType) -> None:
        records = mutation.scope_killers(
            [{"nodeid": "not-a-node-id", "message": None}], scope=["tests/a.py"]
        )

        assert records[0]["in_scope"] is False

    def test_an_empty_nodeid_is_not_in_scope(self, mutation: ModuleType) -> None:
        records = mutation.scope_killers([{"nodeid": "", "message": None}], scope=["tests/a.py"])

        assert records[0]["in_scope"] is False

    def test_a_scope_entry_is_matched_whole_not_as_a_prefix(self, mutation: ModuleType) -> None:
        """[Hostile] `tests/a.py` must not admit `tests/a.py.bak::test_x`."""
        records = mutation.scope_killers(
            [{"nodeid": "tests/a.py.bak::test_x", "message": None}], scope=["tests/a.py"]
        )

        assert records[0]["in_scope"] is False
