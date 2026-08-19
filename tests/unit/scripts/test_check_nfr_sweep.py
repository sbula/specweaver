# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""The NFR sweep counts only the requirements a test could actually prove. `TECH-017`.

Measured 2026-08-13: 224 NFRs on delivered stories, 37 cited, 187 uncited. Ratcheting that raw
number would have been wrong, and in a specific way — the population is not homogeneous:

* `C-FLOW-05` NFR-1 (*"`llm/` must remain an adapter and forbid `loom/*`"*) is proved by
  `tach check`. Demanding a pytest citation for it invites someone to write a fake one.
* `E-EXEC-01` NFR-6 (*"module <= 300 lines"*) is the `file_sizes` gate.
* `TECH-025` NFR-3 (*"every `Proves:` tag names a test that would fail if the behaviour
  regressed"*) is a rule about tests, not about the product.
* `D-VAL-04` NFR-2 (*"token reductions without decreasing accuracy"*) has no threshold, so no
  test can pass or fail it.

So a row may be excused only by an explicit `[proof: ...]` marker written into the design, and the
sweep counts what is left. The marker is the assertion "a pytest is the wrong instrument here" —
made in the open, in the design, reviewable — rather than a silent exemption in the checker.
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

_TABLE = "| # | NFR | Threshold / Constraint |\n|---|-----|----------------------|\n"


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_nfr_sweep.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("check_nfr_sweep", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_nfr_sweep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sweep() -> ModuleType:
    return _load()


class TestBehaviouralNfrsFromText:
    """`behavioural_nfrs_from_text` — which rows the sweep is entitled to count."""

    def test_an_unmarked_row_is_behavioural(self, sweep: ModuleType) -> None:
        text = _TABLE + "| NFR-1 | Latency | Hydration MUST complete in < 50ms. |\n"
        assert sweep.behavioural_nfrs_from_text(text) == ["NFR-1"]

    @pytest.mark.parametrize(
        "marker",
        [
            "**[proof: arch — tach/lint gate, not pytest]**",
            "**[proof: meta — rule about tests, docs or the diff]**",
            "**[proof: none — unfalsifiable as written]**",
        ],
    )
    def test_every_marker_bucket_excuses_the_row(self, sweep: ModuleType, marker: str) -> None:
        text = _TABLE + f"| NFR-1 | Placement | Must live in `workspace/`. {marker} |\n"
        assert sweep.behavioural_nfrs_from_text(text) == []

    def test_a_marked_row_does_not_excuse_its_neighbours(self, sweep: ModuleType) -> None:
        """The excuse is per row. A marker on NFR-1 must not silently cover NFR-2."""
        text = (
            _TABLE
            + "| NFR-1 | Placement | Must live in `workspace/`. **[proof: arch — tach]** |\n"
            + "| NFR-2 | Latency | Hydration MUST complete in < 50ms. |\n"
        )
        assert sweep.behavioural_nfrs_from_text(text) == ["NFR-2"]

    def test_a_design_with_no_nfr_table_yields_nothing(self, sweep: ModuleType) -> None:
        assert sweep.behavioural_nfrs_from_text("# Design\n\nNo table here.\n") == []


class TestCitedNfrsInTests:
    """`cited_nfrs_in_tests` — a citation must name the story, exactly as the FR sweep requires."""

    def test_a_test_naming_the_story_cites_its_nfr(self, sweep: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "test_x.py").write_text('"""Proves: D-INTL-06 NFR-1."""\n', encoding="utf-8")
        assert sweep.cited_nfrs_in_tests(tmp_path, "D-INTL-06") == {"NFR-1"}

    def test_a_test_not_naming_the_story_cites_nothing(
        self, sweep: ModuleType, tmp_path: Path
    ) -> None:
        """The known blind spot, kept deliberately in step with the FR sweep (`TECH-017` finding 6).

        Widening it here alone would make the two sweeps disagree about what a citation is.
        """
        (tmp_path / "test_x.py").write_text('"""NFR-1: latency under 50ms."""\n', encoding="utf-8")
        assert sweep.cited_nfrs_in_tests(tmp_path, "D-INTL-06") == set()


class TestUncited:
    """`uncited` — the per-story number the ratchet is built from."""

    def test_a_marked_row_never_counts_as_uncited(self, sweep: ModuleType) -> None:
        text = _TABLE + "| NFR-1 | Placement | In `workspace/`. **[proof: arch — tach]** |\n"
        assert sweep.uncited_from(text, cited=set()) == 0

    def test_an_unmarked_uncited_row_counts(self, sweep: ModuleType) -> None:
        text = _TABLE + "| NFR-1 | Latency | Under 50ms. |\n"
        assert sweep.uncited_from(text, cited=set()) == 1

    def test_citing_it_clears_it(self, sweep: ModuleType) -> None:
        text = _TABLE + "| NFR-1 | Latency | Under 50ms. |\n"
        assert sweep.uncited_from(text, cited={"NFR-1"}) == 0


class TestMain:
    """`main` — the gate's exit contract."""

    def test_the_repo_is_at_or_under_its_baseline(self, sweep: ModuleType) -> None:
        assert sweep.main([]) == 0

    def test_list_mode_reports_without_judging(self, sweep: ModuleType) -> None:
        assert sweep.main(["--list"]) == 0


class TestNewSince:
    """The baseline tracks WHICH NFRs are uncited, not how many.

    A count is a budget, and a budget can be spent. Measured 2026-08-19: the repo sat at 120
    uncited against a frozen 138, so eighteen new uncited NFRs could be added while the gate
    reported "none new" — and fourteen were, in one session, by the agent that later found it.
    The headroom belonged to whoever did the cleanup that created it; it was silently transferred
    to whoever came next.

    An identity set cannot be spent. A new uncited NFR is new whatever anyone else fixed.
    """

    def test_a_new_uncited_nfr_is_new_even_when_the_total_falls(self, sweep: ModuleType) -> None:
        """The exact hole. Two rows cleaned, one added: the count improves, and the gate must
        still refuse the addition."""
        before = {"A-AAA-01 NFR-1", "A-AAA-01 NFR-2", "A-AAA-01 NFR-3"}
        after = {"A-AAA-01 NFR-1", "B-BBB-02 NFR-9"}

        assert len(after) < len(before)
        assert sweep.new_since(before, after) == {"B-BBB-02 NFR-9"}

    def test_clearing_rows_alone_is_not_a_regression(self, sweep: ModuleType) -> None:
        """The control: cleanup must stay free."""
        before = {"A-AAA-01 NFR-1", "A-AAA-01 NFR-2"}

        assert sweep.new_since(before, {"A-AAA-01 NFR-1"}) == set()


class TestLoadBaselineIdentities:
    """`write_baseline` / `load_baseline_identities` — the ratchet's memory."""

    def test_an_identity_survives_a_freeze_round_trip(
        self, sweep: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ratchet that cannot reload what it wrote degrades to no ratchet at all."""
        baseline = tmp_path / "nfr_uncited.json"
        monkeypatch.setattr(sweep, "BASELINE", baseline)
        identities = {"A-AAA-01 NFR-1", "B-BBB-02 NFR-9"}

        sweep.write_baseline(identities)

        assert sweep.load_baseline_identities() == identities

    def test_a_missing_baseline_admits_it_rather_than_passing_everything(
        self, sweep: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty set would make every existing row look new; `None` lets the caller say so."""
        monkeypatch.setattr(sweep, "BASELINE", tmp_path / "absent.json")

        assert sweep.load_baseline_identities() is None


class TestCensusIdentities:
    """`census_identities` — the live read the gate judges."""

    def test_the_live_repo_reports_identities_not_just_a_number(self, sweep: ModuleType) -> None:
        """Guards the wiring: `census_identities` must actually read the tree."""
        identities = sweep.census_identities()

        assert identities
        assert all(" NFR-" in i for i in identities)
