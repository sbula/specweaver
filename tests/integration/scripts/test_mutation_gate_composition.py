# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`record_run` then `gate_verdict` — the only order in which either is ever used. TECH-056.

Proves: TECH-056 FR-1, NFR-1, NFR-2

`tests/unit/scripts/test_mutation_gate.py` covers both halves and both are correct. `gate_verdict`
blocks on an empty ledger and clears on a dispositioned entry; `record_run` starts a new finding at
`runs: 1`, increments a returning one, prunes a departed one. Every one of those assertions passed
while the gate could not fire.

**The defect lived only in the composition.** `mutation.py::main` calls `record_run` at the end of
the session that discovered the findings, and `record_run` writes `{"runs": 1}` with no disposition;
`gate_verdict` then read *presence in the ledger* as "a human has looked at this". So the run that
found a real survival marked it read, and the morning gate reported *"every finding carries a
disposition"* about an entry carrying none. Nothing in either unit test could see it, because each
constructs the ledger it wants instead of letting the other half build one.

Integration tier for exactly that reason: the seam is two functions and a file, and the file is the
only place the misunderstanding was visible.

**No e2e.** The subprocess path is one `argparse` hop above these calls and is already covered by
`test_mutation_seam.py::TestReportLedgerGateChain`; an e2e here would re-run that with a different
verdict and prove nothing this file does not.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]

FINDING = "TECH-999 FR-1 a-real-survival"


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


def _session_report(tmp_path: Path, verdict: str = "UNPROTECTED") -> Path:
    """What a corpus session leaves behind when a mutant survives."""
    path = tmp_path / "mutation_report.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "session": {"head": "abc1234"},
                "mutants": [{"id": FINDING, "verdict": verdict}],
            }
        ),
        encoding="utf-8",
    )
    return path


def _entries(ledger: Path) -> dict[str, Any]:
    return json.loads(ledger.read_text(encoding="utf-8"))["findings"]


class TestASessionCannotMarkItsOwnFindingsAsRead:
    """FR-1 — the defect, stated as the sequence that produces it."""

    def test_the_gate_still_blocks_after_the_session_recorded_the_finding(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] the whole ticket.

        Step 2 is not a test contrivance — it is the last thing `mutation.py::main` does on every
        run, before anybody sees the report.
        """
        report = _session_report(tmp_path)
        ledger = tmp_path / "ledger.json"

        gate.record_run(report, ledger)
        verdict = gate.gate_verdict(report, ledger)

        assert verdict.blocked is True, (
            "the session recorded its own finding and the gate accepted that as a human having "
            f"read it; ledger holds {_entries(ledger)}"
        )
        assert FINDING in verdict.unconfirmed

    def test_recording_the_same_finding_twice_does_not_clear_it(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] a finding that survives a second night is more urgent, not less.

        Under the defect this was the shape that read worst: `runs: 2` — evidence the problem is
        persisting — was itself the reason the gate stayed quiet.
        """
        report = _session_report(tmp_path)
        ledger = tmp_path / "ledger.json"

        gate.record_run(report, ledger)
        gate.record_run(report, ledger)

        assert _entries(ledger)[FINDING]["occurrences"] == 2
        assert gate.gate_verdict(report, ledger).blocked is True

    def test_a_broken_mutant_is_treated_the_same_way(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] `BROKEN` blocks too — a mutant that did not import measured nothing, and
        "we learned nothing about this claim" is not a state to walk past silently."""
        report = _session_report(tmp_path, verdict="UNMEASURED")
        ledger = tmp_path / "ledger.json"

        gate.record_run(report, ledger)

        assert gate.gate_verdict(report, ledger).blocked is True


class TestConfirmingIsWhatClearsIt:
    """NFR-1 — and the documented route must be the only one needed."""

    def test_the_gate_clears_once_a_human_confirms(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Happy] `--confirm … --as … --why …` on a ledger built by the session itself.

        The bootstrap case: a first-ever finding, in a ledger no human has touched, cleared by the
        documented command and nothing else. If this needed a hand-edited file the gate would be
        switched off within a week.
        """
        report = _session_report(tmp_path)
        ledger = tmp_path / "ledger.json"
        gate.record_run(report, ledger)
        assert gate.gate_verdict(report, ledger).blocked is True

        gate.confirm(ledger, FINDING, disposition="will-fix", why="narrowing the scope first")

        assert gate.gate_verdict(report, ledger).blocked is False

    def test_confirming_preserves_how_long_the_finding_has_been_here(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """NFR-2 — deciding what to do about a finding must not reset its age.

        That number is the only pressure on a `will-fix` nobody gets to, so a fix that cleared the
        gate by forgetting the count would trade one silence for another.
        """
        report = _session_report(tmp_path)
        ledger = tmp_path / "ledger.json"
        gate.record_run(report, ledger)
        gate.record_run(report, ledger)

        gate.confirm(ledger, FINDING, disposition="will-fix", why="scheduled")

        assert _entries(ledger)[FINDING]["occurrences"] == 2
        assert gate.gate_verdict(report, ledger).blocked is False

    def test_a_later_session_keeps_the_disposition_and_the_gate_stays_clear(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] the night after a confirmation.

        `record_run` must fold the returning finding into the existing entry rather than replacing
        it — otherwise every confirmed finding would re-block the next morning, and the disposition
        would be worth nothing.
        """
        report = _session_report(tmp_path)
        ledger = tmp_path / "ledger.json"
        gate.record_run(report, ledger)
        gate.confirm(ledger, FINDING, disposition="equivalent", why="no observable change")

        gate.record_run(report, ledger)

        assert gate.latest_disposition(_entries(ledger)[FINDING]) == "equivalent"
        assert gate.gate_verdict(report, ledger).blocked is False
