# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""Tests for scripts/check_fr_coverage.py — the design→plan→test FR ledger.

The defect this pins (INT-US-21 §Research, gap 4): `D-INTL-02` §6.2 promised
``<name>_decomposition.yaml`` plus stub component specs. The promise was never carried into an
implementation plan, no test asserted it, and it silently evaporated — surfacing 8 months later
as work for the *integration* story that assumed it already existed.

`scripts/` is not an importable package, so the module under test is loaded by path.

This file is marked fixture data: it names a real story above and feeds requirement ids to the
function under test, which together used to read as proof and credited that story with eight
requirements this file asserts nothing about. The tests for that exclusion live in
`test_fr_coverage_fixture_exclusion.py` — they cannot live here, because the marker would discard
their own citation.
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
SCRIPT = REPO_ROOT / "scripts" / "check_fr_coverage.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_fr_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_fr_coverage"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    assert SCRIPT.exists(), f"script not found: {SCRIPT}"
    return _load()


DESIGN_WITH_TABLE = """\
# Design: Something

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | First thing | Engine | does | happens |
| FR-2 | Second thing | Engine | does | happens |
| FR-10 | Tenth thing | Engine | does | happens |

## Sub-Feature Breakdown
- **FRs**: [FR-1, FR-2]
"""


# ---------------------------------------------------------------------------
# Design FR table parsing
# ---------------------------------------------------------------------------


class TestParseDesignFrs:
    """Only the FR table is authoritative — prose mentions must not invent FRs."""

    def test_extracts_table_rows_in_order(self, mod: ModuleType) -> None:
        assert mod.parse_design_frs(DESIGN_WITH_TABLE) == ["FR-1", "FR-2", "FR-10"]

    def test_prose_mention_is_not_an_fr_row(self, mod: ModuleType) -> None:
        """`**FRs**: [FR-1, FR-2]` in the SF breakdown must not register FR-99."""
        text = DESIGN_WITH_TABLE + "\nSee FR-99 for details, and FR-7 elsewhere.\n"
        assert "FR-99" not in mod.parse_design_frs(text)
        assert "FR-7" not in mod.parse_design_frs(text)

    def test_fr_10_is_not_read_as_fr_1(self, mod: ModuleType) -> None:
        frs = mod.parse_design_frs("| FR-10 | x | y | z | w |\n")
        assert frs == ["FR-10"]

    def test_no_table_yields_nothing(self, mod: ModuleType) -> None:
        assert mod.parse_design_frs("# Design\n\nNo requirements yet.\n") == []

    def test_duplicate_rows_are_deduplicated(self, mod: ModuleType) -> None:
        text = "| FR-1 | a | b | c | d |\n| FR-1 | a | b | c | d |\n"
        assert mod.parse_design_frs(text) == ["FR-1"]

    def test_leading_whitespace_and_bold_ids(self, mod: ModuleType) -> None:
        assert mod.parse_design_frs("  |  FR-3  | a | b |\n") == ["FR-3"]

    def test_empty_and_none_safe(self, mod: ModuleType) -> None:
        assert mod.parse_design_frs("") == []


# ---------------------------------------------------------------------------
# Free-text FR collection (plans, tests)
# ---------------------------------------------------------------------------


class TestCollectFrs:
    def test_collects_all_mentions(self, mod: ModuleType) -> None:
        assert mod.collect_frs("covers FR-2 and FR-10 (not FR2, not XFR-3)") == {"FR-2", "FR-10"}

    def test_fr_10_distinct_from_fr_1(self, mod: ModuleType) -> None:
        assert mod.collect_frs("FR-10 only") == {"FR-10"}

    def test_no_mentions(self, mod: ModuleType) -> None:
        assert mod.collect_frs("nothing here") == set()

    def test_lowercase_is_not_matched(self, mod: ModuleType) -> None:
        """The convention is uppercase; matching `fr-1` would catch prose accidents."""
        assert mod.collect_frs("fr-1") == set()


# ---------------------------------------------------------------------------
# Test-tree citation scan
# ---------------------------------------------------------------------------


