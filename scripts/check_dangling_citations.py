#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every citation in the test tree names a requirement some design declares.

`check_fr_coverage.py` asks this per story, and only at closure. That leaves the question unasked
for every story nobody is closing — which on 2026-08-27 was nine dangling citations across six
designs, two of them on `TECH-058`, closed months earlier and never coming back.

`development_framework.md` states the rule: **a check that must be invoked to fire reports success
by not running.** So the same question gets a sweep, in the `doc` gate beside `fr_sweep` and
`nfr_sweep`.

## Why a dangling citation is not cosmetic

A `Proves:` tag is how this repo credits evidence. A tag naming a requirement that does not exist
credits proof to nothing, and reads exactly like proof of something. `TECH-056` declares one FR and
says so in its own prose; a test carried `Proves: TECH-056 FR-2`, and the story-scoped checker
printed `3 of 1 requirement(s)` and exited 0.

`A-VAL-01 FR-6` is the case that shows the shape matters: the citing file's own docstring already
explains that a cross-story text scan invented the id. Somebody diagnosed it by hand, wrote it
down, and nothing has caught it since.

## The rule lives once

`dangling_citations` is imported from `check_fr_coverage`, never reimplemented. Two derivations of
one rule agree on the day they are written and not reliably after — which is the defect the
boundary that added this file was repairing, one level up.

Usage:
    python scripts/check_dangling_citations.py

Exit code 1 blocks the `doc` gate. There is no override flag: a citation naming an id that never
existed is either a typo in the test or a row the design lost, and both are fixed by editing, not
by exempting. Fixture ids are handled by `FIXTURE_ID_FLOOR`, not by an allow-list.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURES_ROOT = REPO_ROOT / "docs" / "roadmap" / "features"
TESTS_ROOT = REPO_ROOT / "tests"


def _load_sibling(name: str) -> Any:
    """A sibling script as a module. `scripts/` is not a package, so this is the import."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_coverage = _load_sibling("check_fr_coverage")

#: Re-exported, not reimplemented. `PRINCIPLES.md` §5.
dangling_citations = _coverage.dangling_citations


def stories_with_a_design(features_root: Path) -> list[str]:
    """Every id that owns a design document, sorted."""
    return sorted({d.parent.name for d in features_root.rglob("*_design.md")})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--features-root", default=str(FEATURES_ROOT), help=argparse.SUPPRESS)
    ap.add_argument("--tests-root", default=str(TESTS_ROOT), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    features_root = Path(args.features_root)
    tests_root = Path(args.tests_root)
    stories = stories_with_a_design(features_root)

    # A sweep that scanned nothing is not a clean repo. `check_proof_tier` shipped reporting zero
    # violations because it never saw the designs, and a mistyped root reproduces that exactly.
    if not stories:
        print(f"FAIL  no design document found under {features_root} — this sweep examined nothing")
        return 1

    findings: list[tuple[str, str, list[str]]] = []
    for story in stories:
        for requirement, files in dangling_citations(features_root, tests_root, story).items():
            findings.append((story, requirement, files))

    print(f"Dangling citations: {len(stories)} design(s) swept")
    for story, requirement, files in findings:
        print(f"  FAIL  {story} {requirement}  <- {', '.join(files)}")

    if findings:
        print(
            f"\n{len(findings)} citation(s) name a requirement neither the FR nor the NFR table "
            "declares. Each one credits proof to something that does not exist. Fix the citation "
            "if the id is a typo, or restore the row if the design lost it — the two are not "
            "interchangeable, and only reading the test says which."
        )
        return 1

    print("Every citation names a requirement its design declares.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
