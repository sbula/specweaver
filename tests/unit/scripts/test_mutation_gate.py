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
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


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


def _report(tmp_path: Path, *results: dict[str, Any], age_hours: float = 0.0) -> Path:
    path = tmp_path / "mutation_report.json"
    path.write_text(
        json.dumps(
            {
                "summary": {"head": "abc1234", "verdict": "FAILED"},
                "campaigns": [
                    {
                        "feature": "F",
                        "requirement": "FR-1",
                        "verdict": "FAILED",
                        "mutants_declared": len(results),
                        "verdicts_returned": len(results),
                        "results": list(results),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    if age_hours:
        old = time.time() - age_hours * 3600
        import os

        os.utime(path, (old, old))
    return path


def _finding(verdict: str = "FAIL", ident: str = "F FR-1 m") -> dict[str, Any]:
    return {"derived_id": ident, "verdict": verdict, "reason": "", "drift": "OK", "detail": ""}


def _ledger(tmp_path: Path, **entries: dict[str, Any]) -> Path:
    path = tmp_path / "mutation_findings.json"
    path.write_text(json.dumps({"findings": entries, "override_count": 0}), encoding="utf-8")
    return path


class TestGateVerdict:
    """Three rules, and what each of them refuses to do."""

    def test_a_missing_report_blocks(self, gate: ModuleType, tmp_path: Path) -> None:
        result = gate.gate_verdict(tmp_path / "absent.json", _ledger(tmp_path))
        assert result.blocked is True
        assert "report" in result.reason

    def test_a_report_older_than_48h_blocks(self, gate: ModuleType, tmp_path: Path) -> None:
        """A scheduler that quietly stopped must not read as a clean bill of health.

        The report is deliberately **all-passing**: an earlier version used one with an
        unconfirmed failure, so rule 2 blocked it regardless and neutralising the staleness check
        changed nothing. The mutant said so. Only a report that would otherwise clear can prove
        staleness is what blocked it.
        """
        report = _report(tmp_path, _finding("PASS"), age_hours=49)
        result = gate.gate_verdict(report, _ledger(tmp_path))
        assert result.blocked is True
        assert "old" in result.reason

    def test_a_report_within_48h_is_not_stale(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Boundary] One missed night is not a block — two is. 47h must pass."""
        report = _report(tmp_path, age_hours=47)
        assert gate.gate_verdict(report, _ledger(tmp_path)).blocked is False

    def test_an_unconfirmed_failure_blocks_and_names_it(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        result = gate.gate_verdict(_report(tmp_path, _finding()), _ledger(tmp_path))
        assert result.blocked is True
        assert "F FR-1 m" in result.unconfirmed

    def test_a_confirmed_failure_clears(self, gate: ModuleType, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path, **{"F FR-1 m": {"disposition": "will-fix", "runs": 1}})
        assert gate.gate_verdict(_report(tmp_path, _finding()), ledger).blocked is False

    def test_a_broken_finding_also_needs_confirming(self, gate: ModuleType, tmp_path: Path) -> None:
        result = gate.gate_verdict(_report(tmp_path, _finding("BROKEN")), _ledger(tmp_path))
        assert result.blocked is True

    def test_indeterminate_alone_does_not_block(self, gate: ModuleType, tmp_path: Path) -> None:
        """The tree was already red. That is not evidence a requirement is unprotected.

        Blocking here would train people to confirm noise, and a gate whose findings are mostly
        noise is one nobody reads.
        """
        result = gate.gate_verdict(_report(tmp_path, _finding("INDETERMINATE")), _ledger(tmp_path))
        assert result.blocked is False

    def test_stale_alone_does_not_block(self, gate: ModuleType, tmp_path: Path) -> None:
        result = gate.gate_verdict(_report(tmp_path, _finding("STALE")), _ledger(tmp_path))
        assert result.blocked is False

    def test_a_passing_report_clears(self, gate: ModuleType, tmp_path: Path) -> None:
        result = gate.gate_verdict(_report(tmp_path, _finding("PASS")), _ledger(tmp_path))
        assert result.blocked is False


class TestRecordRun:
    """`FR-11a` — how many runs a finding has survived."""

    def test_a_returning_finding_increments_its_count(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        ledger = _ledger(tmp_path, **{"F FR-1 m": {"disposition": "will-fix", "runs": 3}})
        gate.record_run(_report(tmp_path, _finding()), ledger)
        assert json.loads(ledger.read_text())["findings"]["F FR-1 m"]["runs"] == 4

    def test_a_finding_that_disappeared_is_pruned(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Boundary] The ledger describes today, not an archive of everything ever seen."""
        ledger = _ledger(tmp_path, **{"F FR-1 gone": {"disposition": "will-fix", "runs": 9}})
        gate.record_run(_report(tmp_path, _finding("PASS")), ledger)
        assert "F FR-1 gone" not in json.loads(ledger.read_text())["findings"]

    def test_a_new_finding_starts_at_one(self, gate: ModuleType, tmp_path: Path) -> None:
        ledger = _ledger(tmp_path)
        gate.record_run(_report(tmp_path, _finding()), ledger)
        assert json.loads(ledger.read_text())["findings"]["F FR-1 m"]["runs"] == 1


class TestConfirm:
    """Recording that a human looked, and what they decided."""

    def test_a_disposition_is_recorded_with_its_reason(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        ledger = _ledger(tmp_path)
        gate.confirm(ledger, "F FR-1 m", disposition="will-fix", why="narrowing scope first")
        entry = json.loads(ledger.read_text())["findings"]["F FR-1 m"]
        assert entry["disposition"] == "will-fix"
        assert entry["why"] == "narrowing scope first"

    def test_an_unknown_disposition_is_refused(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Hostile] Four dispositions exist; a fifth would silently escape the census."""
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
        ledger = _ledger(tmp_path, **{"F FR-1 m": {"runs": 7}})
        gate.confirm(ledger, "F FR-1 m", disposition="will-fix", why="still triaging")
        assert json.loads(ledger.read_text())["findings"]["F FR-1 m"]["runs"] == 7


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

    Proves: TECH-056 FR-2
    """

    @staticmethod
    def _report(tmp_path, baseline: dict) -> Path:
        report = tmp_path / "mutation_report.json"
        report.write_text(
            json.dumps({"summary": {"baseline": baseline, "verdict": "PASSED"}, "campaigns": []}),
            encoding="utf-8",
        )
        return report

    def test_a_red_baseline_blocks_even_with_no_findings(self, gate, tmp_path) -> None:

        report = self._report(tmp_path, {"green": False, "failed": 0})
        ledger = tmp_path / "ledger.json"

        result = gate.gate_verdict(report, ledger)

        assert result.blocked, "a session judged against a broken tree was reported as clear"
        assert "baseline" in result.reason.lower(), result.reason

    def test_a_green_baseline_is_judged_on_its_findings(self, gate, tmp_path) -> None:
        """The control: the new rule must not swallow the one the gate already had."""
        report = self._report(tmp_path, {"green": True, "failed": 0})
        ledger = tmp_path / "ledger.json"

        result = gate.gate_verdict(report, ledger)

        assert not result.blocked, result.reason

    def test_a_report_with_no_baseline_recorded_is_judged_as_before(self, gate, tmp_path) -> None:
        """A session run with `--no-baseline` says nothing about the tree, and never claimed to."""
        report = tmp_path / "mutation_report.json"
        report.write_text(json.dumps({"summary": {"verdict": "PASSED"}, "campaigns": []}), "utf-8")

        assert not gate.gate_verdict(report, tmp_path / "ledger.json").blocked