class TestCitedFrsInTests:
    """A citation counts only inside a file that names the story."""

    def test_file_mentioning_story_contributes_its_frs(
        self, mod: ModuleType, tmp_path: Path
    ) -> None:
        (tmp_path / "test_a.py").write_text(
            '"""INT-US-21 FR-2: hydration bridge."""\n', encoding="utf-8"
        )
        cited = mod.cited_frs_in_tests(tmp_path, "INT-US-21")
        assert set(cited) == {"FR-2"}
        assert cited["FR-2"] == ["test_a.py"]

    def test_file_without_story_is_ignored(self, mod: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "test_b.py").write_text('"""FR-2 of some other story."""\n', encoding="utf-8")
        assert mod.cited_frs_in_tests(tmp_path, "INT-US-21") == {}

    def test_multiple_files_per_fr_are_collected(self, mod: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "test_c.py").write_text("# INT-US-21 FR-3\n", encoding="utf-8")
        sub = tmp_path / "nested"
        sub.mkdir()
        (sub / "test_d.py").write_text("# INT-US-21 FR-3\n", encoding="utf-8")
        cited = mod.cited_frs_in_tests(tmp_path, "INT-US-21")
        assert sorted(cited["FR-3"]) == ["nested/test_d.py", "test_c.py"]

    def test_non_python_files_are_ignored(self, mod: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "notes.md").write_text("INT-US-21 FR-4\n", encoding="utf-8")
        assert mod.cited_frs_in_tests(tmp_path, "INT-US-21") == {}

    def test_pycache_is_skipped(self, mod: ModuleType, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "test_e.py").write_text("INT-US-21 FR-5\n", encoding="utf-8")
        assert mod.cited_frs_in_tests(tmp_path, "INT-US-21") == {}

    def test_undecodable_file_does_not_crash_the_sweep(
        self, mod: ModuleType, tmp_path: Path
    ) -> None:
        """Graceful degradation: one bad file must not hide the rest of the tree."""
        (tmp_path / "test_bad.py").write_bytes(b"\xff\xfe\x00garbage\x00")
        (tmp_path / "test_good.py").write_text("# INT-US-21 FR-6\n", encoding="utf-8")
        cited = mod.cited_frs_in_tests(tmp_path, "INT-US-21")
        assert set(cited) == {"FR-6"}

    def test_missing_tree_returns_empty(self, mod: ModuleType, tmp_path: Path) -> None:
        assert mod.cited_frs_in_tests(tmp_path / "nope", "INT-US-21") == {}


# ---------------------------------------------------------------------------
# Story id hygiene (hostile input)
# ---------------------------------------------------------------------------


class TestStoryIdValidation:
    def test_normal_id_accepted(self, mod: ModuleType) -> None:
        assert mod.normalize_story_id(" int-us-21 ") == "INT-US-21"

    @pytest.mark.parametrize("bad", ["INT*US*21", "../../etc/passwd", "IN[T]-21", "", "a b"])
    def test_metacharacters_and_traversal_rejected(self, mod: ModuleType, bad: str) -> None:
        """A glob/regex metacharacter in the id must be refused, not interpolated."""
        with pytest.raises(ValueError):
            mod.normalize_story_id(bad)


# ---------------------------------------------------------------------------
# End-to-end via main()
# ---------------------------------------------------------------------------


def _story_tree(tmp_path: Path, design: str, plans: dict[str, str]) -> tuple[Path, Path]:
    features = tmp_path / "features"
    story_dir = features / "topic_08_integration" / "TEST-US-1"
    story_dir.mkdir(parents=True)
    (story_dir / "TEST-US-1_design.md").write_text(design, encoding="utf-8")
    for name, body in plans.items():
        (story_dir / name).write_text(body, encoding="utf-8")
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    return features, tests_root


