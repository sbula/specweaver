# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""Tests for scripts/check_dangling_citations.py — the sweep half of the reverse ledger.

**No `Proves:` tag, deliberately.** This check is new behaviour and no design declares a
requirement for it. `TECH-047` — *Nothing Runs the FR-Coverage Gate Across Delivered Work* — is the
nearest owner and is prose-only, with no FR table to cite. Tagging the closest-looking id would be
the exact false credit this file exists to stop, so it claims nothing.

`check_fr_coverage.py` takes a story id and runs at closure. `development_framework.md` states the
rule this file exists for: **a check that must be invoked to fire reports success by not running.**
Nine dangling citations were sitting in the repo on 2026-08-27, two of them on `TECH-058`, which
is closed — nobody was going to run the story-scoped check on it again.

So the same rule gets a sweep beside `fr_sweep` and `nfr_sweep` in the `doc` gate, and the rule
itself lives once: this script imports `dangling_citations` rather than reimplementing it.

Marked fixture data: it names stories and feeds requirement ids to the function under test, which
under the file-level citation rule would otherwise read as proof.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check_dangling_citations.py"


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    assert SCRIPT.exists(), f"script not found: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("check_dangling_citations", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_dangling_citations"] = module
    spec.loader.exec_module(module)
    return module


DESIGN = """\
# Design

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A thing | Engine | does | happens |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Speed | fast |
"""


def _repo(tmp_path: Path, stories: dict[str, str]) -> tuple[Path, Path]:
    """A features root with one design per story, and a tests root citing what each dict says."""
    features = tmp_path / "features"
    tests = tmp_path / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    for story, citation in stories.items():
        d = features / "topic" / story
        d.mkdir(parents=True)
        (d / f"{story}_design.md").write_text(DESIGN, encoding="utf-8")
        (tests / f"test_{story.lower().replace('-', '_')}.py").write_text(
            f'"""Proves: {citation}"""\n', encoding="utf-8"
        )
    return features, tests


class TestMainSweepsEveryDesign:
    """Every design in the repo, in one command, without naming a story."""

    def test_a_clean_repo_passes(self, mod: ModuleType, tmp_path: Path) -> None:
        """[Happy] the control."""
        features, tests = _repo(tmp_path, {"X-Y-01": "X-Y-01 FR-1, X-Y-01 NFR-1"})

        assert mod.main(["--features-root", str(features), "--tests-root", str(tests)]) == 0

    def test_one_dangling_citation_fails_the_sweep(
        self, mod: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """[Hostile] `TECH-058`'s shape: a closed story nobody will re-run the story check on."""
        features, tests = _repo(tmp_path, {"X-Y-01": "X-Y-01 FR-3"})

        code = mod.main(["--features-root", str(features), "--tests-root", str(tests)])

        assert code == 1
        out = capsys.readouterr().out
        assert "X-Y-01" in out and "FR-3" in out, out

    def test_it_names_the_file_so_the_fix_is_obvious(
        self, mod: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """[Boundary] a finding that does not say where it is costs a grep per row."""
        features, tests = _repo(tmp_path, {"X-Y-01": "X-Y-01 FR-3"})

        mod.main(["--features-root", str(features), "--tests-root", str(tests)])

        assert "test_x_y_01.py" in capsys.readouterr().out

    def test_every_story_is_swept_not_just_the_first_offender(
        self, mod: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """[Boundary] the sweep must not stop at the first failure.

        A check that reports one row per run turns a ten-row cleanup into ten runs, and the second
        row is the one nobody gets to.
        """
        features, tests = _repo(tmp_path, {"X-Y-01": "X-Y-01 FR-3", "X-Y-02": "X-Y-02 NFR-9"})

        mod.main(["--features-root", str(features), "--tests-root", str(tests)])

        out = capsys.readouterr().out
        assert "X-Y-01" in out and "X-Y-02" in out, out

    def test_a_fixture_id_does_not_fail_the_sweep(self, mod: ModuleType, tmp_path: Path) -> None:
        """[Graceful degradation] the sweep must honour the same fixture floor as the story check,
        or the two disagree and one of them is wrong."""
        features, tests = _repo(tmp_path, {"X-Y-01": "X-Y-01 FR-98"})

        assert mod.main(["--features-root", str(features), "--tests-root", str(tests)]) == 0

    def test_no_designs_at_all_is_not_a_silent_pass(
        self, mod: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """[Hostile] a mistyped root finds nothing and would otherwise report a clean repo.

        This is the failure `check_proof_tier` shipped with — zero violations because it never saw
        the documents. A sweep that scanned nothing must say so, not congratulate itself.
        """
        empty = tmp_path / "nothing"
        empty.mkdir()

        code = mod.main(["--features-root", str(empty), "--tests-root", str(empty)])

        assert code == 1, "a sweep that examined no designs reported success"
        assert "no design" in capsys.readouterr().out.lower()


class TestDanglingCitationsIsTheStoryChecksOwnFunction:
    """The sweep and the story check must not drift into two answers."""

    def test_the_sweep_uses_the_story_checks_own_function(self, mod: ModuleType) -> None:
        """[Boundary] `PRINCIPLES.md` §5. Two implementations of one rule agree on the day they
        are written and not reliably after — which is the defect the whole boundary is repairing,
        one level up."""
        # Loaded by path above, so it is in `sys.modules` by now and not importable earlier.
        import check_fr_coverage

        assert mod.dangling_citations is check_fr_coverage.dangling_citations
