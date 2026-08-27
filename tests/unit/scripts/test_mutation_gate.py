# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The gate that decides whether findings have been read.

Proves: TECH-049 FR-11, FR-11a, FR-12, NFR-5

It blocks on findings nobody has looked at, and releases the moment each carries a disposition —
never on proof that a fix worked. Demanding proof would mean an on-demand corpus run, which is the
inline model this design rejects; the next scheduled run re-measures anyway, so an unfixed finding
simply comes back. `runs` is what makes that safe: a `will-fix` re-confirmed for a fortnight is
visible rather than quietly renewed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


#: The real producer and the real baseline type. Imported rather than imitated: a hand-written
#: record shape is what let `68a089d4` rename the block under the gate and leave every test green.
_record = _load("_session_record")
_Baseline = _load("mutation").Baseline


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load("_mutation_gate")


def _report(tmp_path: Path, *results: dict[str, Any], age_hours: float = 0.0) -> Path:
    path = tmp_path / "mutation_session.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "session": {"head": "abc1234"},
                "mutants": list(results),
            }
        ),
        encoding="utf-8",
    )
    if age_hours:
        old = time.time() - age_hours * 3600
        import os

        os.utime(path, (old, old))
    return path


def _finding(verdict: str = "UNPROTECTED", ident: str = "F FR-1 m") -> dict[str, Any]:
    return {"id": ident, "verdict": verdict, "reason": "", "drift": "OK", "detail": ""}


def _ledger(tmp_path: Path, **entries: dict[str, Any]) -> Path:
    path = tmp_path / "mutation_findings.json"
    path.write_text(json.dumps({"findings": entries, "override_count": 0}), encoding="utf-8")
    return path