class TestMain:
    def test_fully_covered_story_passes(self, mod: ModuleType, tmp_path: Path) -> None:
        design = "| FR-1 | a | b | c | d |\n| FR-2 | a | b | c | d |\n"
        features, tests_root = _story_tree(
            tmp_path, design, {"TEST-US-1_implementation_plan.md": "covers FR-1 and FR-2"}
        )
        (tests_root / "test_x.py").write_text("# TEST-US-1 FR-1 FR-2\n", encoding="utf-8")
        assert (
            mod.main(
                ["TEST-US-1", "--features-root", str(features), "--tests-root", str(tests_root)]
            )
            == 0
        )

    def test_fr_missing_from_plan_blocks(self, mod: ModuleType, tmp_path: Path) -> None:
        design = "| FR-1 | a | b | c | d |\n| FR-2 | a | b | c | d |\n"
        features, tests_root = _story_tree(
            tmp_path, design, {"TEST-US-1_implementation_plan.md": "covers FR-1 only"}
        )
        (tests_root / "test_x.py").write_text("# TEST-US-1 FR-1 FR-2\n", encoding="utf-8")
        assert (
            mod.main(
                ["TEST-US-1", "--features-root", str(features), "--tests-root", str(tests_root)]
            )
            == 1
        )

    def test_fr_missing_from_tests_blocks(self, mod: ModuleType, tmp_path: Path) -> None:
        design = "| FR-1 | a | b | c | d |\n| FR-2 | a | b | c | d |\n"
        features, tests_root = _story_tree(
            tmp_path, design, {"TEST-US-1_implementation_plan.md": "covers FR-1 and FR-2"}
        )
        (tests_root / "test_x.py").write_text("# TEST-US-1 FR-1\n", encoding="utf-8")
        assert (
            mod.main(
                ["TEST-US-1", "--features-root", str(features), "--tests-root", str(tests_root)]
            )
            == 1
        )

    def test_no_plan_at_all_blocks(self, mod: ModuleType, tmp_path: Path) -> None:
        features, tests_root = _story_tree(tmp_path, "| FR-1 | a | b | c | d |\n", {})
        (tests_root / "test_x.py").write_text("# TEST-US-1 FR-1\n", encoding="utf-8")
        assert (
            mod.main(
                ["TEST-US-1", "--features-root", str(features), "--tests-root", str(tests_root)]
            )
            == 1
        )

    def test_design_without_fr_table_blocks_rather_than_passing_vacuously(
        self, mod: ModuleType, tmp_path: Path
    ) -> None:
        """Zero FRs parsed must FAIL: otherwise a parser break reads as full coverage."""
        features, tests_root = _story_tree(
            tmp_path, "# Design\n\nNo table here.\n", {"TEST-US-1_implementation_plan.md": "x"}
        )
        assert (
            mod.main(
                ["TEST-US-1", "--features-root", str(features), "--tests-root", str(tests_root)]
            )
            == 1
        )

    def test_missing_design_doc_blocks_cleanly(self, mod: ModuleType, tmp_path: Path) -> None:
        features = tmp_path / "features"
        features.mkdir()
        tests_root = tmp_path / "tests"
        tests_root.mkdir()
        assert (
            mod.main(
                ["NOPE-US-9", "--features-root", str(features), "--tests-root", str(tests_root)]
            )
            == 1
        )

    def test_bad_story_id_blocks_cleanly(self, mod: ModuleType, tmp_path: Path) -> None:
        assert (
            mod.main(["../etc", "--features-root", str(tmp_path), "--tests-root", str(tmp_path)])
            == 1
        )

    def test_multiple_plans_are_unioned(self, mod: ModuleType, tmp_path: Path) -> None:
        design = "| FR-1 | a | b | c | d |\n| FR-2 | a | b | c | d |\n"
        features, tests_root = _story_tree(
            tmp_path,
            design,
            {
                "TEST-US-1_sf01_implementation_plan.md": "covers FR-1",
                "TEST-US-1_sf02_implementation_plan.md": "covers FR-2",
            },
        )
        (tests_root / "test_x.py").write_text("# TEST-US-1 FR-1 FR-2\n", encoding="utf-8")
        assert (
            mod.main(
                ["TEST-US-1", "--features-root", str(features), "--tests-root", str(tests_root)]
            )
            == 0
        )


