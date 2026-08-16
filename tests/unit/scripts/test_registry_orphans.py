# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""An entry may not exist in one registry and vanish from the other. `ADR-003`.

`check_roadmap_sync.py` compares *checkbox status* — a `[ ]` box whose capability is `✅`. It never
asked whether the two registries list the same **entries**, and its id pattern excludes `INT-US-*`
and `TECH-*` entirely. So a topic entry could lose its roadmap line and nothing noticed.

Not hypothetical: on 2026-08-13 the `ADR-003` sweep removed 63 roadmap placeholder lines, and **20
of those ids still had real entries in their topic documents** — scope, dependencies, blocking
notes. The whole `doc` gate stayed green. 17 were orphaned for as long as it took to measure it.

A `RETIRED` marker in the entry is the sanctioned way out, because that is what `ADR-003` does to an
integration add-on: the roadmap line goes, the topic entry stays with its scope and its new owner
named. Retirement is a *decision recorded in the open*, which is exactly the difference between it
and an entry that simply vanished.
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
    path = REPO_ROOT / "scripts" / "_registry_orphans.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_registry_orphans", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_registry_orphans"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def orphans() -> ModuleType:
    return _load()


class TestEntryIds:
    """`entry_ids` — a registry ENTRY, not a passing prose mention."""

    def test_a_bolded_list_item_is_an_entry(self, orphans: ModuleType) -> None:
        assert orphans.entry_ids("* `[ ]` **C-FLOW-11:** Graduated Autonomy\n") == {"C-FLOW-11"}

    def test_the_topic_doc_form_is_an_entry_too(self, orphans: ModuleType) -> None:
        """Topic docs write the id inside the bold span, not as a `**ID:**` prefix."""
        assert orphans.entry_ids("* **Autonomous DAG Execution (`C-FLOW-12`)**\n") == {"C-FLOW-12"}

    def test_prose_mentioning_an_id_is_not_an_entry(self, orphans: ModuleType) -> None:
        assert (
            orphans.entry_ids("Sequenced behind `C-EXEC-07`, per the middle-way order.\n") == set()
        )

    def test_a_heading_is_not_an_entry(self, orphans: ModuleType) -> None:
        assert orphans.entry_ids("### 🟢 US-21: Feature Decomposition\n") == set()


class TestOrphans:
    """`orphans` — a topic entry with no roadmap entry, and no recorded retirement."""

    ROAD = "* `[ ]` **C-FLOW-11:** Graduated Autonomy\n"

    def test_an_entry_present_in_both_is_fine(self, orphans: ModuleType) -> None:
        assert orphans.orphans(self.ROAD, {"t.md": self.ROAD}) == []

    def test_an_entry_missing_from_the_roadmap_is_an_orphan(self, orphans: ModuleType) -> None:
        topic = "* **`INT-US-03-SF03` — Graduated Autonomy:** *Pending Design.*\n"
        assert orphans.orphans(self.ROAD, {"US-03.md": topic}) == [("INT-US-03-SF03", "US-03.md")]

    def test_a_retired_entry_is_not_an_orphan(self, orphans: ModuleType) -> None:
        topic = (
            "* **`INT-US-03-SF03` — Graduated Autonomy:** *Pending Design.*\n"
            "\n"
            "  > **RETIRED 2026-08-13 by `ADR-003`.** Moves to `C-FLOW-11`.\n"
        )
        assert orphans.orphans(self.ROAD, {"US-03.md": topic}) == []

    def test_un_retired_does_not_absolve_the_entry(self, orphans: ModuleType) -> None:
        """`UN-RETIRED` contains `RETIRED`, and a substring match reads a withdrawal as a
        retirement — so the entry stays absolved and its MISSING roadmap line goes unreported.

        That inverts the checker: withdrawing a retirement is exactly when the roadmap line has to
        come back, and this is the check that would have said so.
        """
        topic = (
            "* **`INT-US-03-SF03` — Graduated Autonomy:** *Pending Design.*\n"
            "\n"
            "  > **UN-RETIRED 2026-08-16.** The 2026-08-13 retirement named a delivered target.\n"
        )
        assert orphans.orphans(self.ROAD, {"US-03.md": topic}) == [("INT-US-03-SF03", "US-03.md")]

    def test_closed_empty_is_a_second_sanctioned_exit(self, orphans: ModuleType) -> None:
        """An add-on can lose its roadmap line because nothing was left to build, not because the
        scope moved. `INT-US-25-SF01` is the case: all three capabilities delivered AND exercised,
        with only a scope decision outstanding. Forcing that to say `RETIRED` would make it claim a
        move that never happened — the unfalsifiable prose `ADR-003` exists to remove.
        """
        topic = (
            "* **Dynamic Risk Controls (`INT-US-25-SF01`)**\n"
            "\n"
            "  > **CLOSED EMPTY 2026-08-16 — nothing moved, because nothing was left.**\n"
        )
        assert orphans.orphans(self.ROAD, {"US-25.md": topic}) == []

    def test_retirement_covers_only_its_own_entry(self, orphans: ModuleType) -> None:
        """The bug that made this checker necessary, in miniature.

        Consecutive single-line entries have no blank line between them, so a note appended at "the
        next blank line" lands under a LATER entry and silently absolves every entry it skipped.
        An entry ends at the next top-level list item, not at the next blank line.
        """
        topic = (
            "* **`INT-US-01-SF01` — Security Defenses:** *Pending Design.*\n"
            "* **`INT-US-01-SF02` — Enforce Internal Architecture:** *Pending Design.*\n"
            "\n"
            "  > **RETIRED 2026-08-13 by `ADR-003`.** Moves to `C-EXEC-01`.\n"
        )
        assert orphans.orphans(self.ROAD, {"US-01.md": topic}) == [("INT-US-01-SF01", "US-01.md")]


class TestMain:
    """`main` — the gate's exit contract."""

    def test_the_repo_is_at_or_under_its_baseline(self, orphans: ModuleType) -> None:
        assert orphans.main([]) == 0
