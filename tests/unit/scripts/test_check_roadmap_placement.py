# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R-MARKER and R-ONCE, the two rules about what a single roadmap line may be.

Proves: TECH-060 FR-1

R-MARKER: a `TECH` line is `[ ]` when open and `✅` when delivered — never `[x]`.

`TECH-020`'s follow-up. `check_roadmap_placement.py` shipped with `TECH-026` and had **no tests at
all**, which is its own finding: the rules it enforces were only ever exercised against the live
roadmap, so a rule that silently stopped firing would look identical to a clean file. `R-OWNER`
already shipped inert once for exactly that reason.

The marker rule exists because the contract said what an open TECH line looks like and never said
what a delivered one looks like, while the neighbouring instruction — "check off the boxes" — is
user-story vocabulary. Read across, that produces `[x]`, which appears nowhere else in the roadmap.
It was written twice on 2026-08-12 before anyone noticed.

R-ONCE exists because rewriting a retirement note in place produced a SECOND line for a capability
that already had one. On 2026-08-16 five add-on groups were re-labelled from the retired
`INT-US-NN-SFxx` id to the capability that owns the work — beside the capability's own line, which
nobody deleted. Five ids then appeared twice inside one story, each pair `[ ]`, and no gate could
tell which line was the entry.

`scripts/` is not an importable package, so the module is loaded by path (same pattern as the
sibling script tests).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]

OPEN_LINE = "    *   `[ ]` **TECH-031:** [Container Prepare Phase](features/x/TECH-031.md)"
DONE_LINE = "    *   `✅` **TECH-030:** [An Empty FolderGrant Path](features/x/TECH-030.md)"
BAD_LINE = "    *   `[x]` **TECH-020:** [Extract the Step-Execution Loop](features/x/TECH-020.md)"


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


STORY_HEADING = "### 🟢 US-4: Context-Aware Flow Orchestration"
CAPABILITY_LINE = "        *   `[ ]` **B-FLOW-05:** Token-Burn Circuit Breakers (EDoS Prevention)"
RETIRED_TWIN = (
    "        *   `[ ]` **B-FLOW-05:** Token-Burn Circuit Breakers "
    "— was `INT-US-04-SF02`, retired by `ADR-003`"
)
OTHER_CAPABILITY = "        *   `[ ]` **C-INTL-04:** Conversation Summarization"
SECOND_STORY = "### 🟢 US-9: The Zero-Trust Sandbox"


def _violations(*lines: str) -> list[str]:
    module = _load("check_roadmap_placement")
    text = "### 🔧 Technical Debt (TECH)\n" + "\n".join(lines) + "\n"
    return [v for v in module._violations(text) if "R-MARKER" in v]


def _once(*lines: str) -> list[str]:
    module = _load("check_roadmap_placement")
    return [v for v in module._violations("\n".join(lines) + "\n") if "R-ONCE" in v]


def test_a_checked_box_on_a_tech_line_is_rejected() -> None:
    """`[x]` is user-story vocabulary and must not reach a capability-level line."""
    found = _violations(BAD_LINE)

    assert len(found) == 1, f"expected R-MARKER to fire once, got: {found}"
    assert "TECH-020" in found[0]


def test_the_two_legal_markers_pass() -> None:
    """The control. Without it the rule could reject everything and still look correct."""
    assert _violations(OPEN_LINE, DONE_LINE) == []


def test_the_sub_and_mig_suffixes_are_registry_ids() -> None:
    """`STORY_ID` ended at a digit or `-SFnn`, so `-SUB` and `-MIG` were not ids at all.

    R-PLACE then reported a legitimate `INT-US-21-SUB` line as a design's internal decomposition —
    the precise opposite of what the rule is for. `-SUB` is a legacy sub-story suffix carried by a
    live entry; `-MIG` is `ADR-004`'s migration entry.
    """
    story = "### 🟡 US-21: Autonomous Feature Decomposition"
    for line in (
        "        *   `[ ]` **INT-US-21-SUB:** Recursive Planning",
        "        *   `[ ]` **INT-US-21-MIG:** Migration",
        "        *   `[ ]` **INT-US-21-SF01-MIG:** Migration",
    ):
        module = _load("check_roadmap_placement")
        found = [v for v in module._violations(f"{story}\n{line}\n") if "R-PLACE" in v]
        assert found == [], f"{line} reported as having no registry ID: {found}"


def test_one_id_on_two_lines_of_a_story_is_rejected() -> None:
    """The 2026-08-16 shape: a retirement note re-labelled onto an id that already had a line."""
    found = _once(STORY_HEADING, RETIRED_TWIN, CAPABILITY_LINE)

    assert len(found) == 1, f"expected R-ONCE to fire once, got: {found}"
    assert "B-FLOW-05" in found[0]


def test_distinct_ids_in_one_story_pass() -> None:
    """The control. Without it the rule could reject every add-on group and still look correct."""
    assert _once(STORY_HEADING, CAPABILITY_LINE, OTHER_CAPABILITY) == []


def test_the_same_id_under_two_stories_passes() -> None:
    """A capability legitimately serves more than one story — `US-4 Core` is cited by six.

    Scoping the rule to the file rather than the entry would report those as duplicates and the
    rule would be switched off within a day.
    """
    assert _once(STORY_HEADING, CAPABILITY_LINE, SECOND_STORY, CAPABILITY_LINE) == []


def test_a_repeated_tech_line_is_out_of_scope() -> None:
    """The TECH ledger is not a story entry, and `roadmap_sync` already judges its ids."""
    tech = "    *   `[ ]` **TECH-031:** [Container Prepare Phase](features/x/TECH-031.md)"
    assert _once("### 🔧 Technical Debt (TECH)", tech, tech) == []


def test_the_live_roadmap_has_no_duplicate_entry() -> None:
    """The rule is enforced against the real file — five ids were duplicated when it was written."""
    module = _load("check_roadmap_placement")
    roadmap = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"

    found = [v for v in module._violations(roadmap.read_text(encoding="utf-8")) if "R-ONCE" in v]

    assert found == [], "R-ONCE violations in the live roadmap:\n  " + "\n  ".join(found)


def test_the_live_roadmap_is_clean() -> None:
    """The rule is enforced against the real file, not only fixtures.

    A checker that passes its own fixtures while the artifact it guards has drifted is the failure
    `R-OWNER` actually shipped with — it matched `SF-03` as its own owner, so every unqualified
    reference looked satisfied and the rule could never fire.
    """
    module = _load("check_roadmap_placement")
    roadmap = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"

    found = [v for v in module._violations(roadmap.read_text(encoding="utf-8")) if "R-MARKER" in v]

    assert found == [], "R-MARKER violations in the live roadmap:\n  " + "\n  ".join(found)
