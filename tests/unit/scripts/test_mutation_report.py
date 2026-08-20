# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The report is the only thing that outlives the run.

Proves: TECH-049 FR-9, NFR-3

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
                "results": [
                    _verdict(mutation, "PROTECTED"),
                    _verdict(mutation, "UNPROTECTED"),
                ],
            }
        ]
        doc = self._doc(report, mutation, campaigns=campaigns)
        assert doc["summary"]["counts"]["protected"] == 1
        assert doc["summary"]["counts"]["unprotected"] == 1

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


class TestBuildSessionRecord:
    """Stage C — the session record stores nothing it can recompute.

    A stored roll-up is one that can disagree with its own detail, and this repo has already been
    bitten by exactly that: a `CLEAR` verdict outlived the run it described. `counts`, `declared`,
    `returned`, `not_run` and the per-campaign roll-up are all derivable from the mutants, so they
    are derived at read time and not written down.
    """

    def _record(self, report: ModuleType, mutation: ModuleType, **kwargs: object) -> dict:
        campaigns = kwargs.pop("campaigns", None) or [
            {
                "feature": "F",
                "requirement": "FR-1",
                "verdict": "PASSED",
                "mutants_declared": 1,
                "verdicts_returned": 1,
                "results": [_verdict(mutation, "PROTECTED")],
            }
        ]
        return report.build_session_record(
            campaigns=campaigns, head="abc1234", dirty=False, **kwargs
        )

    def test_the_session_block_names_the_commit_and_the_time(
        self, report: ModuleType, mutation: ModuleType
    ) -> None:
        session = self._record(report, mutation)["session"]

        assert session["head"] == "abc1234"
        assert session["started_at"]

    def test_mutants_are_a_flat_list(self, report: ModuleType, mutation: ModuleType) -> None:
        """Campaign grouping is derivable from the mutant id, which already carries feature and
        requirement. Storing the nesting as well is storing the same fact twice."""
        record = self._record(report, mutation)

        assert isinstance(record["mutants"], list)
        assert record["mutants"][0]["verdict"] == "PROTECTED"

    def test_no_derived_counts_are_stored(self, report: ModuleType, mutation: ModuleType) -> None:
        record = self._record(report, mutation)

        for gone in ("counts", "declared", "returned", "not_run", "verdict"):
            assert gone not in record["session"], f"{gone} is derivable and must not be stored"

    def test_no_campaign_rollup_is_stored(self, report: ModuleType, mutation: ModuleType) -> None:
        assert "campaigns" not in self._record(report, mutation)

    def test_a_skipped_baseline_says_so_rather_than_using_null(
        self, report: ModuleType, mutation: ModuleType
    ) -> None:
        """`{"green": null, "failed": 0}` could not distinguish *not attempted* from *attempted
        and inconclusive*, and put a meaningless `0` beside the null."""
        assert self._record(report, mutation)["session"]["baseline"] == {"ran": False}

    def test_a_baseline_that_ran_reports_its_outcome(
        self, report: ModuleType, mutation: ModuleType
    ) -> None:
        baseline = mutation.Baseline(green=False, failures=["tests/a.py::test_x"], code=1)

        assert self._record(report, mutation, baseline=baseline)["session"]["baseline"] == {
            "ran": True,
            "green": False,
            "failed": 1,
        }

    def test_the_record_declares_its_schema(self, report: ModuleType, mutation: ModuleType) -> None:
        """The ledger and the record are versioned separately; a reader must be able to tell
        which shape it has."""
        assert self._record(report, mutation)["schema"] == 1

    def test_sandbox_paths_are_still_scrubbed(
        self, report: ModuleType, mutation: ModuleType
    ) -> None:
        """The control that must survive the reshape: the sanitiser is recursive so a field
        nobody remembered still gets cleaned, and the mutants moved."""
        campaigns = [
            {
                "feature": "F",
                "requirement": "FR-1",
                "verdict": "FAILED",
                "mutants_declared": 1,
                "verdicts_returned": 1,
                "results": [
                    {
                        "derived_id": "F FR-1 m",
                        "verdict": "UNMEASURED",
                        "reason": "bad-anchor",
                        "explanation": "",
                        "drift": "OK",
                        "confirmed": False,
                        "killers": [],
                        "leaked": [],
                        "detail": "/tmp/sw-session-abc/scripts/x.py moved",
                    }
                ],
            }
        ]
        record = self._record(report, mutation, campaigns=campaigns)

        assert "/tmp/sw-session-abc" not in record["mutants"][0]["detail"]


