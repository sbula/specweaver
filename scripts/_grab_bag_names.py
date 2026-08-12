#!/usr/bin/env python
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R7 — a module name may not promise nothing (`TECH-015`).

A module whose name promises nothing cannot be contradicted, so it accretes. Every author with
something that "sort of belongs near the runner" reaches for `runner_utils`, and the next one
reaches for it because the last one did.

**Measured, not asserted.** `runner_utils.py` grew from 413 to 469 lines between `TECH-015` being
filed (2026-07-25) and being worked (2026-08-12) — and one of those additions was made by the agent
working `TECH-014`, who put it there precisely because `runner.py` had no headroom. The ticket
predicted the mechanism and then the mechanism ran on the ticket's own example.

A census against a frozen baseline rather than a per-file rule, for the same reason R6 is: the
existing offenders are known and named, each split lowers the count, and the count may fall but
never rise. Rejecting them outright would just block every commit until the whole refactor lands.

Lives in a sibling of `check_conventions.py` and is re-exported from it, matching R6 — so a reader
still has one place to look for "why was my module name rejected".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "scripts" / "baselines" / "grab_bag_module_names.json"

#: Names that describe a location rather than a contract. Matched as whole `_`-delimited segments,
#: so `runner_utils` is caught and `commonmark` is not — a substring match would reject real words.
GRAB_BAG = re.compile(
    r"(^|_)(util|utils|helper|helpers|misc|shared|common|commons)(_|$)", re.IGNORECASE
)

#: `specweaver/commons` is the L0 foundation leaf, where `commons` IS the contract — it is the
#: designated home for genuinely cross-cutting code, which is what makes the rule enforceable
#: everywhere else. Exempted by **path**, so a stray `commons.py` elsewhere is still rejected.
#:
#: `tests/fixtures` holds sample projects that exist to be analysed by the tool. Their names are
#: deliberate test data, not this repo's architecture.
EXEMPT_PREFIXES = (
    "src/specweaver/commons/",
    "tests/fixtures/",
)

SCANNED = ("src", "tests", "scripts")


def is_grab_bag(stem: str) -> bool:
    """Whether a module stem names a location instead of a contract."""
    return bool(GRAB_BAG.search(stem))


def is_exempt(path: Path) -> bool:
    """Whether this path sits somewhere a grab-bag name is legitimate."""
    posix = path.as_posix()
    return any(posix.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def census(root: Path) -> list[str]:
    """Every module in the repo whose name promises nothing, as repo-relative posix paths."""
    found: list[str] = []
    for scanned in SCANNED:
        base = root / scanned
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            relative = path.relative_to(root)
            if is_exempt(relative) or not is_grab_bag(path.stem):
                continue
            found.append(relative.as_posix())
    return sorted(found)


def load_baseline() -> list[str] | None:
    """The frozen offender list, or None when it has never been written."""
    if not BASELINE_PATH.is_file():
        return None
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    names = data.get("modules", [])
    return [str(name) for name in names]


def write_baseline(modules: list[str]) -> None:
    """Freeze the current offender list. The diff is meant to be reviewed."""
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps({"modules": sorted(modules)}, indent=2) + "\n", encoding="utf-8"
    )


def regressions(current: list[str], baseline: list[str]) -> list[str]:
    """Offenders present now and absent from the baseline — i.e. newly introduced."""
    return sorted(set(current) - set(baseline))
