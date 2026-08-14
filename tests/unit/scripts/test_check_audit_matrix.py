# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The audit matrix must stay a measurement, not decay into a snapshot.

`TECH-017` produced 64 claims with verdicts and evidence, and then had no way to prove it had. Its
FRs name **"Auditor"** as the Actor — they describe a process and emit a document, so
`check_fr_coverage.py TECH-017` reported all six as `NO TEST` and blocked the ticket. That is the
right answer to the wrong question: the outputs *are* checkable, just not as behaviour of `src/`.

What this guards, and why each rule earns its place:

* **Every claim carries a recognised verdict** (`FR-2`). A row with prose where a verdict belongs is
  how an audit quietly loses a claim.
* **Every `proven` names a tier or a test function** (`FR-2`, `FR-3`). The audit's founding defect
  was file-level citation — 8 of `INT-US-21`'s 10 requirements credited to a file that asserted
  nothing about them.
* **The header's tally matches the table** (`FR-1`). Both were hand-maintained through four
  sub-features; a header that drifts is a lie told at the top of the document.
* **Claims never disappear and `unproven` never rises** (`FR-4`). The count must fall *by work, not
  by re-wording* — which is exactly what a ratchet is for, and `NFR-1` forbids the alternative.

The back-reference case is why the evidence rule accepts a tier word **or** a test name rather than
demanding a test name. Five proven rows legitimately say *"same test"* or *"the cited file"*,
pointing at the row above; requiring a function name there would force copy-paste, and whitelisting
the prose would be brittle. Both spellings were measured against the real matrix before choosing.

Proves: TECH-017 FR-1, FR-2, FR-3, FR-4, FR-6, NFR-2.

`NFR-2` (*every verdict names a test function or states that none exists*) is rule 2, and is the
only one of the four NFRs a pytest can own; the other three constrain the auditor's editing,
filing and committing behaviour and are marked `[proof: meta]` in the design.

`FR-5` is **not** claimed, and no longer exists. It constrained what the auditor may file, and the
artifact that would prove it is the absence of tickets — a historical fact, not a property of any
document. Citing it here to clear the coverage check would have been exactly the loose credit
`TECH-017` existed to remove, so it was **descoped to `AD-2`** on 2026-08-14 instead.
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

