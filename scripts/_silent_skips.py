#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R8 of the conventions guard: a test may skip for the machine, never for this repo. `TECH-017`.

A sibling for the same reason R6 (`_test_class_naming.py`) and R7 (`_grab_bag_names.py`) are:
`check_conventions.py` sits against a 600-line RED threshold, and adding this rule inline pushed it
to 662 and blocked the very commit that shipped the rule. Extracted rather than condensed, because
buying headroom back with prose density is the mistake `TECH-020` was filed about.

The seam: this module decides **which skips are illegitimate**; `check_conventions.py` owns which
rules exist and how a violation is worded and reported. Returning plain tuples rather than
`Violation` keeps the import one-directional.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = "tests"

#: What a test may legitimately skip for: a capability of the MACHINE, not of this repo. Matched
#: case-insensitively against the skip's reason string. Deliberately short — every entry widens the
#: set of tests allowed to vanish from a green run, so an addition should feel costly.
ENVIRONMENT_SKIP_REASONS = (
    "symlink",  # requires elevation on Windows; the OS decides this, not us
    "_api_key",  # tests/manual live calls, not collected by the suite
    "api key",
    # `systemd-analyze` is a host tool, not something this repo ships or can install. Verifying a
    # generated unit file is worth doing where systemd exists and is impossible where it does not,
    # so the skip states a genuine environment fact rather than routing around a defect.
    "systemd-analyze",
)


def offending_skips(path: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    """Return one ready-to-print message per `pytest.skip()` this repo controls the outcome of.

    A skip on something the repo CONTROLS — a bundled file's path, a shipped pipeline's contents,
    or the output of the very endpoint under test — converts a defect into a green run. The suite
    then reports success for a test that did not execute, which is the failure this repo already
    names elsewhere: a check that silently does not run is indistinguishable from one that passes.

    Not theory. `PIPELINES_DIR` in `test_feature_pipeline.py` pointed at a nonexistent path for
    months, and both of that file's tests were guarded by
    `if not path.exists(): pytest.skip(...)` — so they skipped rather than failed and the wrong
    constant stayed invisible. Found 2026-07-25; the incident was written into a comment above the
    constant and **the guard was left armed**, still there on 2026-08-13. Four such guards were
    converted to hard failures that day: the two here, one on a bundled pipeline in
    `test_pipeline_yaml.py`, one on a rule's presence in the default spec pipeline, and one in
    `test_standards.py` that skipped when the scan returned nothing — making the accept-flow test's
    outcome conditional on the very endpoint it exercises.

    `@pytest.mark.skipif` is out of scope on purpose: it is declarative and appears in the run
    report, and what the 11 `skipif`-gated suites should do on a machine without `git`/`bash` is a
    separate `TECH-017` decision from whether an inline skip may hide a repo defect.
    """
    rel = (
        path.relative_to(repo_root).as_posix()
        if path.is_relative_to(repo_root)
        else path.as_posix()
    )
    if not rel.startswith(f"{TESTS_ROOT}/"):
        return []

    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []

    found: list[str] = []
    for node in ast.walk(tree):
        # Narrowed inline rather than via a helper predicate: mypy does not carry a `bool`
        # helper's narrowing back to its caller, and papering that over with a blanket type
        # suppression would spend ratchet budget on a checker whose whole subject is hidden
        # failures. (Spelling the suppression out here is what tipped the ratchet by one --
        # check_suppressions.py counts the token in prose, not just in force.)
        # `pytest.mark.skipif` has a different shape and never matches this.
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "skip"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest"
        ):
            continue
        reason = ast.unparse(node.args[0]).lower() if node.args else "()"
        if any(token in reason for token in ENVIRONMENT_SKIP_REASONS):
            continue
        found.append(
            f"line {node.lineno}: pytest.skip({reason}) does not cite an environment capability. "
            "A skip on something this repo controls turns a defect into a green run — assert "
            "instead, or add the reason to ENVIRONMENT_SKIP_REASONS with why."
        )
    return found