class TestParseDesignFrsBulletForm:
    """`TECH-048`: an FR declared as a bullet counts. The parser required a table; nothing else did.

    `specweaver-design` phase-3 Section A mandates that each FR be numbered, unambiguous, testable
    and structured (Actor + Action + Outcome). It says **nothing about a table**. So `C-SENS-02` and
    `D-SENS-03`, which declare their FRs as bullets, are conforming — and the checker reported
    `no FR rows parsed` for both, which from the outside is indistinguishable from a design that
    states no requirements at all.

    The table-only rule was not arbitrary: it kept prose like `**FRs**: [FR-1, FR-2]` in a
    sub-feature breakdown from inventing ledger entries the story can never satisfy. That
    protection is preserved by requiring the id to be the SUBJECT of the line — `FR-N` directly
    after the bullet marker, followed by a colon — rather than merely present on it.
    """

    def test_a_bold_bullet_declaration_counts(self, mod: ModuleType) -> None:
        text = "- **FR-1:** The Engine must enforce structural exclusions.\n"

        assert mod.parse_design_frs(text) == ["FR-1"]

    def test_the_asterisk_bullet_form_counts(self, mod: ModuleType) -> None:
        """`D-SENS-03` uses `*   **FR-1:**` — a different marker and padding."""
        text = "*   **FR-2:** The system SHALL parse C and C++ source files.\n"

        assert mod.parse_design_frs(text) == ["FR-2"]

    def test_table_rows_still_count(self, mod: ModuleType) -> None:
        text = "| FR-1 | Execution | System | Parses a spec |\n"

        assert mod.parse_design_frs(text) == ["FR-1"]

    def test_a_plural_reference_does_not_declare(self, mod: ModuleType) -> None:
        """The protection the table-only rule was carrying: a breakdown line is not a declaration."""
        text = "- **FRs**: [FR-1, FR-2, FR-3]\n"

        assert mod.parse_design_frs(text) == []

    def test_a_prose_reference_does_not_declare(self, mod: ModuleType) -> None:
        text = "- See FR-5's correction, which supersedes FR-2.\n"

        assert mod.parse_design_frs(text) == []

    def test_declaration_and_table_forms_deduplicate(self, mod: ModuleType) -> None:
        text = "- **FR-1:** Stated as a bullet.\n\n| FR-1 | and again as a row |\n"

        assert mod.parse_design_frs(text) == ["FR-1"]

    def test_document_order_is_preserved_across_forms(self, mod: ModuleType) -> None:
        text = "- **FR-2:** second.\n| FR-1 | first by number, second in the document |\n"

        assert mod.parse_design_frs(text) == ["FR-2", "FR-1"]

    def test_the_two_real_designs_now_parse(self, mod: ModuleType) -> None:
        """The live cases. Both were reported as having no requirements at all."""
        import pathlib

        root = (
            pathlib.Path(__file__).resolve().parents[3] / "docs/roadmap/features/topic_02_sensors"
        )
        c = mod.parse_design_frs(
            (root / "C-SENS-02/C-SENS-02_design.md").read_text(encoding="utf-8")
        )
        d = mod.parse_design_frs(
            (root / "D-SENS-03/D-SENS-03_design.md").read_text(encoding="utf-8")
        )

        assert c == ["FR-1", "FR-2", "FR-3", "FR-4", "FR-5"]
        assert len(d) >= 6


class TestDeclaredFrsFromText:
    """`TECH-048`: "no FRs declared" and "FRs present but unreadable" are different failures.

    Collapsed into one message they are indistinguishable from outside — and the second is the one
    that matters, because it means the gate's reach silently shrank. Every new design format that
    the parser does not know removes a capability from coverage while reporting the same words as a
    design that genuinely promised nothing.
    """

    def test_a_design_with_no_requirements_says_so(self, mod: ModuleType) -> None:
        frs, err = mod.declared_frs_from_text("# Design\n\nProse only.\n", "X_design.md")

        assert frs == []
        assert "states no Functional Requirements" in err

    def test_a_design_with_unreadable_requirements_says_that_instead(self, mod: ModuleType) -> None:
        """`FR-` ids are present, so something was promised — the parser just cannot read it."""
        text = "# Design\n\nRequirements: FR-1 and FR-2 are handled inline in the prose.\n"

        frs, err = mod.declared_frs_from_text(text, "X_design.md")

        assert frs == []
        assert "cannot read" in err
        assert "FR-1" in err

    def test_the_unreadable_message_names_the_ids_it_saw(self, mod: ModuleType) -> None:
        """So a reader can check the design against the parser without opening both."""
        text = "Mentions FR-3 and FR-7 without declaring either.\n"

        _, err = mod.declared_frs_from_text(text, "X_design.md")

        assert "FR-3" in err and "FR-7" in err

    def test_a_readable_design_reports_no_error(self, mod: ModuleType) -> None:
        frs, err = mod.declared_frs_from_text("- **FR-1:** Something testable.\n", "X_design.md")

        assert frs == ["FR-1"]
        assert err is None


