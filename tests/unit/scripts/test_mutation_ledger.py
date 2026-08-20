# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The durable half: which findings exist, how they changed, and how long they lived.

Stage D of the mutation data contract. The ledger is the only part of this tool that is committed
to git, and until now it **deleted** a finding the moment it stopped appearing — so the question
it exists to answer, *how long did this defect live*, could not be answered at all. A finding that
was fixed left no trace, and one that returned every few months looked like six unrelated ones.

Two rules carry the redesign:

- **Current state is the last history entry, never a field beside it.** A stored current-state is a
  second copy that can disagree with its own history, which is what this whole contract is against.
- **Append only on change.** A session that sees the same finding in the same state writes nothing,
  so history grows with events rather than with runs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
DAY = 86400.0


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_mutation_gate", REPO_ROOT / "scripts" / "_mutation_gate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_mutation_gate"] = module
    spec.loader.exec_module(module)
    return module


def _empty() -> dict[str, Any]:
    return {"schema": 1, "findings": {}}


def _judged(**verdicts: str) -> dict[str, str]:
    return dict(verdicts)


class TestFoldSessionOpening:
    """A finding arrives."""

    def test_a_new_finding_is_opened(self, gate: ModuleType) -> None:
        ledger = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )

        entry = ledger["findings"]["F FR-1 m"]
        assert entry["history"][-1]["state"] == "open"
        assert entry["history"][-1]["verdict"] == "UNPROTECTED"
        assert entry["history"][-1]["reason"] == "no-killer"

    def test_a_protected_mutant_is_not_a_finding(self, gate: ModuleType) -> None:
        """The control. Recording clean results would make the ledger a log, not a ledger."""
        ledger = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "PROTECTED"},
            reasons={},
            declared={"F FR-1 m"},
            now=0.0,
        )

        assert ledger["findings"] == {}

    def test_first_and_last_seen_start_together(self, gate: ModuleType) -> None:
        ledger = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=1000.0,
        )

        entry = ledger["findings"]["F FR-1 m"]
        assert entry["first_seen"] == entry["last_seen"]
        assert entry["occurrences"] == 1


class TestFoldSessionAppendOnChange:
    """History records events, not runs."""

    def _opened(self, gate: ModuleType) -> dict[str, Any]:
        return gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )

    def test_an_unchanged_finding_appends_nothing(self, gate: ModuleType) -> None:
        ledger = gate.fold_session(
            self._opened(gate),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=DAY,
        )

        assert len(ledger["findings"]["F FR-1 m"]["history"]) == 1

    def test_but_it_still_counts_and_moves_last_seen(self, gate: ModuleType) -> None:
        """Occurrences is the one number a change-only history cannot reconstruct."""
        ledger = gate.fold_session(
            self._opened(gate),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=DAY,
        )

        entry = ledger["findings"]["F FR-1 m"]
        assert entry["occurrences"] == 2
        assert entry["last_seen"] != entry["first_seen"]

    def test_a_changed_reason_is_a_new_entry(self, gate: ModuleType) -> None:
        """`bad-anchor` becoming `timed-out` is a different defect with a different fix, and the
        old shape could not record it at all."""
        ledger = gate.fold_session(
            self._opened(gate),
            judged={"F FR-1 m": "UNMEASURED"},
            reasons={"F FR-1 m": "timed-out"},
            declared={"F FR-1 m"},
            now=DAY,
        )

        history = ledger["findings"]["F FR-1 m"]["history"]
        assert len(history) == 2
        assert (history[-1]["verdict"], history[-1]["reason"]) == ("UNMEASURED", "timed-out")


