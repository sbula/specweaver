# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the delivered-claim guard (`scripts/check_delivered_claims.py`).

Proves: TECH-053 FR-1, TECH-053 FR-2, TECH-053 FR-3, TECH-053 NFR-1, TECH-053 NFR-3

`TECH-053`. Two ways a `✅` can mean nothing: an add-on group whose flag disagrees with its own
children, and a capability marked delivered that `check_fr_sweep.py` cannot see — no design
document, or a design declaring no FRs, either of which scores **zero uncited FRs** and reads as
perfect.

**Every rule is driven against synthetic registries.** The live repo has 22 findings and 6 corrected
groups; asserting against that state would pass for as long as nobody changed it and prove nothing
about the rule. The two live-repo assertions are at the bottom, and they check the ratchet and the
group rule rather than standing in for the rules themselves.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cdc() -> ModuleType:
    return _load("check_delivered_claims")


_FR_TABLE = """
## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Something | System | Does it | It happened |
"""


def _registry(root: Path, *, matrix: str, roadmap: str = "", designs: dict[str, str] | None = None):
    """Build a throwaway `docs/roadmap/` — matrix, master roadmap, and feature designs."""
    roadmap_dir = root / "docs" / "roadmap"
    (roadmap_dir / "features" / "topic_01").mkdir(parents=True, exist_ok=True)
    (roadmap_dir / "capability_matrix.md").write_text(matrix, encoding="utf-8")
    (roadmap_dir / "master_story_roadmap.md").write_text(roadmap, encoding="utf-8")
    for cap, body in (designs or {}).items():
        d = roadmap_dir / "features" / "topic_01" / cap
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{cap}_design.md").write_text(body, encoding="utf-8")
    return roadmap_dir