class TestOwnFrMentions:
    """An FR belonging to ANOTHER story is a reference, not an unreadable declaration.

    `TECH-048`, caught by running the new message across all 61 capabilities rather than trusting
    it: `B-EXEC-04` cites `C-EXEC-02 FR-11` and `C-FLOW-12` cites `INT-US-21's FR-9(a)`. Both are
    stubs with no requirements of their own, and both were reported as "cannot read them as
    declarations" — pointing a reader at a parser bug that does not exist.

    A design that references a neighbour's requirement is doing the right thing; saying so must not
    look like a defect.
    """

    def test_a_foreign_fr_does_not_imply_unreadable(self, mod: ModuleType) -> None:
        text = "`C-EXEC-02 FR-11` promises that a fork-bombing script is capped by default.\n"

        frs, err = mod.declared_frs_from_text(text, "B-EXEC-04_design.md")

        assert frs == []
        assert "states no Functional Requirements" in err

    def test_the_possessive_form_is_also_foreign(self, mod: ModuleType) -> None:
        text = "INT-US-21's `FR-9(a)` attempted exactly that and was descoped.\n"

        _, err = mod.declared_frs_from_text(text, "C-FLOW-12_design.md")

        assert "states no Functional Requirements" in err

    def test_an_unqualified_mention_is_still_unreadable(self, mod: ModuleType) -> None:
        """The real case must survive: an unowned `FR-1` in prose is this design's, and unreadable."""
        text = "Requirements: FR-1 and FR-2 are handled inline in the prose.\n"

        _, err = mod.declared_frs_from_text(text, "X_design.md")

        assert "cannot read" in err

    def test_a_design_with_both_reports_only_its_own(self, mod: ModuleType) -> None:
        text = "Builds on `C-EXEC-02 FR-11`. Our own FR-4 is described in prose below.\n"

        _, err = mod.declared_frs_from_text(text, "X_design.md")

        assert "cannot read" in err
        assert "FR-4" in err
        assert "FR-11" not in err


# ---------------------------------------------------------------------------
# The reverse direction: a citation naming a requirement no design declares
# ---------------------------------------------------------------------------


DESIGN_WITH_BOTH_TABLES = """\
# Design: Something

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | First thing | Engine | does | happens |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Speed | under 50ms |
"""