class TestFoldSessionClosing:
    """A finding leaves — and *why* it left is the statistic."""

    def _opened(self, gate: ModuleType) -> dict[str, Any]:
        return gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )

    def test_a_mutant_now_protected_closes_as_fixed(self, gate: ModuleType) -> None:
        ledger = gate.fold_session(
            self._opened(gate),
            judged={"F FR-1 m": "PROTECTED"},
            reasons={},
            declared={"F FR-1 m"},
            now=DAY,
        )

        last = ledger["findings"]["F FR-1 m"]["history"][-1]
        assert (last["state"], last["reason"]) == ("closed", "fixed")

    def test_a_mutant_gone_from_the_corpus_closes_as_withdrawn(self, gate: ModuleType) -> None:
        """Deleting the campaign must not read as a year of diligent fixing."""
        ledger = gate.fold_session(
            self._opened(gate), judged={}, reasons={}, declared=set(), now=DAY
        )

        last = ledger["findings"]["F FR-1 m"]["history"][-1]
        assert (last["state"], last["reason"]) == ("closed", "withdrawn")

    def test_a_declared_mutant_that_never_ran_closes_as_unreachable(self, gate: ModuleType) -> None:
        ledger = gate.fold_session(
            self._opened(gate), judged={}, reasons={}, declared={"F FR-1 m"}, now=DAY
        )

        last = ledger["findings"]["F FR-1 m"]["history"][-1]
        assert (last["state"], last["reason"]) == ("closed", "unreachable")

    def test_a_closure_is_not_repeated_every_session(self, gate: ModuleType) -> None:
        """[Boundary] Append-on-change applies to closing too, or a closed finding grows a line
        a night for ever."""
        closed = gate.fold_session(
            self._opened(gate), judged={}, reasons={}, declared=set(), now=DAY
        )
        again = gate.fold_session(closed, judged={}, reasons={}, declared=set(), now=2 * DAY)

        assert len(again["findings"]["F FR-1 m"]["history"]) == 2

    def test_a_reappearance_reopens_the_same_entry(self, gate: ModuleType) -> None:
        """One long-lived finding, not six short ones — which is what makes a period visible."""
        closed = gate.fold_session(
            self._opened(gate), judged={}, reasons={}, declared=set(), now=DAY
        )
        reopened = gate.fold_session(
            closed,
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=30 * DAY,
        )

        entry = reopened["findings"]["F FR-1 m"]
        assert entry["first_seen"] == 0.0 or entry["history"][0]["at"] == 0.0
        assert [h["state"] for h in entry["history"]] == ["open", "closed", "open"]


class TestFoldSessionRetention:
    """Long enough to see a pattern; not for ever."""

    def _closed_at(self, gate: ModuleType, when: float) -> dict[str, Any]:
        opened = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )
        return gate.fold_session(opened, judged={}, reasons={}, declared=set(), now=when)

    def test_a_finding_closed_recently_is_kept(self, gate: ModuleType) -> None:
        ledger = self._closed_at(gate, DAY)

        pruned = gate.fold_session(ledger, judged={}, reasons={}, declared=set(), now=100 * DAY)

        assert "F FR-1 m" in pruned["findings"]

    def test_a_finding_closed_over_a_year_ago_is_pruned(self, gate: ModuleType) -> None:
        ledger = self._closed_at(gate, DAY)

        pruned = gate.fold_session(ledger, judged={}, reasons={}, declared=set(), now=400 * DAY)

        assert "F FR-1 m" not in pruned["findings"]

    def test_an_open_finding_is_never_pruned_however_old(self, gate: ModuleType) -> None:
        """[Hostile] Age is not a disposition. A defect that has been here two years is the one
        most worth seeing, not the one to forget."""
        opened = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )

        later = gate.fold_session(
            opened,
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=800 * DAY,
        )

        assert "F FR-1 m" in later["findings"]


