# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The report is the only thing that outlives the run.

Proves: TECH-049 FR-9

The sandbox is a detached worktree deleted when the session ends, so anything in the report that
points into it is unreadable by the time a human or a gate acts on it. Measured: a stale anchor
raises `anchor not found in /tmp/sw-leak-jvmq7sif/src/…/scanner.py`, and that string reaches
`detail` verbatim.

Paths are rewritten to repo-relative rather than blanked. The sandbox mirrors the repo, so
`src/…/scanner.py` is both accurate and still useful; `<sandbox>/…` would throw away the only
informative half.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report() -> ModuleType:
    return _load("_mutation_report")


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    return _load("mutation")


def _verdict(mutation: ModuleType, kind: str = "PASS", **over: Any) -> Any:
    base = {"derived_id": "C-EXEC-06 FR-8 m", "verdict": kind, "reason": "", "drift": "OK"}
    return mutation.Verdict(**{**base, **over})


class TestSanitise:
    """`FR-9` — no field may point into a directory that no longer exists."""

    def test_a_sandbox_path_becomes_repo_relative(self, report: ModuleType) -> None:
        raw = "anchor not found in /tmp/sw-leak-jvmq7sif/src/specweaver/x.py: 'foo'"
        assert report.sanitise(raw) == "anchor not found in src/specweaver/x.py: 'foo'"

    def test_several_paths_in_one_string_are_all_rewritten(self, report: ModuleType) -> None:
        raw = "/tmp/sw-a-1/src/a.py and /tmp/sw-b-2/tests/b.py"
        assert "/tmp/" not in report.sanitise(raw)

    def test_it_survives_a_string_with_no_paths(self, report: ModuleType) -> None:
        assert report.sanitise("nothing to see") == "nothing to see"

    def test_it_rewrites_nested_structures(self, report: ModuleType) -> None:
        """Sanitisation runs once over the whole document, so a new field cannot be forgotten."""
        doc = {"a": ["/tmp/sw-x-1/src/a.py"], "b": {"c": "/tmp/sw-x-1/tests/b.py"}, "n": 3}
        assert "/tmp/" not in json.dumps(report.sanitise_document(doc))

    def test_non_string_leaves_are_untouched(self, report: ModuleType) -> None:
        """[Boundary] Counts and booleans must survive the walk unchanged."""
        doc = {"n": 3, "ok": True, "none": None}
        assert report.sanitise_document(doc) == doc


class TestBuildReport:
    """The document a machine reads after the sandbox is gone."""

    def _doc(self, report: ModuleType, mutation: ModuleType, **over: Any) -> dict[str, Any]:
        campaigns = over.pop(
            "campaigns",
            [
                {
                    "feature": "C-EXEC-06",
                    "requirement": "FR-8",
                    "verdict": "PASSED",
                    "mutants_declared": 1,
                    "verdicts_returned": 1,
                    "results": [_verdict(mutation)],
                }
            ],
        )
        return report.build_report(campaigns=campaigns, head="abc1234", dirty=False, **over)

    def test_the_summary_comes_first(self, report: ModuleType, mutation: ModuleType) -> None:
        """A reader that stops after one block must still learn the verdict."""
        doc = self._doc(report, mutation)
        assert next(iter(doc)) == "summary"

    def test_counts_match_the_results(self, report: ModuleType, mutation: ModuleType) -> None:
        campaigns = [
            {
                "feature": "F",
                "requirement": "FR-1",
                "verdict": "FAILED",
                "mutants_declared": 2,
                "verdicts_returned": 2,
                "results": [_verdict(mutation, "PASS"), _verdict(mutation, "FAIL")],
            }
        ]
        doc = self._doc(report, mutation, campaigns=campaigns)
        assert doc["summary"]["counts"]["pass"] == 1
        assert doc["summary"]["counts"]["fail"] == 1

    def test_a_failing_run_still_produces_a_report(
        self, report: ModuleType, mutation: ModuleType
    ) -> None:
        """[Degradation] A run with nothing but failures is exactly when the report is needed."""
        campaigns = [
            {
                "feature": "F",
                "requirement": "FR-1",
                "verdict": "FAILED",
                "mutants_declared": 1,
                "verdicts_returned": 1,
                "results": [_verdict(mutation, "FAIL")],
            }
        ]
        doc = self._doc(report, mutation, campaigns=campaigns)
        assert doc["summary"]["verdict"] == "FAILED"

    def test_the_document_never_carries_a_sandbox_path(
        self, report: ModuleType, mutation: ModuleType
    ) -> None:
        campaigns = [
            {
                "feature": "F",
                "requirement": "FR-1",
                "verdict": "FAILED",
                "mutants_declared": 1,
                "verdicts_returned": 1,
                "results": [_verdict(mutation, "BROKEN", reason="died in /tmp/sw-q-9/src/x.py")],
            }
        ]
        doc = self._doc(report, mutation, campaigns=campaigns)
        assert "/tmp/" not in json.dumps(doc)


class TestExitCodeFor:
    """`0` no-fail · `1` any-fail · `2` could not run."""

    def test_all_passing_is_zero(self, report: ModuleType) -> None:
        assert report.exit_code_for(["PASSED", "PASSED"]) == 0

    def test_partial_is_still_zero(self, report: ModuleType) -> None:
        """`PARTIAL` means unreadable, not broken — it must not read as a failure."""
        assert report.exit_code_for(["PASSED", "PARTIAL"]) == 0

    def test_any_failure_is_one(self, report: ModuleType) -> None:
        assert report.exit_code_for(["PASSED", "FAILED"]) == 1

    def test_nothing_to_run_is_two_not_zero(self, report: ModuleType) -> None:
        """[Hostile] The false green this ticket has now fixed four times.

        A session that found no corpus files has measured nothing, and reporting that as success
        is indistinguishable from a session where everything was protected.
        """
        assert report.exit_code_for([]) == 2
