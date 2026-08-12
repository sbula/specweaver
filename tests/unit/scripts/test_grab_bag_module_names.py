# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R7: a module name may not promise nothing (`TECH-015`).

A module whose name promises nothing cannot be contradicted, so it accretes. `runner_utils.py` is
the worked example, and the mechanism is observable rather than theoretical: it grew **413 -> 469
lines between the ticket being filed and being worked**, and one of those accretions was added by
the agent working `TECH-014` — who reached for it precisely because `runner.py` had no room.

So the guardrail ships with the fix. Without it the pathology regrows, which is the whole reason
`TECH-015` was written after the offenders were already known.

A census against a frozen baseline rather than a per-file rule, matching R6: the existing offenders
are named in the baseline and each split lowers the count. **The count may fall, never rise.**

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

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


def test_the_grab_bag_tokens_are_recognised() -> None:
    """The vocabulary the rule rejects, and the shapes it must not catch."""
    module = _load("_grab_bag_names")

    for name in ("runner_utils", "_helpers", "misc", "shared_state", "common_types", "util"):
        assert module.is_grab_bag(name), f"{name!r} should be rejected"

    for name in ("staleness", "hydration", "step_execution", "reservation", "gates"):
        assert not module.is_grab_bag(name), f"{name!r} names a contract and must pass"

    assert module.is_grab_bag("commons"), (
        "`commons` is a grab-bag name like any other — the L0 leaf is exempt by PATH, so a stray "
        "commons.py elsewhere must still be rejected"
    )


def test_a_token_inside_a_real_word_is_not_a_grab_bag() -> None:
    """The rule matches whole segments, not substrings.

    Without this, `commonmark` or `utilisation` would be rejected for containing the letters. The
    boundary is `_` or the ends of the name, which is why `runner_utils` matches and `commonmark`
    does not.
    """
    module = _load("_grab_bag_names")

    for name in ("commonmark", "utilisation", "sharded_store", "helperless"):
        assert not module.is_grab_bag(name), f"{name!r} merely contains the letters"


def test_the_commons_leaf_is_exempt() -> None:
    """`specweaver/commons` is the L0 foundation leaf — there, `commons` IS the contract.

    Exempting it by path rather than by name, so a `commons.py` sitting somewhere else is still
    rejected.
    """
    module = _load("_grab_bag_names")

    assert module.is_exempt(Path("src/specweaver/commons/qa.py"))
    assert module.is_exempt(Path("tests/fixtures/sample_project/src/greeter/utils.py"))
    assert not module.is_exempt(Path("src/specweaver/core/flow/engine/runner_utils.py"))


def test_the_census_reflects_the_real_tree() -> None:
    """Anchored to the tree, so the rule cannot pass while the artifact drifts.

    Deliberately asserts *properties* rather than today's offender list: `TECH-015` is actively
    deleting entries, and a test that names them would need editing on every split — which is how a
    census test decays into a copy of the baseline it is supposed to check.
    """
    module = _load("_grab_bag_names")

    offenders = module.census(REPO_ROOT)

    assert all((REPO_ROOT / o).is_file() for o in offenders), "census lists a module that is gone"
    assert not any(o.startswith("tests/fixtures/") for o in offenders), (
        "fixture sample projects are deliberate and must stay exempt"
    )
    assert not any(o.startswith("src/specweaver/commons/") for o in offenders), (
        "the L0 leaf is where cross-cutting code belongs and must stay exempt"
    )


def test_the_split_removed_the_module_the_ticket_was_written_about() -> None:
    """`runner_utils.py` is the worked example, and its removal is the ticket's headline claim.

    Worth its own assertion rather than folding into the ratchet: the ratchet only notices names
    being *added*, so nothing else in this file would fail if the split were reverted.
    """
    module = _load("_grab_bag_names")

    offenders = module.census(REPO_ROOT)

    assert "src/specweaver/core/flow/engine/runner_utils.py" not in offenders
    assert not (REPO_ROOT / "src/specweaver/core/flow/engine/runner_utils.py").exists()


def test_the_count_has_not_risen_above_the_baseline() -> None:
    """The ratchet itself. Splitting an offender lowers it; adding one fails here."""
    module = _load("_grab_bag_names")

    current = module.census(REPO_ROOT)
    baseline = module.load_baseline()

    assert baseline is not None, (
        "no baseline — run `python scripts/check_conventions.py --update-grab-bag-baseline`"
    )
    new = sorted(set(current) - set(baseline))

    assert new == [], (
        "new grab-bag module name(s) — name the module for its contract instead:\n  "
        + "\n  ".join(new)
    )
