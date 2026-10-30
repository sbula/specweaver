# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Telling a lint that did not run apart from one that found errors, from the atom's exports.

Proves: TECH-087 FR-4

The lint-fix step only sees the atom's exported error dicts. The check reads the code the shared
factory writes, and is tested on that factory's own output, so the two cannot drift apart.
"""

from __future__ import annotations

from dataclasses import asdict

from specweaver.sandbox.language.core.toolchain import did_not_run_reason, failed_lint


def _exported(*results) -> list[dict]:
    return [asdict(error) for result in results for error in result.errors]


def test_the_shared_not_run_result_is_recognised() -> None:
    assert did_not_run_reason(_exported(failed_lint("ruff timed out after 120 s"))) == (
        "ruff timed out after 120 s"
    )


def test_real_lint_errors_are_not_a_not_run() -> None:
    errors = [{"file": "src/a.py", "line": 3, "code": "F401", "message": "unused import"}]

    assert did_not_run_reason(errors) is None


def test_no_errors_is_not_a_not_run() -> None:
    assert did_not_run_reason([]) is None


def test_one_target_that_did_not_run_wins_over_real_errors() -> None:
    errors = [
        {"file": "src/a.py", "line": 3, "code": "F401", "message": "unused import"},
        *_exported(failed_lint("ruff did not run: no engine"), failed_lint("second target")),
    ]

    assert did_not_run_reason(errors) == "ruff did not run: no engine; second target"


def test_malformed_entries_are_not_a_not_run() -> None:
    assert did_not_run_reason([None, "x", {"code": None}, {}]) is None  # type: ignore[list-item]
