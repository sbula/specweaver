# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A `🟢` story must have every Core Required (MVS) item delivered.

The roadmap's own legend: *🟢 Completed (For Base: Core MVS is 100% delivered)*. Nothing checked it.
`TECH-053` FR-1 compares an **add-on group** flag with its children and never a **story** flag with
its MVS list, so appending one unbuilt `[ ]` to a completed story's Core Required list silently makes
its flag false — which is exactly what happened to `US-4` when `C-FLOW-13` was minted into the wrong
list on 2026-08-16, and passed every gate for a day.

Indentation is the whole grammar: 4 spaces is Core MVS, 8 is a sub-story add-on. The rule reads only
the 4-space plane, so add-on state stays `TECH-053`'s business and neither rule can double-count.
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
def cdc() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_delivered_claims", REPO_ROOT / "scripts" / "check_delivered_claims.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_delivered_claims"] = module
    spec.loader.exec_module(module)
    return module


def _roadmap(root: Path, body: str) -> Path:
    rd = root / "docs" / "roadmap"
    (rd / "features").mkdir(parents=True, exist_ok=True)
    (rd / "capability_matrix.md").write_text("", encoding="utf-8")
    (rd / "master_story_roadmap.md").write_text(body, encoding="utf-8")
    return rd


class TestStoryFlagFindings:
    """FR-1 — the story header against its own Core Required list."""

    def test_a_green_story_with_an_unbuilt_mvs_item_is_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] the defect, verbatim: one `[ ]` appended to a completed story."""
        root = _roadmap(
            tmp_path,
            "### 🟢 US-4: Context-Aware Flow Orchestration\n"
            "*   **Core Required (MVS):**\n"
            "    *   `✅` **E-FLOW-01:** Config DB\n"
            "    *   `[ ]` **C-FLOW-13:** Model Catalogue\n",
        )

        found = cdc.story_flag_findings(root)

        assert [f.story for f in found] == ["US-4"]
        assert "C-FLOW-13" in found[0].reason

    def test_a_green_story_with_every_item_done_is_not_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Happy] the case that must stay silent for the 20-odd completed stories."""
        root = _roadmap(
            tmp_path,
            "### 🟢 US-4: Done\n*   **Core Required (MVS):**\n    *   `✅` **E-FLOW-01:** Config DB\n",
        )

        assert cdc.story_flag_findings(root) == []

    def test_an_unfinished_story_may_carry_unbuilt_items(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] only `🟢` claims completeness. 🔴/🟡 are allowed their open work."""
        for flag in ("🔴", "🟡"):
            root = _roadmap(
                tmp_path,
                f"### {flag} US-9: In Progress\n"
                "*   **Core Required (MVS):**\n"
                "    *   `[ ]` **X-AAA-01:** pending\n",
            )
            assert cdc.story_flag_findings(root) == [], flag

    def test_add_on_items_are_not_read_as_mvs(self, cdc: ModuleType, tmp_path: Path) -> None:
        """[Boundary] 8-space children belong to `TECH-053`'s group rule.

        A completed story routinely carries unfinished add-ons — that is what an add-on is. Reading
        them here would report every 🟢 story in the file and the rule would be switched off.
        """
        root = _roadmap(
            tmp_path,
            "### 🟢 US-4: Done\n"
            "*   **Core Required (MVS):**\n"
            "    *   `✅` **E-FLOW-01:** Config DB\n"
            "*   **Sub-Story Add-Ons:**\n"
            "    *   🔴 **Later:**\n"
            "        *   `[ ]` **X-AAA-02:** not started\n",
        )

        assert cdc.story_flag_findings(root) == []

    def test_a_story_with_no_mvs_list_is_not_reported(
        self, cdc: ModuleType, tmp_path: Path
    ) -> None:
        """[Graceful] narrative sections exist; a story with nothing to compare says nothing."""
        root = _roadmap(tmp_path, "### 🟢 US-7: Prose only\n\nSome text.\n")

        assert cdc.story_flag_findings(root) == []

    def test_the_live_roadmap_agrees(self, cdc: ModuleType) -> None:
        """Zero-tolerance, like `TECH-053` FR-1: `C-FLOW-13` was the only offender and it moved."""
        assert cdc.story_flag_findings(REPO_ROOT / "docs" / "roadmap") == []