_HEAD = "| # | Claim | Verdict | Evidence |\n|---|---|---|---|\n"
#: The `FR-6` table's presence is itself a rule, so fixtures for the OTHER rules must carry it or
#: they trip it and mask what they meant to assert.
_FR6 = "| Capability | Finding | Surfaced by | State |\n"


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_audit_matrix.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("check_audit_matrix", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_audit_matrix"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load()


class TestClaimRows:
    """`claim_rows` — find the claims and ignore every other table in the document."""

    def test_it_reads_id_verdict_and_evidence(self, mod: ModuleType) -> None:
        text = _HEAD + "| C1 | It works. | `proven` | e2e — `test_a` proves it. |\n"
        rows = mod.claim_rows(text)
        assert len(rows) == 1
        assert rows[0].claim_id == "C1"
        assert rows[0].verdict == "proven"

    def test_other_tables_are_not_claims(self, mod: ModuleType) -> None:
        """The matrix carries coverage tables, capability findings and a tally, all pipe tables.

        Only `C<n>`-led rows are claims. Keying on 'starts with a pipe' would sweep the lot in.
        """
        text = "| `D-INTL-01` | A finding. | `INT-US-03` | open |\n| Entry | 1 | 2 | e2e | 3 |\n"
        assert mod.claim_rows(text) == []

    def test_a_verdict_with_a_trailing_qualifier_still_parses(self, mod: ModuleType) -> None:
        """`INT-US-24` C5 reads ``unproven` — **reason narrowed by SF-04**`. Real, and must parse."""
        text = (
            _HEAD + "| C5 | Journey. | `unproven` — **reason narrowed** | integration — none. |\n"
        )
        rows = mod.claim_rows(text)
        assert len(rows) == 1
        assert rows[0].verdict == "unproven"


class TestViolations:
    """`violations` — the six rules, each stated as a defect someone actually shipped."""

    def test_an_unrecognised_verdict_is_a_violation(self, mod: ModuleType) -> None:
        text = _HEAD + "| C1 | It works. | probably fine | e2e — `test_a`. |\n"
        assert any("verdict" in v for v in mod.violations(text))

    def test_proven_without_a_tier_or_a_test_name_is_a_violation(self, mod: ModuleType) -> None:
        """A `proven` that names nothing is the file-level citation this audit exists to remove."""
        text = _HEAD + "| C1 | It works. | `proven` | It is obviously fine and always has been. |\n"
        assert any("names no tier" in v for v in mod.violations(text))

    def test_proven_naming_only_a_tier_is_accepted(self, mod: ModuleType) -> None:
        """The back-reference case: 'same test as the row above' is legitimate evidence."""
        text = (
            _FR6
            + _HEAD
            + "| C1 | It works. | `proven` | e2e — same test as C1 above, read-verified. |\n"
        )
        assert mod.violations(text) == []

    def test_proven_naming_only_a_test_function_is_accepted(self, mod: ModuleType) -> None:
        text = (
            _FR6
            + _HEAD
            + "| C1 | It works. | `proven` | `test_the_loop_goes_green` covers it fully. |\n"
        )
        assert mod.violations(text) == []

    def test_a_header_tally_that_disagrees_with_the_table_is_a_violation(
        self, mod: ModuleType
    ) -> None:
        """Both are hand-maintained. A header that drifts is a lie told at the top of the file."""
        text = "| `proven` | 7 |\n" + _HEAD + "| C1 | Works. | `proven` | e2e — `test_a`. |\n"
        assert any("header" in v for v in mod.violations(text))

    def test_a_header_tally_that_agrees_is_not_a_violation(self, mod: ModuleType) -> None:
        text = (
            "| `proven` | 1 |\n" + _FR6 + _HEAD + "| C1 | Works. | `proven` | e2e — `test_a`. |\n"
        )
        assert mod.violations(text) == []


class TestViolationsTierAndFindings:
    """The two rules that own `FR-3` and `FR-6`, added after the first four were measured.

    `FR-6` is the diagnostic half of the audit — where a contract's gap traces to an incomplete
    capability rather than to the contract. It is the half that goes missing, which is why its
    table's existence is asserted rather than assumed.
    """

    def test_a_proof_row_with_no_recognised_tier_is_a_violation(self, mod: ModuleType) -> None:
        """`FR-3`. This is the gap `check_proof_tier` cannot see: it reads the contract's own claim
        about its proof, never the audit's reading of it."""
        text = _FR6 + "| `tests/unit/a.py` | smoke | 3 |\n"
        assert any("tier" in v for v in mod.violations(text))

    def test_the_three_real_tiers_are_accepted(self, mod: ModuleType) -> None:
        text = _FR6 + "".join(
            f"| `tests/x/a.py` | {tier} | 3 |\n" for tier in ("unit", "integration", "e2e")
        )
        assert mod.violations(text) == []

    def test_a_missing_capability_findings_table_is_a_violation(self, mod: ModuleType) -> None:
        text = _HEAD + "| C1 | Works. | `proven` | e2e — `test_a`. |\n"
        assert any("FR-6" in v for v in mod.violations(text))

    def test_a_finding_naming_no_surfacing_entry_is_a_violation(self, mod: ModuleType) -> None:
        """A finding nobody can trace back to the entry that found it is one hop from useless."""
        text = _FR6 + "| `D-INTL-01` | A finding. |  | open |\n"
        assert any("surfaced" in v for v in mod.violations(text))


class TestRatchet:
    """`ratchet_failures` — claims may not vanish and `unproven` may not rise."""

    def test_a_lost_claim_is_a_failure(self, mod: ModuleType) -> None:
        """`NFR-1`: a delivered contract is immutable, so a claim can only ever be ADDED."""
        assert any(
            "claims" in f for f in mod.ratchet_failures({"claims": 64, "unproven": 9}, 63, 9)
        )

    def test_a_risen_unproven_count_is_a_failure(self, mod: ModuleType) -> None:
        """`FR-4`: the count falls by work, not by re-wording. Rising means a proof was lost."""
        assert any(
            "unproven" in f for f in mod.ratchet_failures({"claims": 64, "unproven": 9}, 64, 10)
        )

    def test_a_fallen_unproven_count_is_not_a_failure(self, mod: ModuleType) -> None:
        assert mod.ratchet_failures({"claims": 64, "unproven": 9}, 64, 4) == []

    def test_more_claims_is_not_a_failure(self, mod: ModuleType) -> None:
        """The count rose twice during the audit as contracts were re-read in full. That is work."""
        assert mod.ratchet_failures({"claims": 64, "unproven": 9}, 70, 9) == []


class TestViolationsOnTheRealMatrix:
    """The document in the tree must pass its own check."""

    def test_the_matrix_is_clean(self, mod: ModuleType) -> None:
        assert mod.violations(mod.matrix_text()) == []

    def test_the_matrix_is_on_baseline(self, mod: ModuleType) -> None:
        rows = mod.claim_rows(mod.matrix_text())
        unproven = sum(1 for r in rows if r.verdict == "unproven")
        assert mod.ratchet_failures(mod.load_baseline(), len(rows), unproven) == []

    def test_a_checker_that_cannot_find_its_subject_fails(self, mod: ModuleType) -> None:
        """`TECH-032`: an absent subject reported as a clean run is a vacuous proof in the gate."""
        assert mod.main(["--matrix", "/nonexistent/matrix.md"]) == 2
