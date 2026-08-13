# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""The FR sweep counts requirements, and only on delivered work. `TECH-047`.

A list of blocked capability names moves only when a whole capability is finished, which is never —
so the ratchet holds one number, the count of requirements cited by no test. That number falls when
a real test lands and rises when a new requirement ships untested.

It counts **delivered** stories only, and that was not the first design. Counting every design
punished the one behaviour this repo most wants: adding the fan-out requirements to `C-FLOW-12` —
unbuilt, and the new owner of `C-INTL-01`'s descoped `FR-3` — raised the total and the ratchet
blocked the commit that improved the specification.
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
    path = REPO_ROOT / "scripts" / "check_fr_sweep.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("check_fr_sweep", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_fr_sweep"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sweep() -> ModuleType:
    return _load()


class TestDeliveredStories:
    def test_a_delivered_marker_is_read(self, sweep: ModuleType) -> None:
        assert "C-INTL-01" in sweep.delivered_stories()

    def test_an_unbuilt_capability_is_not(self, sweep: ModuleType) -> None:
        """`C-FLOW-12` declares four FRs and is unbuilt — its uncited FRs are expected, not debt."""
        assert "C-FLOW-12" not in sweep.delivered_stories()

    def test_the_set_is_not_empty(self, sweep: ModuleType) -> None:
        """A parse failure would silently empty the census and read as perfect coverage."""
        assert len(sweep.delivered_stories()) > 20


class TestCensus:
    def test_it_omits_undelivered_designs(self, sweep: ModuleType) -> None:
        assert "C-FLOW-12" not in sweep.census()

    def test_every_counted_story_is_delivered(self, sweep: ModuleType) -> None:
        delivered = sweep.delivered_stories()

        assert all(story in delivered for story in sweep.census())

    def test_counts_are_positive(self, sweep: ModuleType) -> None:
        """A zero would mean a clean story was listed, which the census must omit entirely."""
        assert all(count > 0 for count in sweep.census().values())


class TestMain:
    def test_the_repo_is_at_its_frozen_baseline(self, sweep: ModuleType) -> None:
        assert sweep.main([]) == 0

    def test_the_baseline_is_not_stale(self, sweep: ModuleType) -> None:
        """A baseline above the live total would silently absorb a future regression."""
        assert sweep.load_baseline() == sum(sweep.census().values())


class TestDanglingCitations:
    """`dangling_citations` — a `Proves:` tag naming a requirement that does not exist.

    A tag is a human's judgment written down, so the machine cannot check it is TRUE. It can check
    the tag is not nonsense, and that is worth doing before anyone tags in bulk: a mistyped tag
    credits nothing and says nothing, which is the failure mode this repo keeps meeting —
    *"a check that silently does not run is indistinguishable from one that passes."*

    Zero-padding is the specific trap. Designs declare `NFR-3`; a tag reading `NFR-03` is a
    different string, so it silently credits nothing at all.
    """

    def test_a_tag_matching_the_design_is_not_dangling(self, sweep: ModuleType) -> None:
        declared = {"AA-BB-01": {"FR-1", "NFR-3"}}
        tags = {"AA-BB-01": {"FR-1"}}
        assert sweep.dangling_citations(tags, declared) == []

    def test_a_zero_padded_tag_is_reported(self, sweep: ModuleType) -> None:
        declared = {"AA-BB-01": {"NFR-3"}}
        tags = {"AA-BB-01": {"NFR-03"}}
        assert sweep.dangling_citations(tags, declared) == [("AA-BB-01", "NFR-03")]

    def test_a_tag_for_an_undeclared_requirement_is_reported(self, sweep: ModuleType) -> None:
        declared = {"AA-BB-01": {"FR-1"}}
        tags = {"AA-BB-01": {"FR-9"}}
        assert sweep.dangling_citations(tags, declared) == [("AA-BB-01", "FR-9")]

    def test_a_tag_naming_an_unknown_story_is_reported(self, sweep: ModuleType) -> None:
        assert sweep.dangling_citations({"NOPE-99": {"FR-1"}}, {}) == [("NOPE-99", "FR-1")]

    def test_the_repo_has_none(self, sweep: ModuleType) -> None:
        """Zero tolerance, not a ratchet: a dangling citation is never acceptable debt to freeze."""
        assert sweep.dangling_citations(sweep.all_strict_tags(), sweep.all_declared()) == []
