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
