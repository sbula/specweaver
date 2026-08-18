# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every mutation campaign must name test files that exist.

A campaign's `scope` is the set of tests run against each mutant. When a path in it no longer
resolves, pytest collects nothing, every mutant in that campaign is reported as a failure with
*"no tests were collected for this scope"*, and the corpus says the requirement is unproven when
really the campaign is misaddressed.

**This is not hypothetical.** Moving the e2e suite into `tests/e2e/capabilities/<domain>/` on
2026-08-17 stranded four scope paths across `TECH-054` and `INT-US-16`. Nothing noticed, because the
corpus is deliberately not part of any commit gate and the nightly timer was not installed on this
machine — two independent safety nets, both absent. The breakage surfaced only when the timer was
installed a day later and the first real run came back FAILED.

The corpus stays out of the commit gate for good reasons; that is what makes this cheap check worth
having in the suite instead.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = REPO_ROOT / "docs" / "roadmap" / "features"


def _campaign_scopes() -> list[tuple[str, str, str]]:
    """`(campaign file, requirement, scope path)` for every scope entry in the corpus."""
    entries: list[tuple[str, str, str]] = []
    for path in sorted(CORPUS_ROOT.rglob("*_mutants.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for campaign in document.get("campaigns", []):
            for scope in campaign.get("scope", []):
                entries.append((path.name, campaign.get("requirement", "?"), scope))
    return entries


def test_the_corpus_is_being_read_at_all() -> None:
    """The check below is an absence proof, and absence is what an empty corpus returns.

    Without this, moving or renaming the corpus directory turns the guard into a permanent pass —
    the same failure mode it exists to catch, one level up.
    """
    scopes = _campaign_scopes()
    assert len(scopes) >= 10, (
        f"only {len(scopes)} campaign scope(s) found under {CORPUS_ROOT} — the corpus moved, or the "
        "campaign schema changed, and this guard is now inspecting nothing"
    )


def test_every_campaign_scope_resolves_to_a_real_file() -> None:
    """A scope path that no longer exists makes its campaign report a failure it did not have."""
    missing = [
        f"{name} {requirement}: {scope}"
        for name, requirement, scope in _campaign_scopes()
        if not (REPO_ROOT / scope).exists()
    ]

    assert not missing, (
        "mutation campaigns name test files that do not exist. Each one makes pytest collect nothing "
        "and reports its mutants as failures with 'no tests were collected for this scope', so the "
        "nightly says a requirement is unproven when the campaign is simply misaddressed:\n  "
        + "\n  ".join(missing)
    )
