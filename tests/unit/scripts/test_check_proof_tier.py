# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A delivered integration contract must cite integration or e2e tests. `TECH-017`.

The ticket's Approach 3, built as a **repo-wide sweep with no story argument** — deliberately, and
for a reason measured on 2026-08-13: `check_story_preconditions.py` already contains a check that
fails an `INT-US-NN` marked delivered whose proof is `[Pending]`, and it would have caught
`INT-US-25` since the day it was written. It never did, because it only runs when a human passes
that story ID and nobody ever passed `INT-US-25`. A guardrail that must be invoked to fire is a
guardrail that reports success by not running.

So this one takes no arguments, judges every contract in the tree, and runs in the `doc` gate.
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


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_proof_tier.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("check_proof_tier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_proof_tier"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load()


CONTRACT = """\
# US-99: Example - Integration Contracts

## Base Story Contract (`INT-US-99`)
* **Status:** ✅ Complete (2026-01-01)
* **Integration Description:** Something.
* **Verifiable Proof:** `tests/e2e/capabilities/test_journey_e2e.py` - 9 scenarios.

## Sub-Story Add-Ons

* **First Add-On (`INT-US-99-SF01`)**
  * **Status:** ✅ Complete
  * **Integration Description:** Something else.
  * **Verifiable Proof:** Covered by the `Widget` suite, `tests/unit/widgets/test_widget.py`.

* **Second Add-On (`INT-US-99-SF02`)**
  * **Status:** ⬜ Pending
  * **Integration Description:** [Pending definition...]
  * **Verifiable Proof:** [Pending]

* **Third Add-On (`INT-US-99-SF03`)**
  * **Status:** ✅ Complete
  * **Integration Description:** Something more.
  * **Verifiable Proof:** Covered by E2E tests in `tests/e2e/capabilities/core/` and `pytest -m integration`.
"""


class TestContractEntries:
    def test_every_declared_entry_is_found(self, mod: ModuleType) -> None:
        """The base contract is a `##` heading; add-ons are `*` bullets. Both carry an ID."""
        ids = [e.entry_id for e in mod.contract_entries(CONTRACT, Path("US-99_integration.md"))]

        assert ids == ["INT-US-99", "INT-US-99-SF01", "INT-US-99-SF02", "INT-US-99-SF03"]

    def test_an_entry_carries_its_own_status_and_not_its_neighbour_s(self, mod: ModuleType) -> None:
        """The whole point of splitting into blocks: a greedy match spans into the next add-on."""
        by_id = {
            e.entry_id: e for e in mod.contract_entries(CONTRACT, Path("US-99_integration.md"))
        }

        assert by_id["INT-US-99-SF02"].delivered is False
        assert by_id["INT-US-99-SF01"].delivered is True

    def test_the_title_is_captured_because_ids_are_not_unique(self, mod: ModuleType) -> None:
        """`INT-US-05-SUB` names two different delivered add-ons, so the ID alone cannot key them."""
        by_id = {
            e.entry_id: e for e in mod.contract_entries(CONTRACT, Path("US-99_integration.md"))
        }

        assert by_id["INT-US-99-SF01"].title == "First Add-On"


class TestClassify:
    def test_an_e2e_proof_passes(self, mod: ModuleType) -> None:
        assert mod.classify("`tests/e2e/capabilities/test_x_e2e.py` - 9 scenarios") == mod.OK

    def test_an_integration_proof_passes(self, mod: ModuleType) -> None:
        assert mod.classify("`tests/integration/core/test_x.py` (33)") == mod.OK

    def test_a_unit_only_proof_fails(self, mod: ModuleType) -> None:
        """The exact defect: an integration contract whose proof is unit tests."""
        assert (
            mod.classify("the `Widget` suite, `tests/unit/widgets/test_widget.py`") == mod.UNIT_ONLY
        )

    def test_a_mixed_proof_passes(self, mod: ModuleType) -> None:
        """Unit tests inside an integration story are legitimate to fill a narrow gap."""
        proof = "`tests/unit/a/test_a.py` plus `tests/e2e/b/test_b_e2e.py`"

        assert mod.classify(proof) == mod.OK

    def test_a_directory_without_a_file_fails(self, mod: ModuleType) -> None:
        """`tests/e2e/capabilities/core/` names a place, not a proof. Nothing pins what runs."""
        proof = "Covered by E2E tests in `tests/e2e/capabilities/core/` and `pytest -m integration`"

        assert mod.classify(proof) == mod.NO_TEST_FILE

    def test_a_bare_pytest_marker_fails(self, mod: ModuleType) -> None:
        assert mod.classify("Covered by `pytest -m integration`.") == mod.NO_TEST_FILE

    def test_a_pending_placeholder_fails(self, mod: ModuleType) -> None:
        assert mod.classify("[Pending]") == mod.NO_TEST_FILE


class TestViolations:
    def test_a_pending_entry_is_never_judged(self, mod: ModuleType) -> None:
        """A tier supplies defaults, never prohibitions: undelivered work owes no proof yet."""
        found = mod.violations_in(CONTRACT, Path("US-99_integration.md"))

        assert all(v.entry_id != "INT-US-99-SF02" for v in found)

    def test_the_delivered_unit_only_entry_is_reported(self, mod: ModuleType) -> None:
        found = {
            v.entry_id: v.verdict for v in mod.violations_in(CONTRACT, Path("US-99_integration.md"))
        }

        assert found["INT-US-99-SF01"] == mod.UNIT_ONLY

    def test_the_delivered_directory_only_entry_is_reported(self, mod: ModuleType) -> None:
        found = {
            v.entry_id: v.verdict for v in mod.violations_in(CONTRACT, Path("US-99_integration.md"))
        }

        assert found["INT-US-99-SF03"] == mod.NO_TEST_FILE

    def test_a_proven_entry_is_not_reported(self, mod: ModuleType) -> None:
        found = {v.entry_id for v in mod.violations_in(CONTRACT, Path("US-99_integration.md"))}

        assert "INT-US-99" not in found

    def test_the_key_distinguishes_two_entries_sharing_an_id(self, mod: ModuleType) -> None:
        """`INT-US-05-SUB` is used twice. Keying on the ID alone would freeze one and hide one."""
        text = CONTRACT.replace("INT-US-99-SF03", "INT-US-99-SF01")

        keys = {v.key for v in mod.violations_in(text, Path("US-99_integration.md"))}

        assert len(keys) == 2, keys


class TestMain:
    def test_the_repo_is_at_its_frozen_baseline(self, mod: ModuleType) -> None:
        """The ratchet's whole contract: known debt frozen, regressions blocked."""
        assert mod.main([]) == 0

    def test_every_frozen_entry_still_exists(self, mod: ModuleType) -> None:
        """A baseline naming an entry that is gone hides a real violation behind a stale key."""
        live = {v.key for v in mod.all_violations()}
        stale = set(mod.load_baseline()) - live

        assert not stale, f"baseline entries no longer present: {sorted(stale)}"

    def test_every_frozen_entry_states_why(self, mod: ModuleType) -> None:
        """A frozen violation with no owner is a suppression, not a ratchet."""
        for key, entry in mod.load_baseline().items():
            assert entry.get("reason"), f"{key} is frozen with no reason"
