# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R-MARKER: a `TECH` line is `[ ]` when open and `✅` when delivered — never `[x]`.

`TECH-020`'s follow-up. `check_roadmap_placement.py` shipped with `TECH-026` and had **no tests at
all**, which is its own finding: the rules it enforces were only ever exercised against the live
roadmap, so a rule that silently stopped firing would look identical to a clean file. `R-OWNER`
already shipped inert once for exactly that reason.

The marker rule exists because the contract said what an open TECH line looks like and never said
what a delivered one looks like, while the neighbouring instruction — "check off the boxes" — is
user-story vocabulary. Read across, that produces `[x]`, which appears nowhere else in the roadmap.
It was written twice on 2026-08-12 before anyone noticed.

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


def _violations(*lines: str) -> list[str]:
    module = _load("check_roadmap_placement")
    text = "### 🔧 Technical Debt (TECH)\n" + "\n".join(lines) + "\n"
    return [v for v in module._violations(text) if "R-MARKER" in v]


def test_a_checked_box_on_a_tech_line_is_rejected() -> None:
    """`[x]` is user-story vocabulary and must not reach a capability-level line."""
    found = _violations(BAD_LINE)

    assert len(found) == 1, f"expected R-MARKER to fire once, got: {found}"
    assert "TECH-020" in found[0]


def test_the_two_legal_markers_pass() -> None:
    """The control. Without it the rule could reject everything and still look correct."""
    assert _violations(OPEN_LINE, DONE_LINE) == []


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