class TestUnprovenGreenFindings:
    """`TECH-060` FR-4 — a green unit holding closed features with NO integration contract.

    The distinctive word is **no**. `group_flag_findings` and `story_flag_findings` compare a flag
    with the children that are present, so an unchecked integration entry already forces `🟡` and is
    covered. Neither can see a child that was never written — and a check that never looks is
    indistinguishable from one that passes, which is this module's own founding argument.

    Zero-tolerance, not ratcheted. The design assumed it would fire on all 27 migration entries on
    day one; measured after they were registered, it fires on none, because those units are `🟡` or
    their entries are `[ ]`. Nothing to carry forward.
    """

    _MATRIX = "| **DAL-C** | `✅ C-FLOW-01`: One<br>`✅ C-FLOW-02`: Two |\n"

    def test_a_green_group_with_closed_work_and_no_contract_is_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        roadmap = (
            "### 🟡 US-1: Story\n"
            "*   **Sub-Story Add-Ons:**\n"
            "    *   🟢 **Some Group:**\n"
            "        *   `✅` **C-FLOW-01:** One\n"
        )
        root = _registry(tmp_path, matrix=self._MATRIX, roadmap=roadmap)
        found = cdc.unproven_green_findings(root)
        assert len(found) == 1
        assert "Some Group" in found[0].unit

    def test_a_green_group_with_a_delivered_contract_passes(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        roadmap = (
            "### 🟡 US-1: Story\n"
            "*   **Sub-Story Add-Ons:**\n"
            "    *   🟢 **Some Group:**\n"
            "        *   `✅` **INT-US-01-SF01:** Some Group\n"
            "        *   `✅` **C-FLOW-01:** One\n"
        )
        root = _registry(tmp_path, matrix=self._MATRIX, roadmap=roadmap)
        assert cdc.unproven_green_findings(root) == []

    def test_a_green_group_with_nothing_closed_owes_nothing(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """A group can be green over dependency references alone; it holds no closed capability."""
        roadmap = (
            "### 🟡 US-1: Story\n"
            "*   **Sub-Story Add-Ons:**\n"
            "    *   🟢 **Some Group:**\n"
            "        *   `✅` **US-4 Core** *(a dependency, not a capability)*\n"
        )
        root = _registry(tmp_path, matrix=self._MATRIX, roadmap=roadmap)
        assert cdc.unproven_green_findings(root) == []

    def test_a_non_green_group_is_not_judged(self, cdc: ModuleType, tmp_path: Path) -> None:
        """`🟡` already says the work is unfinished. The rule is about a green claim."""
        roadmap = (
            "### 🟡 US-1: Story\n"
            "*   **Sub-Story Add-Ons:**\n"
            "    *   🟡 **Some Group:**\n"
            "        *   `✅` **C-FLOW-01:** One\n"
        )
        root = _registry(tmp_path, matrix=self._MATRIX, roadmap=roadmap)
        assert cdc.unproven_green_findings(root) == []

    def test_a_green_story_with_closed_mvs_and_no_contract_is_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        roadmap = (
            "### 🟢 US-1: Story\n*   **Core Required (MVS):**\n    *   `✅` **C-FLOW-01:** One\n"
        )
        root = _registry(tmp_path, matrix=self._MATRIX, roadmap=roadmap)
        found = cdc.unproven_green_findings(root)
        assert len(found) == 1
        assert found[0].unit == "US-1"

    def test_a_green_story_with_its_base_contract_passes(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        roadmap = (
            "### 🟢 US-1: Story\n"
            "*   **Core Required (MVS):**\n"
            "    *   `✅` **INT-US-01:** Base Integration Contract\n"
            "    *   `✅` **C-FLOW-01:** One\n"
        )
        root = _registry(tmp_path, matrix=self._MATRIX, roadmap=roadmap)
        assert cdc.unproven_green_findings(root) == []

    def test_a_migration_entry_is_not_the_contract(self, cdc: ModuleType, tmp_path: Path) -> None:
        """A `-MIG` entry is the task of building the inventory, not the proof it produced."""
        roadmap = (
            "### 🟢 US-1: Story\n"
            "*   **Core Required (MVS):**\n"
            "    *   `✅` **INT-US-01-MIG:** Migration\n"
            "    *   `✅` **C-FLOW-01:** One\n"
        )
        root = _registry(tmp_path, matrix=self._MATRIX, roadmap=roadmap)
        assert len(cdc.unproven_green_findings(root)) == 1

    def test_the_live_registry_is_clean(self, cdc: ModuleType) -> None:
        """Zero-tolerance: `TECH-060` FR-2/FR-3 brought the registry to consistency."""
        assert cdc.unproven_green_findings(REPO_ROOT / "docs" / "roadmap") == []


class TestGroupFlagFindings:
    """FR-1 — a group's flag against its own children."""

    _CHILDREN = (
        "    *   {flag} **Some Group:**\n"
        "        *   `✅` **C-FLOW-01:** One\n"
        "        *   `[ ]` **C-FLOW-02:** Two\n"
    )

    def test_a_group_with_some_children_done_must_be_amber(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """The shape that started this: 🔴 while a capability under it is ✅."""
        root = _registry(tmp_path, matrix="", roadmap=self._CHILDREN.format(flag="🔴"))

        assert [f.reason for f in cdc.group_flag_findings(root)] == ["1 of 2 done, so 🟡 not 🔴"]

    def test_a_group_with_every_child_done_must_be_green(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        body = (
            "    *   🟡 **Some Group:**\n"
            "        *   `✅` **C-FLOW-01:** One\n"
            "        *   `✅` **C-FLOW-02:** Two\n"
        )
        root = _registry(tmp_path, matrix="", roadmap=body)

        assert [f.reason for f in cdc.group_flag_findings(root)] == ["2 of 2 done, so 🟢 not 🟡"]

    def test_a_group_that_agrees_with_its_children_is_not_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        root = _registry(tmp_path, matrix="", roadmap=self._CHILDREN.format(flag="🟡"))

        assert cdc.group_flag_findings(root) == []

    def test_a_parked_group_is_left_alone(self, cdc: ModuleType, tmp_path: Path) -> None:
        """🔵 means *on hold* — a deliberate statement about intent, not about progress.

        Deriving it from children would silently un-park anything with one delivered dependency,
        which is a decision the flag exists to record.
        """
        root = _registry(tmp_path, matrix="", roadmap=self._CHILDREN.format(flag="🔵"))

        assert cdc.group_flag_findings(root) == []

    def test_a_group_with_no_children_is_not_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] an empty group states nothing to disagree with."""
        root = _registry(tmp_path, matrix="", roadmap="    *   🔴 **Empty Group:**\n")

        assert cdc.group_flag_findings(root) == []


class TestUnverifiableFindings:
    """FR-2, FR-3 — a `✅` the FR sweep cannot see."""

    _MATRIX = "| DAL-C | `✅ C-FLOW-01`: One<br>`✅ C-FLOW-02`: Two<br>`🔜 C-FLOW-03`: Three |"

    def test_a_delivered_capability_with_no_design_is_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        root = _registry(tmp_path, matrix=self._MATRIX, designs={"C-FLOW-02": _FR_TABLE})

        found = {f.capability: f.reason for f in cdc.unverifiable_findings(root)}
        assert found == {"C-FLOW-01": "no design document"}

    def test_a_delivered_capability_whose_design_declares_no_frs_is_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """The subtler half: a design exists, so the sweep reads zero uncited FRs and is content."""
        root = _registry(
            tmp_path,
            matrix=self._MATRIX,
            designs={"C-FLOW-01": _FR_TABLE, "C-FLOW-02": "# Design\n\nNo requirements here.\n"},
        )

        found = {f.capability: f.reason for f in cdc.unverifiable_findings(root)}
        assert found == {"C-FLOW-02": "design declares no FRs"}

    def test_the_two_causes_are_named_separately(self, cdc: ModuleType, tmp_path: Path) -> None:
        """FR-3 — *write the design* and *declare the FRs* are different jobs."""
        root = _registry(
            tmp_path, matrix=self._MATRIX, designs={"C-FLOW-02": "# Design\n\nNothing.\n"}
        )

        reasons = {f.reason for f in cdc.unverifiable_findings(root)}
        assert reasons == {"no design document", "design declares no FRs"}

    def test_an_undelivered_capability_is_not_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] `🔜 C-FLOW-03` has no design either, and is not claiming anything."""
        root = _registry(
            tmp_path, matrix=self._MATRIX, designs={"C-FLOW-01": _FR_TABLE, "C-FLOW-02": _FR_TABLE}
        )

        assert cdc.unverifiable_findings(root) == []

    def test_frs_declared_as_bullets_count_as_declared(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] a design may list its FRs as bullets rather than a table, and two do.

        The first draft of this check read table rows only and reported `C-SENS-02` (5 FRs) and
        `D-SENS-03` (7 FRs) as declaring none — twelve requirements erased by a second parser
        disagreeing with the one already in the repo. It now loads `check_fr_coverage`'s grammar
        instead of restating it, and this pins that.
        """
        bullets = "## Functional Requirements\n\n- **FR-1**: the thing\n- **FR-2**: the other\n"
        root = _registry(
            tmp_path, matrix=self._MATRIX, designs={"C-FLOW-01": bullets, "C-FLOW-02": _FR_TABLE}
        )

        assert cdc.unverifiable_findings(root) == []

    def test_a_delivered_capability_with_frs_is_not_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] whether those FRs are CITED is `check_fr_sweep.py`'s question, not this one.

        Asserted so the two checks stay one number each: duplicating the citation rule here would
        mean two baselines to freeze and two places to argue about the same 39 capabilities.
        """
        root = _registry(
            tmp_path, matrix=self._MATRIX, designs={"C-FLOW-01": _FR_TABLE, "C-FLOW-02": _FR_TABLE}
        )

        assert cdc.unverifiable_findings(root) == []


class TestMain:
    """The CLI contract `quality.py doc` depends on: 0 clean, 1 findings, 2 cannot run."""

    def test_a_group_disagreement_exits_one(
        self, cdc: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _registry(
            tmp_path,
            matrix="",
            roadmap="    *   🔴 **Some Group:**\n        *   `✅` **C-FLOW-01:** One\n",
        )

        assert cdc.main(["--root", str(tmp_path)]) == 1
        assert "Some Group" in capsys.readouterr().out

    def test_growth_beyond_the_baseline_exits_one(
        self, cdc: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FR-2's ratchet: today's 22 are frozen, the 23rd blocks."""
        _registry(tmp_path, matrix="| DAL-C | `✅ C-FLOW-01`: One |")

        assert cdc.main(["--root", str(tmp_path), "--baseline", "0"]) == 1
        assert "C-FLOW-01" in capsys.readouterr().out

    def test_at_the_baseline_exits_zero(self, cdc: ModuleType, tmp_path: Path) -> None:
        """A ratchet that blocked on its own backlog would be switched off within a day."""
        _registry(tmp_path, matrix="| DAL-C | `✅ C-FLOW-01`: One |")

        assert cdc.main(["--root", str(tmp_path), "--baseline", "1"]) == 0

    def test_below_the_baseline_exits_zero(self, cdc: ModuleType, tmp_path: Path) -> None:
        """An IMPROVEMENT must not fail the gate — found by a mutant, not by review.

        Changing `len(caps) > baseline` to `!= baseline` survived the whole suite: every test used
        a count equal to its baseline, so nothing covered the direction the ratchet exists to
        allow. A gate that punishes someone for fixing two of the 22 is a gate they route around.
        """
        _registry(tmp_path, matrix="| DAL-C | `✅ C-FLOW-01`: One |")

        assert cdc.main(["--root", str(tmp_path), "--baseline", "5"]) == 0

    def test_a_missing_matrix_exits_two(self, cdc: ModuleType, tmp_path: Path) -> None:
        """`TECH-032`: a checker that cannot find its subject says so rather than passing."""
        assert cdc.main(["--root", str(tmp_path / "nowhere")]) == 2

    def test_the_live_repo_group_flags_agree(self, cdc: ModuleType) -> None:
        """FR-1 is zero-tolerance and the six known disagreements were corrected in `577744b3`."""
        assert cdc.group_flag_findings(REPO_ROOT / "docs" / "roadmap") == []

    def test_the_live_repo_is_at_or_under_its_baseline(self, cdc: ModuleType) -> None:
        """FR-2's ratchet against the real registry — the count may fall, never rise."""
        assert cdc.main([]) == 0

    def test_the_census_is_cheap_enough_for_the_doc_gate(self, cdc: ModuleType) -> None:
        """NFR-1 — reads the matrix and the features tree, no subprocess per capability.

        The 62-capability census that produced this ticket's numbers needed a parallel subprocess
        fan-out and takes minutes; that shape must never reach the gate, because a `doc` run that
        costs minutes is a `doc` run people stop taking. The bar is deliberately loose — this is a
        tripwire for a change of shape, not a benchmark.
        """
        started = time.perf_counter()
        cdc.unverifiable_findings(REPO_ROOT / "docs" / "roadmap")
        elapsed = time.perf_counter() - started

        assert elapsed < 5.0, (
            f"the census took {elapsed:.1f}s; at that cost it belongs in a nightly, not in "
            "`quality.py doc`, which is run on every commit boundary"
        )
