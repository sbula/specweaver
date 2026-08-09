#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What module does a changed file belong to, and what does it mean if none does?

Split out of `scripts/tests.py` (2026-08-09) under TECH-025 SF-04 CB-1, which had spent its
file-size headroom twice over. The seam is real rather than convenient: this module answers
"**what does this changed path mean?**" — a pure mapping over strings — while `tests.py` decides
what to *run* for it and then runs it. Nothing here touches pytest, profiles, DAL or scopes.

Kept deliberately free of `UsageError`: that class lives in `_story_resolution.py` and is
re-exported by `tests.py`, and a second module loading it by path would create a SECOND class of
the same name that no caller's `except` clause would catch. Scope validation therefore stays with
scope resolution, in `tests.py`.

The mapping is by DIRECTORY, which is a proxy: an integration test genuinely spanning three modules
maps to whichever directory it sits in. Same proxy the source side uses, stated rather than implied.
"""

from __future__ import annotations

from pathlib import Path

#: `tests/e2e/` groups some suites under a container directory rather than by domain directly, so
#: the domain is what FOLLOWS it. Taking the first path part verbatim selects every capability.
DOMAIN_CONTAINERS = ("capabilities",)


def src_relative(path: Path) -> Path | None:
    """src/specweaver/core/flow/runner.py -> core/flow/runner.py; scripts/x.py -> scripts/x.py.

    `scripts/` keeps its prefix because callers scope by `rel.parent`, which puts its mirror at
    `tests/unit/scripts`. Excluding it blocked every scripts-only change; see the tests.
    """
    posix = path.as_posix()
    if path.suffix != ".py":
        return None
    if posix.startswith("src/specweaver/"):
        return Path(posix[len("src/specweaver/") :])
    return Path(posix) if posix.startswith("scripts/") else None


def tier_relative(path: Path, tier: str) -> Path | None:
    """`tests/unit/core/flow/test_x.py` -> `core/flow/test_x.py`, for THIS tier only.

    A test belongs to the module it covers, so it contributes that module to the scope exactly as a
    source file does. Only ever a UNION with the source-derived set: a changed test can add a
    module, never redirect or remove one, so it decides nothing — which is what the guard this
    replaced was protecting.

    Tier-specific because a test's tier is embedded in its own path, unlike a source file which
    serves every tier. Without that, editing an e2e test would pull in unit paths.
    """
    prefix = f"tests/{tier}/"
    posix = path.as_posix()
    if not posix.startswith(prefix) or path.suffix != ".py":
        return None
    return Path(posix[len(prefix) :])


def domain_parts(rel: Path) -> tuple[str, ...]:
    """The path parts with any container directory stripped, so `parts[0]` is really the domain."""
    parts = rel.parts
    return parts[1:] if parts and parts[0] in DOMAIN_CONTAINERS else parts


def blocked_reason(tier: str, changed: list[Path]) -> str:
    """WHICH cause applies. The message this replaced asserted the source one unconditionally,
    so it was flatly false for a tests-only change — see `TestBlockedReason`.
    """
    if any(src_relative(p) is not None for p in changed):
        return "you changed source that nothing mirrors here — missing coverage, not a clean run"
    if any(tier_relative(p, tier) is not None for p in changed):
        return "the tests you changed sit in a package with no mirror in this tier"
    return "nothing you changed resolves to this tier at all"