class TestCurrentStateIsDerived:
    """Read from the history, never stored beside it."""

    def test_the_current_verdict_comes_from_the_last_open_entry(self, gate: ModuleType) -> None:
        ledger = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNMEASURED"},
            reasons={"F FR-1 m": "timed-out"},
            declared={"F FR-1 m"},
            now=0.0,
        )

        assert gate.current_state(ledger["findings"]["F FR-1 m"]) == "open"

    def test_a_closed_finding_reads_closed(self, gate: ModuleType) -> None:
        opened = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )
        closed = gate.fold_session(opened, judged={}, reasons={}, declared=set(), now=DAY)

        assert gate.current_state(closed["findings"]["F FR-1 m"]) == "closed"

    def test_no_verdict_is_stored_outside_the_history(self, gate: ModuleType) -> None:
        """The rule this contract is built on: one fact, one place."""
        ledger = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )

        entry = ledger["findings"]["F FR-1 m"]
        assert "verdict" not in entry
        assert "reason" not in entry
        assert "closed_at" not in entry


class TestConfirmWritesHistory:
    """A human's decision is a state change, so it belongs in the history like any other.

    It used to overwrite a field, so *when* somebody accepted a finding — and whether they later
    changed their mind — was unrecoverable. "Accepted in March and still open in August" is the
    statistic that makes a `will-fix` uncomfortable, and it needs a date to exist.
    """

    def _open(self, gate: ModuleType, tmp_path: Path) -> Path:
        ledger = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )
        path = tmp_path / "ledger.json"
        gate.write_ledger(path, ledger)
        return path

    def test_a_disposition_is_appended_not_overwritten(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        path = self._open(gate, tmp_path)

        ledger = gate.confirm(path, "F FR-1 m", disposition="will-fix", why="scheduled")

        history = ledger["findings"]["F FR-1 m"]["history"]
        assert history[-1]["state"] == "disposed"
        assert (history[-1]["disposition"], history[-1]["why"]) == ("will-fix", "scheduled")

    def test_the_finding_is_still_open_after_a_disposition(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """Accepting a finding is not fixing it. `current_state` must still read `open`, or a
        `will-fix` would silently look resolved."""
        path = self._open(gate, tmp_path)

        ledger = gate.confirm(path, "F FR-1 m", disposition="will-fix", why="scheduled")

        assert gate.current_state(ledger["findings"]["F FR-1 m"]) == "open"

    def test_changing_your_mind_keeps_both_decisions(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        path = self._open(gate, tmp_path)
        gate.confirm(path, "F FR-1 m", disposition="will-fix", why="scheduled")

        ledger = gate.confirm(path, "F FR-1 m", disposition="real-gap", why="wrote the test")

        dispositions = [
            h["disposition"]
            for h in ledger["findings"]["F FR-1 m"]["history"]
            if h["state"] == "disposed"
        ]
        assert dispositions == ["will-fix", "real-gap"]

    def test_an_unmeasured_finding_takes_its_own_dispositions(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """`equivalent` is meaningless for a campaign that could not run; these two say where the
        fix went."""
        path = self._open(gate, tmp_path)

        for code in ("fixed-campaign", "fixed-environment"):
            gate.confirm(path, "F FR-1 m", disposition=code, why="because")

        assert (
            gate.load_ledger(path)["findings"]["F FR-1 m"]["history"][-1]["disposition"]
            == "fixed-environment"
        )

    def test_an_unknown_disposition_is_still_refused(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """The control on the widened vocabulary."""
        path = self._open(gate, tmp_path)

        with pytest.raises(ValueError, match="unknown disposition"):
            gate.confirm(path, "F FR-1 m", disposition="looks-fine", why="because")

    def test_a_reason_is_still_mandatory(self, gate: ModuleType, tmp_path: Path) -> None:
        path = self._open(gate, tmp_path)

        with pytest.raises(ValueError, match="why is required"):
            gate.confirm(path, "F FR-1 m", disposition="will-fix", why="   ")


class TestCurrentStateEdges:
    """Stories 1 and 4 — reading a state from a history that does not cooperate."""

    def test_an_entry_with_no_history_is_unknown_not_open(self, gate: ModuleType) -> None:
        """[Hostile] A hand-edited or half-written entry must not default to `open`.

        `open` would invent a finding nobody recorded and block the gate on it; `closed` would
        hide one. `unknown` is the only answer that is true.
        """
        assert gate.current_state({}) == "unknown"
        assert gate.current_state({"history": []}) == "unknown"

    def test_a_disposition_does_not_hide_the_state_beneath_it(self, gate: ModuleType) -> None:
        """[Boundary] Accepting a finding is not resolving it, so the newest entry is not always
        the one that carries the state."""
        entry = {
            "history": [
                {"at": 0.0, "state": "open", "verdict": "UNPROTECTED", "reason": "no-killer"},
                {"at": 1.0, "state": "disposed", "disposition": "will-fix", "why": "later"},
            ]
        }

        assert gate.current_state(entry) == "open"

    def test_an_unrecognised_state_is_skipped_rather_than_trusted(self, gate: ModuleType) -> None:
        """[Hostile] A future version writing a state this one does not know must not make the
        entry unreadable — the last state we *do* understand still holds."""
        entry = {
            "history": [
                {"at": 0.0, "state": "open", "verdict": "UNPROTECTED", "reason": "no-killer"},
                {"at": 1.0, "state": "hibernating"},
            ]
        }

        assert gate.current_state(entry) == "open"


class TestLatestDispositionEdges:
    """Story 2."""

    def test_an_entry_never_disposed_returns_none(self, gate: ModuleType) -> None:
        entry = {"history": [{"at": 0.0, "state": "open", "verdict": "UNPROTECTED"}]}

        assert gate.latest_disposition(entry) is None

    def test_an_empty_entry_returns_none(self, gate: ModuleType) -> None:
        """The control: `None` means nobody decided, and the gate blocks on exactly that."""
        assert gate.latest_disposition({}) is None


class TestRetentionClockReadsTheClosure:
    """RED-D.1 — the year runs from when it closed, not from the last thing anyone wrote.

    A human can record a disposition after a finding has closed — noting what fixed it, or
    correcting an earlier call. That entry then sits last in the history, and reading the clock off
    the last entry restarts the year from the note rather than from the closure. A finding could be
    kept indefinitely by commenting on it, which is the opposite of a bounded file.
    """

    def _closed_then_disposed(self, gate: ModuleType) -> dict[str, Any]:
        opened = gate.fold_session(
            _empty(),
            judged={"F FR-1 m": "UNPROTECTED"},
            reasons={"F FR-1 m": "no-killer"},
            declared={"F FR-1 m"},
            now=0.0,
        )
        closed = gate.fold_session(opened, judged={}, reasons={}, declared=set(), now=DAY)
        entry = closed["findings"]["F FR-1 m"]
        # Late on purpose. A note written a day after the closure cannot tell the two readings
        # apart — both say "keep" or both say "prune" — so the test would pass either way. The gap
        # has to straddle the retention boundary for the assertion to mean anything.
        entry["history"].append(
            {"at": 300 * DAY, "state": "disposed", "disposition": "real-gap", "why": "wrote it"}
        )
        return closed

    def test_the_clock_runs_from_the_closure_not_the_note(self, gate: ModuleType) -> None:
        ledger = self._closed_then_disposed(gate)

        # 400 days after the closure, but only 101 after the note.
        pruned = gate.fold_session(ledger, judged={}, reasons={}, declared=set(), now=401 * DAY)

        assert "F FR-1 m" not in pruned["findings"]

    def test_a_note_does_not_reopen_it(self, gate: ModuleType) -> None:
        """The control: the state is still closed, whatever was written afterwards."""
        assert (
            gate.current_state(self._closed_then_disposed(gate)["findings"]["F FR-1 m"]) == "closed"
        )

    def test_a_recently_closed_finding_is_still_kept(self, gate: ModuleType) -> None:
        """The other control — pruning must not become eager."""
        ledger = self._closed_then_disposed(gate)

        kept = gate.fold_session(ledger, judged={}, reasons={}, declared=set(), now=10 * DAY)

        assert "F FR-1 m" in kept["findings"]