def _mutant(mid: str, verdict: str, reason: str | None = None) -> dict:
    return {
        "id": mid,
        "verdict": verdict,
        "reason": reason,
        "explanation": "",
        "drift": "OK",
        "confirmed": True,
        "killers": [],
        "leaked": [],
        "detail": "",
    }


class TestCountsOf:
    """Everything the record no longer stores is computed here, from the one place it lives.

    This is the other half of dropping the roll-ups. If the counts are not recomputed on read,
    dropping them does not simplify the record — it deletes information. And because they are
    computed from `mutants`, they cannot disagree with it, which a stored count could and did.
    """

    def _record(self, *mutants: dict) -> dict:
        return {"schema": 1, "session": {"head": "abc"}, "mutants": list(mutants)}

    def test_counts_are_computed_from_the_mutants(self, report: ModuleType) -> None:
        record = self._record(
            _mutant("F FR-1 a", "PROTECTED"),
            _mutant("F FR-1 b", "UNPROTECTED", "no-killer"),
            _mutant("G FR-2 c", "UNMEASURED", "timed-out"),
        )

        assert report.counts_of(record) == {
            "protected": 1,
            "unprotected": 1,
            "unmeasured": 1,
            "stale": 0,
        }


class TestCampaignsOf:
    """`campaigns_of` — the grouping the record no longer stores."""

    def _record(self, *mutants: dict) -> dict:
        return {"schema": 1, "session": {"head": "abc"}, "mutants": list(mutants)}

    def test_campaigns_are_grouped_from_the_mutant_id(self, report: ModuleType) -> None:
        """The id already carries feature and requirement, which is why the nesting was dropped."""
        record = self._record(
            _mutant("F FR-1 a", "PROTECTED"),
            _mutant("F FR-1 b", "PROTECTED"),
            _mutant("G FR-2 c", "UNPROTECTED", "no-killer"),
        )

        grouped = report.campaigns_of(record)

        assert [(c["feature"], c["requirement"], len(c["mutants"])) for c in grouped] == [
            ("F", "FR-1", 2),
            ("G", "FR-2", 1),
        ]

    def test_a_campaign_fails_when_any_mutant_is_a_finding(self, report: ModuleType) -> None:
        record = self._record(
            _mutant("F FR-1 a", "PROTECTED"), _mutant("F FR-1 b", "UNMEASURED", "timed-out")
        )

        assert report.campaigns_of(record)[0]["verdict"] == "FAILED"

    def test_a_campaign_passes_when_every_mutant_is_protected(self, report: ModuleType) -> None:
        """The control: a roll-up that always failed would be as useless as one that always
        passed."""
        record = self._record(_mutant("F FR-1 a", "PROTECTED"))

        assert report.campaigns_of(record)[0]["verdict"] == "PASSED"

    def test_an_empty_record_is_not_silently_a_pass(self, report: ModuleType) -> None:
        """[Hostile] Zero mutants must never read as success — that is what a crashed session
        looks like."""
        record = self._record()

        assert report.counts_of(record) == {
            "protected": 0,
            "unprotected": 0,
            "unmeasured": 0,
            "stale": 0,
        }
        assert report.campaigns_of(record) == []

    def test_drift_is_counted_beside_the_verdict_not_instead_of_it(
        self, report: ModuleType
    ) -> None:
        """A stale symbol is orthogonal to what the mutant taught us, so it has its own key."""
        mutant = _mutant("F FR-1 a", "UNMEASURED", "symbol-drifted")
        mutant["drift"] = "STALE"

        counts = report.counts_of(self._record(mutant))

        assert (counts["unmeasured"], counts["stale"]) == (1, 1)