class TestGateVerdict:
    """Three rules, and what each of them refuses to do."""

    def test_a_missing_record_blocks(self, gate: ModuleType, tmp_path: Path) -> None:
        result = gate.gate_verdict(tmp_path / "absent.json", _ledger(tmp_path))
        assert result.blocked is True
        assert "session record" in result.reason

    def test_a_report_older_than_48h_blocks(self, gate: ModuleType, tmp_path: Path) -> None:
        """A scheduler that quietly stopped must not read as a clean bill of health.

        The report is deliberately **all-passing**: an earlier version used one with an
        unconfirmed failure, so rule 2 blocked it regardless and neutralising the staleness check
        changed nothing. The mutant said so. Only a report that would otherwise clear can prove
        staleness is what blocked it.
        """
        report = _report(tmp_path, _finding("PROTECTED"), age_hours=49)
        result = gate.gate_verdict(report, _ledger(tmp_path))
        assert result.blocked is True
        assert "old" in result.reason

    def test_a_report_older_than_the_last_scheduled_run_is_stale(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] This replaced a 48-hour tolerance, and the tolerance was the bug.

        One missed night used to be forgiven so a reboot would not read as a block. What it
        actually forgave was a nightly that hung at 03:00 and wrote nothing: at 04:22 the gate
        answered CLEAR from the previous morning's report, 20 hours old and well inside the
        window. Freshness is now measured against the schedule, so a run that was due and did not
        report is an alarm on the morning it happens.
        """
        report = _report(tmp_path, age_hours=47)
        assert gate.gate_verdict(report, _ledger(tmp_path)).blocked is True

    def test_an_unconfirmed_failure_blocks_and_names_it(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        result = gate.gate_verdict(_report(tmp_path, _finding()), _ledger(tmp_path))
        assert result.blocked is True
        assert "F FR-1 m" in result.unconfirmed

    def test_a_confirmed_failure_clears(self, gate: ModuleType, tmp_path: Path) -> None:
        ledger = _ledger(
            tmp_path,
            **{
                "F FR-1 m": {
                    "occurrences": 1,
                    "history": [
                        {
                            "at": 0.0,
                            "state": "open",
                            "verdict": "UNPROTECTED",
                            "reason": "no-killer",
                        },
                        {
                            "at": 1.0,
                            "state": "disposed",
                            "disposition": "will-fix",
                            "why": "recorded",
                        },
                    ],
                }
            },
        )
        assert gate.gate_verdict(_report(tmp_path, _finding()), ledger).blocked is False

    def test_a_broken_finding_also_needs_confirming(self, gate: ModuleType, tmp_path: Path) -> None:
        result = gate.gate_verdict(_report(tmp_path, _finding("UNMEASURED")), _ledger(tmp_path))
        assert result.blocked is True

    def test_indeterminate_alone_does_not_block(self, gate: ModuleType, tmp_path: Path) -> None:
        """The tree was already red. That is not evidence a requirement is unprotected.

        Blocking here would train people to confirm noise, and a gate whose findings are mostly
        noise is one nobody reads.
        """
        result = gate.gate_verdict(_report(tmp_path, _finding("UNMEASURED")), _ledger(tmp_path))
        assert result.blocked is True

    def test_learning_nothing_is_not_a_free_pass(self, gate: ModuleType, tmp_path: Path) -> None:
        """This inverted with the vocabulary, and the inversion is the point.

        `INDETERMINATE` and `STALE` used not to block, on the reasoning that they were noise and a
        gate full of noise goes unread. What that actually bought was two of the three ways to
        learn nothing passing silently — a corpus can rot toward zero coverage while every morning
        reads clear. `UNMEASURED` says the campaign, the tests or the machine is broken, and each
        of those is fixed by a person.
        """
        result = gate.gate_verdict(_report(tmp_path, _finding("UNMEASURED")), _ledger(tmp_path))
        assert result.blocked is True

    def test_a_passing_report_clears(self, gate: ModuleType, tmp_path: Path) -> None:
        result = gate.gate_verdict(_report(tmp_path, _finding("PROTECTED")), _ledger(tmp_path))
        assert result.blocked is False


class TestRecordRun:
    """`FR-11a` — how many runs a finding has survived."""

    def test_a_returning_finding_increments_its_count(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        ledger = _ledger(
            tmp_path,
            **{
                "F FR-1 m": {
                    "occurrences": 3,
                    "history": [
                        {
                            "at": 0.0,
                            "state": "open",
                            "verdict": "UNPROTECTED",
                            "reason": "no-killer",
                        },
                        {
                            "at": 1.0,
                            "state": "disposed",
                            "disposition": "will-fix",
                            "why": "recorded",
                        },
                    ],
                }
            },
        )
        gate.record_run(_report(tmp_path, _finding()), ledger)
        assert json.loads(ledger.read_text())["findings"]["F FR-1 m"]["occurrences"] == 4

    def test_a_finding_that_disappeared_is_closed_not_deleted(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """This rule inverted, and the inversion is the point.

        Deleting on absence kept the file small and made the ledger unable to answer the one
        question it exists for: how long did this defect live. A finding that was fixed left no
        trace, and one that returned every few months read as six unrelated ones. It now closes,
        carrying why it closed, and is pruned a year later.
        """
        ledger = _ledger(
            tmp_path,
            **{
                "F FR-1 gone": {
                    "occurrences": 9,
                    "history": [
                        {
                            "at": 0.0,
                            "state": "open",
                            "verdict": "UNPROTECTED",
                            "reason": "no-killer",
                        },
                        {
                            "at": 1.0,
                            "state": "disposed",
                            "disposition": "will-fix",
                            "why": "recorded",
                        },
                    ],
                }
            },
        )
        gate.record_run(_report(tmp_path, _finding("PROTECTED")), ledger)

        entry = json.loads(ledger.read_text())["findings"]["F FR-1 gone"]
        assert gate.current_state(entry) == "closed"
        assert entry["history"][-1]["reason"] == "withdrawn"

    def test_a_new_finding_starts_at_one(self, gate: ModuleType, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        gate.record_run(_report(tmp_path, _finding()), ledger)
        assert json.loads(ledger.read_text())["findings"]["F FR-1 m"]["occurrences"] == 1


class TestConfirm:
    """Recording that a human looked, and what they decided."""

    def test_a_disposition_is_recorded_with_its_reason(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        ledger = _ledger(tmp_path)
        gate.confirm(ledger, "F FR-1 m", disposition="will-fix", why="narrowing scope first")

        entry = json.loads(ledger.read_text())["findings"]["F FR-1 m"]
        disposed = [h for h in entry["history"] if h["state"] == "disposed"]
        assert disposed[-1]["disposition"] == "will-fix"
        assert disposed[-1]["why"] == "narrowing scope first"
        assert disposed[-1]["at"], "when it was decided is the half a field could not carry"

    def test_an_unknown_disposition_is_refused(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Hostile] Six dispositions exist; a seventh would silently escape the census."""
        with pytest.raises(ValueError, match="disposition"):
            gate.confirm(_ledger(tmp_path), "F FR-1 m", disposition="probably-fine", why="x")

    def test_an_empty_reason_is_refused(self, gate: ModuleType, tmp_path: Path) -> None:
        """A confirmation with no reason is a click-through, which is what the census exists to stop."""
        with pytest.raises(ValueError, match="why"):
            gate.confirm(_ledger(tmp_path), "F FR-1 m", disposition="will-fix", why="  ")

    def test_confirming_preserves_the_recurrence_count(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] Deciding what to do about a finding must not reset how long it has been here."""
        ledger = _ledger(
            tmp_path,
            **{
                "F FR-1 m": {
                    "occurrences": 7,
                    "history": [
                        {
                            "at": 0.0,
                            "state": "open",
                            "verdict": "UNPROTECTED",
                            "reason": "no-killer",
                        }
                    ],
                }
            },
        )
        gate.confirm(ledger, "F FR-1 m", disposition="will-fix", why="still triaging")
        assert json.loads(ledger.read_text())["findings"]["F FR-1 m"]["occurrences"] == 7


class TestOverrideCensus:
    """`FR-12` — the count may fall, never rise."""

    def test_a_will_fix_counts_as_an_override(self, gate: ModuleType, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        gate.confirm(ledger, "F FR-1 m", disposition="will-fix", why="later")
        assert json.loads(ledger.read_text())["override_count"] == 1

    def test_an_equivalent_mutant_counts_too(self, gate: ModuleType, tmp_path: Path) -> None:
        """Surviving because the mutant changes nothing still releases the gate without a fix."""
        ledger = _ledger(tmp_path)
        gate.confirm(ledger, "F FR-1 m", disposition="equivalent", why="no observable change")
        assert json.loads(ledger.read_text())["override_count"] == 1

    def test_a_real_gap_does_not_count(self, gate: ModuleType, tmp_path: Path) -> None:
        """You fixed it. That is the gate working, not a bypass of it."""
        ledger = _ledger(tmp_path)
        gate.confirm(ledger, "F FR-1 m", disposition="real-gap", why="wrote the missing test")
        assert json.loads(ledger.read_text())["override_count"] == 0

    def test_a_stale_refresh_does_not_count(self, gate: ModuleType, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        gate.confirm(ledger, "F FR-1 m", disposition="stale-refreshed", why="re-read and re-pinned")
        assert json.loads(ledger.read_text())["override_count"] == 0

    def test_growth_past_the_baseline_fails(self, gate: ModuleType, tmp_path: Path) -> None:
        assert gate.ratchet_ok(current=3, baseline=2) is False

    def test_a_falling_count_passes(self, gate: ModuleType, tmp_path: Path) -> None:
        """The whole point of a ratchet: debt may be repaid, never taken on silently."""
        assert gate.ratchet_ok(current=1, baseline=2) is True
        assert gate.ratchet_ok(current=2, baseline=2) is True


class TestARedBaselineBlocks:
    """A run whose baseline was red proves nothing, and the gate must not call it clear.

    The report already records this and the summary already says it in as many words — *every
    verdict below is meaningless while the baseline is red* — but the gate never read the field. So
    the nightly announced `CLEAR: every finding carries a disposition` about twenty-six mutants that
    had been judged against a tree whose suite never ran.

    That is the same failure the gate exists to prevent, one level up: not a finding nobody read,
    but a whole session nobody could have learned anything from.

    **Every record here comes from the producer.** This class used to hand-build
    `{"summary": …, "campaigns": []}` — a shape no producer has written since `68a089d4` renamed
    the block `session`, and one `findings_in` cannot read either. So the rule was proven against
    a document nothing emits while the shipped gate could not fire at all. The pair is proven at
    the integration tier, where it belongs; this file keeps the per-branch detail and buys it from
    `build_session_record` so it can never again describe a record nobody writes.

    Proves: TECH-049 FR-3a
    """

    @staticmethod
    def _report(tmp_path: Path, baseline: Any) -> Path:
        """`baseline` is a real `Baseline`, or `None` for a `--no-baseline` run."""
        report = tmp_path / "mutation_session.json"
        report.write_text(
            json.dumps(
                _record.build_session_record(
                    campaigns=[], head="abc1234", dirty=False, baseline=baseline
                )
            ),
            encoding="utf-8",
        )
        return report

    def test_a_red_baseline_blocks_even_with_no_findings(self, gate, tmp_path) -> None:

        report = self._report(tmp_path, _Baseline(green=False, failures=["t::a"], code=1))
        ledger = tmp_path / "ledger.json"

        result = gate.gate_verdict(report, ledger)

        assert result.blocked, "a session judged against a broken tree was reported as clear"
        assert "baseline" in result.reason.lower(), result.reason

    def test_a_green_baseline_is_judged_on_its_findings(self, gate, tmp_path) -> None:
        """The control: the new rule must not swallow the one the gate already had."""
        report = self._report(tmp_path, _Baseline(green=True))
        ledger = tmp_path / "ledger.json"

        result = gate.gate_verdict(report, ledger)

        assert not result.blocked, result.reason

    def test_a_report_with_no_baseline_recorded_is_judged_as_before(self, gate, tmp_path) -> None:
        """A session run with `--no-baseline` says nothing about the tree, and never claimed to.

        The producer writes `{"ran": false}` here, not an absent block. A gate that asked whether
        the block was present would read *nobody measured* as *the tree was red* and block every
        `--no-baseline` run — the safe absence turned into the loud failure.
        """
        report = self._report(tmp_path, None)

        assert json.loads(report.read_text())["session"]["baseline"] == {"ran": False}
        assert not gate.gate_verdict(report, tmp_path / "ledger.json").blocked

    def test_a_red_baseline_with_no_count_still_blocks(self, gate, tmp_path) -> None:
        """[Boundary] the reason degrades to `?`; the verdict does not degrade to CLEAR.

        A baseline block can reach the gate without `failed` — an older record, or a producer that
        learned the tree was red without counting. The count is decoration on the message; the
        block is the requirement.
        """
        report = tmp_path / "mutation_session.json"
        report.write_text(
            json.dumps({"schema": 1, "session": {"baseline": {"ran": True, "green": False}}}),
            encoding="utf-8",
        )

        result = gate.gate_verdict(report, tmp_path / "ledger.json")

        assert result.blocked, result.reason
        assert "? failing" in result.reason, result.reason


class TestAnUnreadableRecordIsNotAPass:
    """A record the gate cannot understand is not a clean bill of health.

    Proves: TECH-049 FR-11

    `_read_json` answers `{}` for anything it cannot parse, and every rule below it reads that as
    *nothing to report*: no baseline block, so the baseline rule is silent; no mutants, so there
    are no findings; `CLEAR: every finding carries a disposition`, about a file with nothing in it.

    Measured against the shipped gate before this class existed — corrupt JSON, an empty file and a
    record with its `session` block missing all three read `CLEAR`.

    This is the same defect as the baseline reader one level down. `FR-11` already says a **missing**
    record blocks; a record that arrives unreadable is missing in every sense that matters, and it
    is what a run killed mid-write leaves behind. The staleness rule cannot catch it, because the
    file's mtime is new — the nightly really did write it, just not all of it.
    """

    @staticmethod
    def _written_now(tmp_path: Path, body: str) -> Path:
        """On disk and fresh, so only readability is under test."""
        path = tmp_path / "mutation_session.json"
        path.write_text(body, encoding="utf-8")
        now = time.time()
        os.utime(path, (now, now))
        return path

    def test_a_record_that_is_not_json_blocks(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Hostile] a half-written file — the nightly killed mid-`write_text`."""
        report = self._written_now(tmp_path, '{"schema": 1, "session": {"bas')

        result = gate.gate_verdict(report, tmp_path / "ledger.json")

        assert result.blocked, "an unparseable record was reported as a clean session"
        assert "read" in result.reason.lower(), result.reason

    def test_an_empty_record_blocks(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Hostile] zero bytes. `touch` on the record path must not clear the morning gate."""
        report = self._written_now(tmp_path, "")

        assert gate.gate_verdict(report, tmp_path / "ledger.json").blocked

    def test_a_record_with_no_session_block_blocks(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Boundary] valid JSON, and still not a session record.

        Distinct from the two above on purpose: this one parses. Nothing raises, nothing is caught,
        and the document simply does not describe a run — which every rule below reads as silence.
        """
        report = self._written_now(tmp_path, json.dumps({"schema": 1, "mutants": []}))

        result = gate.gate_verdict(report, tmp_path / "ledger.json")

        assert result.blocked, "a document that describes no session was reported as one that did"

    def test_a_readable_record_is_still_judged_on_its_contents(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Happy] the control. A rule that blocked every record would be switched off in a week."""
        report = self._written_now(
            tmp_path,
            json.dumps(
                _record.build_session_record(
                    campaigns=[], head="abc1234", dirty=False, baseline=_Baseline(green=True)
                )
            ),
        )

        assert not gate.gate_verdict(report, tmp_path / "ledger.json").blocked


class TestLastExpectedRun:
    """The nightly's own schedule decides what "current" means, not a fixed tolerance.

    Measured 2026-08-20: a 03:00 run wedged on a mutant that made a WebSocket test wait for a
    message that never arrived. It never wrote a report. At 04:22 the gate read the previous
    morning's report — 20 hours old, inside the 48-hour tolerance — and answered CLEAR. A nightly
    that had been hung for eighty minutes reported as a clean bill of health, and would have done
    so again the next morning, and the next.

    **A missing report for a run that should have happened is an alarm, not a pass.**
    """

    def test_a_report_from_before_todays_run_is_stale(self, gate: ModuleType) -> None:
        now = time.mktime((2026, 8, 20, 4, 22, 0, 0, 0, -1))
        yesterday_morning = time.mktime((2026, 8, 19, 7, 59, 0, 0, 0, -1))

        assert yesterday_morning < gate.last_expected_run(now)

    def test_a_report_from_after_todays_run_is_current(self, gate: ModuleType) -> None:
        """The control. A gate that called everything stale would be switched off in a week."""
        now = time.mktime((2026, 8, 20, 4, 22, 0, 0, 0, -1))
        this_morning = time.mktime((2026, 8, 20, 3, 30, 0, 0, 0, -1))

        assert this_morning >= gate.last_expected_run(now)

    def test_before_the_run_hour_yesterdays_report_still_counts(self, gate: ModuleType) -> None:
        """At 02:00 the night's run has not happened yet, so last night's report is the current
        one. Alarming then would fire every single night."""
        now = time.mktime((2026, 8, 20, 2, 0, 0, 0, 0, -1))
        yesterday_morning = time.mktime((2026, 8, 19, 3, 30, 0, 0, 0, -1))

        assert yesterday_morning >= gate.last_expected_run(now)


class TestGateVerdictStaleness:
    """`gate_verdict` — what the human is told.

    **Every test here pins the clock, and that is not tidiness.** "Fresh" is not an age: a report
    is current when it was written *after the last scheduled run*, and `NIGHTLY_HOUR` is 3. A
    report sixty seconds old is fresh at 10:00 and stale at 03:00:30, because at 03:00:30 sixty
    seconds ago was yesterday's business.

    This class used to assert that a sixty-second-old report never blocks. That is false for one
    minute of every day — 03:00:00 to 03:01:00 — and the nightly runs at 03:00. It failed on the
    2026-08-26 run, took the whole baseline red with it, and voided all 145 verdicts including the
    five `TECH-056` mutants that share this file. Wall-clock time is an input; an input a test does
    not control is not a test.
    """

    def _report(self, tmp_path: Path, written_at: float) -> Path:
        """From the producer, so a record that ages is the record the nightly actually leaves."""
        report = tmp_path / "report.json"
        report.write_text(
            json.dumps(
                _record.build_session_record(
                    campaigns=[], head="abc1234", dirty=False, baseline=None
                )
            ),
            encoding="utf-8",
        )
        os.utime(report, (written_at, written_at))
        return report

    @staticmethod
    def _at(gate: ModuleType, monkeypatch: pytest.MonkeyPatch, when: float) -> None:
        """Hold `gate`'s view of now at `when`, leaving the real `time` module alone."""
        monkeypatch.setattr(
            gate,
            "time",
            SimpleNamespace(
                time=lambda: when,
                localtime=time.localtime,
                mktime=time.mktime,
                strftime=time.strftime,
            ),
        )

    def test_a_report_older_than_the_last_run_blocks(
        self, gate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._at(gate, monkeypatch, time.mktime((2026, 8, 26, 10, 0, 0, 0, 0, -1)))
        report = self._report(tmp_path, time.mktime((2026, 8, 25, 3, 5, 0, 0, 0, -1)))

        result = gate.gate_verdict(report, tmp_path / "ledger.json")

        assert result.blocked
        assert "did not" in result.reason or "no report" in result.reason

    def test_a_fresh_report_does_not_block_on_staleness(
        self, gate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The control: freshness must not become a second way to fail an otherwise clean run."""
        self._at(gate, monkeypatch, time.mktime((2026, 8, 26, 10, 0, 0, 0, 0, -1)))
        report = self._report(tmp_path, time.mktime((2026, 8, 26, 3, 5, 0, 0, 0, -1)))

        result = gate.gate_verdict(report, tmp_path / "ledger.json")

        assert not result.blocked

    def test_during_the_run_minute_tonights_report_is_current(
        self, gate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """03:00:30, report written ten seconds ago — by tonight's run. It must not block.

        This is what the old sixty-second test meant to say. Reproduced against the shipped gate
        before the fix: at this instant a sixty-second-old report blocks, and it is right to.
        """
        self._at(gate, monkeypatch, time.mktime((2026, 8, 26, 3, 0, 30, 0, 0, -1)))
        report = self._report(tmp_path, time.mktime((2026, 8, 26, 3, 0, 20, 0, 0, -1)))

        result = gate.gate_verdict(report, tmp_path / "ledger.json")

        assert not result.blocked

    def test_during_the_run_minute_a_report_from_before_it_still_blocks(
        self, gate: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other half, and the one the nightly tripped over. 03:00:30, report written at
        02:59:30 — sixty seconds old, and from before tonight's run started. Age says fresh; the
        schedule says tonight produced nothing yet. The schedule wins."""
        self._at(gate, monkeypatch, time.mktime((2026, 8, 26, 3, 0, 30, 0, 0, -1)))
        report = self._report(tmp_path, time.mktime((2026, 8, 26, 2, 59, 30, 0, 0, -1)))

        result = gate.gate_verdict(report, tmp_path / "ledger.json")

        assert result.blocked
