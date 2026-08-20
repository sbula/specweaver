# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The readable rendering of a mutation report, and why a machine format needed one.

JSON was chosen because it is machine readable. It was then hand-parsed by an agent three times in one
session and produced a wrong answer every time — `campaign` for `feature`, a top-level `scope` that
lives under `campaigns[]`, `outcome` for `verdict`. None of those raised: `dict.get(key, default)`
returns the default, so a wrong key yields a confident zero. One of them nearly closed an
investigation with a false all-clear.

So the writer renders the same document as prose, from the same data, and a reader with a parse in
hand can check it against this rather than against their own guesses. The rendering is a **pure
function of the document**, so it cannot drift from the JSON — there is one source of truth and one
view of it, not two records to keep in step.

Every test here is about the rendering being *unable to omit the thing that matters*.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def rep() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_mutation_report", REPO_ROOT / "scripts" / "_mutation_report.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_mutation_report"] = module
    spec.loader.exec_module(module)
    return module


def _document(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema": 1,
        "session": {
            "started_at": "2026-08-16T15:59:29+00:00",
            "head": "abc1234",
            "dirty": False,
            "baseline": {"ran": True, "green": True, "failed": 0},
        },
        "mutants": [
            {
                "id": "TECH-054 FR-1 discovery-finds-nothing",
                "verdict": "PROTECTED",
                "reason": None,
                "explanation": "",
                "confirmed": True,
                "drift": "OK",
            },
            {
                "id": "TECH-054 FR-1 project-filter-inverted",
                "verdict": "UNMEASURED",
                "reason": "nothing-collected",
                "explanation": "no tests were collected for this scope",
                "confirmed": False,
                "drift": "OK",
            },
            {
                "id": "TECH-055 FR-1 ok",
                "verdict": "PROTECTED",
                "reason": None,
                "explanation": "",
                "confirmed": True,
                "drift": "OK",
            },
        ],
    }
    doc["session"].update(overrides)
    return doc


class TestRenderSummary:
    def test_the_verdict_and_the_counts_are_stated(self, rep: ModuleType) -> None:
        out = rep.render_summary(_document())

        assert "FAILED" in out
        assert "26" in out, "the declared total is the number a reader checks their parse against"

    def test_every_failing_mutant_is_named_with_its_reason(self, rep: ModuleType) -> None:
        """The anti-omission property. A summary that reported only counts would have let the

        'no tests were collected for this scope' diagnosis stay buried in the JSON, which is exactly
        where it sat for two days.
        """
        out = rep.render_summary(_document())

        assert "TECH-054 FR-1 project-filter-inverted" in out
        assert "no tests were collected for this scope" in out

    def test_a_passing_mutant_is_not_listed_individually(self, rep: ModuleType) -> None:
        """Twenty-six passing lines would bury the two that matter."""
        out = rep.render_summary(_document())

        assert "discovery-finds-nothing" not in out
        assert "TECH-055" in out, "but its campaign still appears, so coverage is visible"

    def test_the_evidence_states_its_own_age(self, rep: ModuleType) -> None:
        """`--gate` said CLEAR for two days against a stale report because nothing carried a date.

        The file's mtime knew. The document did not, and the document is what gets read.
        """
        out = rep.render_summary(_document(), now="2026-08-18T08:00:00+00:00")

        assert "2026-08-16" in out
        # 40 hours is one day, not two. Truncating is the honest reading of an elapsed duration, and
        # the warning beside it does the work that rounding up would otherwise be asked to do.
        assert "1 day old" in out, f"the age must be stated in words a reader will notice:\n{out}"
        assert "CHECK THIS" in out, "a day-old verdict must not read like a fresh one"

    def test_a_dirty_tree_is_flagged(self, rep: ModuleType) -> None:
        """A verdict measured against uncommitted work does not describe any commit."""
        out = rep.render_summary(_document(dirty=True))

        assert "dirty" in out.lower()

    def test_a_red_baseline_is_stated_before_any_verdict(self, rep: ModuleType) -> None:
        """Mutant verdicts against a red baseline are meaningless, so this cannot be a footnote."""
        out = rep.render_summary(_document(baseline={"ran": True, "green": False, "failed": 3}))

        head = out[: out.index("TECH-054")] if "TECH-054" in out else out
        assert "baseline" in head.lower() and "not green" in head.lower(), (
            f"a red baseline must be visible before the results it invalidates:\n{out}"
        )

    def test_an_empty_run_says_so_rather_than_looking_clean(self, rep: ModuleType) -> None:
        """No campaigns is not the same as everything passing, and must not read like it."""
        doc = _document()
        doc["mutants"] = []

        out = rep.render_summary(doc)

        assert "NOT_RUN" in out or "no campaigns ran" in out

        out = rep.render_summary(doc)

        assert "no campaigns" in out.lower() or "0 campaign" in out.lower()


class TestRenderSummaryShowsWhatBroke:
    """RED-E.1 — the sentence every author is made to write must reach the reader.

    `breaks` is required of every authored mutant, and its whole justification is that a survival
    is unreadable without it: the report can say a test did not object, but not to *what*. It was
    carried through the loader and shown nowhere, so the field was a tax on authors that bought
    nothing at read time — and Stage E, which made it conditional on `origin`, is where that
    became obvious.
    """

    def _record(self, breaks: str | None) -> dict:
        return {
            "schema": 1,
            "session": {"started_at": "2026-08-20T00:00:00+00:00", "head": "abc", "dirty": False},
            "mutants": [
                {
                    "id": "F FR-1 m",
                    "verdict": "UNPROTECTED",
                    "reason": "no-killer",
                    "explanation": "no test noticed the behaviour disappearing",
                    "breaks": breaks,
                    "confirmed": False,
                    "drift": "OK",
                }
            ],
        }

    def test_a_survival_says_what_stopped_working(self, rep: ModuleType) -> None:
        out = rep.render_summary(self._record("the bind address is ignored"))

        assert "the bind address is ignored" in out

    def test_a_mutant_with_nothing_to_say_still_renders(self, rep: ModuleType) -> None:
        """[Graceful] A derived mutant carries no `breaks`, and must not blank the line or crash."""
        out = rep.render_summary(self._record(None))

        assert "F FR-1 m" in out
        assert "no-killer" in out

    def test_a_protected_mutant_is_not_narrated(self, rep: ModuleType) -> None:
        """The control: twenty-six passing lines would bury the two that matter."""
        record = self._record("the bind address is ignored")
        record["mutants"][0]["verdict"] = "PROTECTED"

        assert "the bind address is ignored" not in rep.render_summary(record)