class TestDanglingCitations:
    """The ledger was one-directional, and the missing direction hid real defects.

    It asked *is every declared FR cited* and never *does every citation name a declared FR*. So a
    test could carry `Proves: TECH-056 FR-2` against a design that declares one FR and says so in
    its own words — and the check printed `3 of 1 requirement(s)` and exited 0.

    Measured across the repo on 2026-08-27: eight citations name a requirement neither table
    declares, on six stories. `A-VAL-01 FR-6` is the one that proves the class matters — the citing
    file's own docstring already explains that a cross-story text scan invented it, so a previous
    session diagnosed this by hand and no gate has caught it since.

    A dangling citation is not a cosmetic problem. It is proof credited to a requirement that does
    not exist, which is indistinguishable from proof of one that does.
    """

    @staticmethod
    def _story(tmp_path: Path, design: str, test_body: str) -> tuple[Path, Path]:
        """A story complete enough that only a dangling citation can block it.

        The implementation plan is not scenery. Without one, `missing_from_plan` blocks every
        fixture story regardless — so `test_main_blocks_on_a_dangling_citation` passed with the
        dangling rule deleted, and the mutant that removed it was SILENT. A guard that cannot fail
        is not a guard, and this fixture is where that one hid.
        """
        features = tmp_path / "features" / "topic" / "X-Y-01"
        features.mkdir(parents=True)
        (features / "X-Y-01_design.md").write_text(design, encoding="utf-8")
        (features / "X-Y-01_implementation_plan.md").write_text(
            "# Plan\n\n**FRs owned: FR-1.**\n", encoding="utf-8"
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_thing.py").write_text(test_body, encoding="utf-8")
        return tmp_path / "features", tests

    def test_an_fr_the_design_does_not_declare_is_reported(
        self, mod: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] the `TECH-056 FR-2` shape, reduced."""
        features, tests = self._story(
            tmp_path, DESIGN_WITH_BOTH_TABLES, '"""Proves: X-Y-01 FR-2"""\n'
        )

        dangling = mod.dangling_citations(features, tests, "X-Y-01")

        assert "FR-2" in dangling, "a citation of an undeclared FR was not reported"
        assert dangling["FR-2"] == ["test_thing.py"]

    def test_an_nfr_the_design_declares_is_not_dangling(
        self, mod: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] the trap that makes a naive version useless.

        NFRs are declared in their own table. A reverse check comparing every citation against the
        **FR** table alone reports each of them as dangling: measured, that is 62 false positives
        against 8 true ones, and a check that is 89% noise gets switched off in a week.
        """
        features, tests = self._story(
            tmp_path, DESIGN_WITH_BOTH_TABLES, '"""Proves: X-Y-01 FR-1, X-Y-01 NFR-1"""\n'
        )

        assert mod.dangling_citations(features, tests, "X-Y-01") == {}

    def test_an_nfr_no_table_declares_is_dangling(self, mod: ModuleType, tmp_path: Path) -> None:
        """[Graceful degradation] `TECH-065`: a design with no NFR table, cited for `NFR-2`.

        Absent table and empty table must read the same. A design that declares no NFRs cannot have
        one proven.
        """
        features, tests = self._story(
            tmp_path,
            "# Design\n\n## Functional Requirements\n\n| FR-1 | a | b | c | d |\n",
            '"""Proves: X-Y-01 NFR-2"""\n',
        )

        assert "NFR-2" in mod.dangling_citations(features, tests, "X-Y-01")

    def test_a_fixture_id_is_exempt(self, mod: ModuleType, tmp_path: Path) -> None:
        """[Boundary] `tests/CLAUDE.md` tells authors to give fixtures ids the design does not
        declare, and names `FR-98`. The convention deliberately produces a dangling id, so the
        check must honour it or contradict a rule already in use.

        The floor is a property of the id, not of the file: the existing `fixture-data` marker is
        file-level and would discard that file's real citations too.
        """
        features, tests = self._story(
            tmp_path, DESIGN_WITH_BOTH_TABLES, '"""X-Y-01 FR-98 and X-Y-01 FR-99 are fixtures"""\n'
        )

        assert mod.dangling_citations(features, tests, "X-Y-01") == {}

    def test_the_id_below_the_floor_is_still_checked(self, mod: ModuleType, tmp_path: Path) -> None:
        """[Boundary] the other side of the fence. `FR-89` is a requirement id, not a fixture."""
        features, tests = self._story(
            tmp_path, DESIGN_WITH_BOTH_TABLES, '"""Proves: X-Y-01 FR-89"""\n'
        )

        assert "FR-89" in mod.dangling_citations(features, tests, "X-Y-01")

    def test_a_clean_story_reports_nothing(self, mod: ModuleType, tmp_path: Path) -> None:
        """[Happy] the control. A check that fired on everything would be switched off."""
        features, tests = self._story(
            tmp_path, DESIGN_WITH_BOTH_TABLES, '"""Proves: X-Y-01 FR-1"""\n'
        )

        assert mod.dangling_citations(features, tests, "X-Y-01") == {}

    def test_main_blocks_on_a_dangling_citation(
        self, mod: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """[Hostile] the whole point — it must change the exit code, not only the prose."""
        features, tests = self._story(
            tmp_path,
            DESIGN_WITH_BOTH_TABLES,
            '"""Proves: X-Y-01 FR-1, X-Y-01 NFR-1, X-Y-01 FR-2"""\n',
        )

        code = mod.main(["X-Y-01", "--features-root", str(features), "--tests-root", str(tests)])

        out = capsys.readouterr().out
        assert code == 1, "a dangling citation was reported and the story still passed"
        assert "FR-2" in out
        assert "carried by no implementation plan" not in out, (
            "this story blocked for a different reason, so it proves nothing about dangling "
            f"citations: {out}"
        )
        assert "cited by no test file" not in out, out


class TestPrintLedgerRatio:
    """`3 of 1 requirement(s)` was printed by the shipped checker, and it exited 0.

    The numerator counted every strictly-cited id including NFRs; the denominator counted FR rows
    only. A ratio above 1 is not a display bug — it is the reverse check missing, stated in
    arithmetic, and it was on screen every time anyone ran the tool on `TECH-056`.
    """

    def test_the_numerator_counts_only_declared_frs(
        self, mod: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        features = tmp_path / "features" / "topic" / "X-Y-02"
        features.mkdir(parents=True)
        (features / "X-Y-02_design.md").write_text(DESIGN_WITH_BOTH_TABLES, encoding="utf-8")
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_t.py").write_text(
            '"""Proves: X-Y-02 FR-1, X-Y-02 NFR-1"""\n', encoding="utf-8"
        )

        mod.main(
            ["X-Y-02", "--features-root", str(tmp_path / "features"), "--tests-root", str(tests)]
        )

        out = capsys.readouterr().out
        assert "1 of 1 requirement(s)" in out, out
