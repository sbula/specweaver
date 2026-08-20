# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prose may not call a capability delivered when the matrix says it is not.

A capability's flag lives in `capability_matrix.md`. Its *claims* live everywhere else: a story's
prerequisite line, a queue candidate's Pros, a P-row's owner. Nothing read the second kind.

Measured 2026-08-20, after six capabilities were set back from `✅` to `🔧`: twelve places still
said `✅`, the doc gate passed all twelve, and the Active Routing Queue's first candidate was a
capability that had already been built. A new agent reading the queue would have rebuilt it.

The flag is one fact. Prose asserting a different one is a second copy, and this is the check that
they agree.
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
def check() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_stale_delivered", REPO_ROOT / "scripts" / "check_stale_delivered.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_stale_delivered"] = module
    spec.loader.exec_module(module)
    return module


class TestFlagsFromMatrix:
    def test_it_reads_a_delivered_flag(self, check: ModuleType) -> None:
        flags = check.flags_from("| x | `✅ C-VAL-01`: Constitution | `🔧 D-UI-01`: API |")

        assert flags["C-VAL-01"] == "✅"

    def test_it_reads_an_in_work_flag(self, check: ModuleType) -> None:
        flags = check.flags_from("| x | `✅ C-VAL-01`: Constitution | `🔧 D-UI-01`: API |")

        assert flags["D-UI-01"] == "🔧"

    def test_an_unbuilt_capability_is_read_too(self, check: ModuleType) -> None:
        """`🔜` matters as much as `🔧`: prose calling an unbuilt thing delivered is the same lie."""
        assert check.flags_from("`🔜 A-SENS-02`: Sidecar")["A-SENS-02"] == "🔜"


class TestStaleClaimsIn:
    def test_a_tick_beside_an_in_work_capability_is_stale(self, check: ModuleType) -> None:
        stale = check.stale_claims_in("Prereqs: `D-UI-01` ✅, ready to go", {"D-UI-01": "🔧"})

        assert stale == ["D-UI-01"]

    def test_a_tick_beside_a_delivered_capability_is_fine(self, check: ModuleType) -> None:
        """The control. Flagging every tick would make the check unpassable."""
        assert check.stale_claims_in("Prereqs: `C-VAL-01` ✅", {"C-VAL-01": "✅"}) == []

    def test_the_matrix_row_itself_is_not_a_claim(self, check: ModuleType) -> None:
        """[Hostile] ``🔧 D-UI-01`` is the flag, not a claim about it. Reading the marker as
        prose would make the matrix permanently fail its own check."""
        assert check.stale_claims_in("`🔧 D-UI-01`: Core API", {"D-UI-01": "🔧"}) == []

    def test_a_capability_the_matrix_does_not_know_is_ignored(self, check: ModuleType) -> None:
        """[Graceful] An ID from a doc that predates the matrix must not fail the gate."""
        assert check.stale_claims_in("`Z-GONE-99` ✅", {}) == []

    def test_an_unbuilt_capability_called_delivered_is_stale(self, check: ModuleType) -> None:
        assert check.stale_claims_in("`A-SENS-02` ✅ shipped", {"A-SENS-02": "🔜"}) == ["A-SENS-02"]


class TestMainOnTheRealTree:
    def test_the_repo_has_no_stale_delivered_claims(self, check: ModuleType) -> None:
        assert check.main([]) == 0
