# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A closed TECH ticket must not still read `[ ]` in the master roadmap.

`TECH-017` was closed on 2026-08-14 and the roadmap kept an unticked box for it. That is the
**third** stale status marker found in two days, after `INT-US-04`'s base contract (`✅ Complete`
over unbuilt work) and its SF-08 (`Committed ⬜` over work shipped in May).

The reason it survived is worth recording: a status lives in **three** places with **three
spellings** — `🟢` in the topic doc, `✅` in the roadmap's checkbox list, and prose in the routing
table. A sweep for `🔴` reported clean while `[ ]` sat two hundred lines further down, so the
checker missed it and so did the human reading the checker.

`check_roadmap_sync` already does exactly this for capabilities (`[ ]` in the roadmap vs `✅` in the
matrix). TECH tickets simply had no equivalent, which is the whole defect.
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
    path = REPO_ROOT / "scripts" / "check_roadmap_sync.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("check_roadmap_sync", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_roadmap_sync"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load()


class TestStaleTechTickets:
    """`stale_tech_tickets` — closed in the topic doc, still unticked in the roadmap."""

    def test_a_green_ticket_left_unticked_is_stale(self, mod: ModuleType) -> None:
        """The exact `TECH-017` case this was written for."""
        topic = "* **`TECH-017` 🟢: Integration-Contract Proof Audit**\n"
        road = "    *   `[ ]` **TECH-017:** [Integration-Contract Proof Audit](x.md)\n"
        assert mod.stale_tech_tickets(road, topic) == ["TECH-017"]

    def test_a_green_ticket_already_ticked_is_fine(self, mod: ModuleType) -> None:
        topic = "* **`TECH-017` 🟢: Integration-Contract Proof Audit**\n"
        road = "    *   `✅` **TECH-017:** [Integration-Contract Proof Audit](x.md)\n"
        assert mod.stale_tech_tickets(road, topic) == []

    def test_an_open_ticket_left_unticked_is_fine(self, mod: ModuleType) -> None:
        """`[ ]` against a `🔴` ticket is the correct state, not drift."""
        topic = "* **`TECH-010` 🔴: MCP Persistent-Process Executor Migration**\n"
        road = "    *   `[ ]` **TECH-010:** [MCP Persistent-Process Executor Migration](x.md)\n"
        assert mod.stale_tech_tickets(road, topic) == []

    def test_a_ticket_absent_from_the_roadmap_is_not_reported_here(self, mod: ModuleType) -> None:
        """Existence drift is `_registry_orphans`' job. One checker, one question."""
        topic = "* **`TECH-099` 🟢: Something**\n"
        assert mod.stale_tech_tickets("", topic) == []

    def test_the_real_tree_is_in_sync(self, mod: ModuleType) -> None:
        """If this fails, a closed ticket is still advertised as open work."""
        road = (REPO_ROOT / "docs/roadmap/master_story_roadmap.md").read_text(encoding="utf-8")
        topic = (REPO_ROOT / "docs/roadmap/topics/topic_07_technical_debt.md").read_text(
            encoding="utf-8"
        )
        assert mod.stale_tech_tickets(road, topic) == []
