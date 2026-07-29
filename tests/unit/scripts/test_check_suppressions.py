# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the suppression ratchet (`scripts/check_suppressions.py`).

This guard is the one every other gate rests on: each of the others can be switched off one line
at a time, and this is what notices. So it is exercised against input known to be bad AND input
known to be good, and specifically against the self-detection defect found on its first run — it
counted the word `noqa` inside its own docstring and regexes and reported a suppression that did
not exist.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sup() -> ModuleType:
    return _load("check_suppressions")


# ---------------------------------------------------------------------------
# Happy path — each suppression form is counted
# ---------------------------------------------------------------------------


class TestDetection:
    def test_coded_noqa_is_counted_under_its_code(self, sup: ModuleType) -> None:
        assert sup.scan_source("x = 1  # noqa: C901\n")["noqa:C901"] == 1

    def test_several_codes_on_one_line_each_count(self, sup: ModuleType) -> None:
        counts = sup.scan_source("x = 1  # noqa: C901, N802\n")

        assert counts["noqa:C901"] == 1
        assert counts["noqa:N802"] == 1

    def test_coded_type_ignore_is_counted(self, sup: ModuleType) -> None:
        assert sup.scan_source("x = f()  # type: ignore[arg-type]\n")["type-ignore:arg-type"] == 1

    def test_pragma_no_cover_is_counted(self, sup: ModuleType) -> None:
        assert sup.scan_source("if x:  # pragma: no cover\n    pass\n")["pragma:no-cover"] == 1

    def test_file_level_mypy_ignore_is_counted(self, sup: ModuleType) -> None:
        """A whole file silently exempted from mypy is the largest bypass available."""
        assert sup.scan_source("# mypy: ignore-errors\nx = 1\n")["mypy:file-ignore-errors"] == 1


class TestBlanketForms:
    def test_bare_noqa_counts_as_blanket(self, sup: ModuleType) -> None:
        assert sup.scan_source("x = 1  # noqa\n")["noqa:BLANKET"] == 1

    def test_bare_type_ignore_counts_as_blanket(self, sup: ModuleType) -> None:
        assert sup.scan_source("x = f()  # type: ignore\n")["type-ignore:BLANKET"] == 1

    def test_empty_type_ignore_brackets_count_as_blanket(self, sup: ModuleType) -> None:
        assert sup.scan_source("x = f()  # type: ignore[]\n")["type-ignore:BLANKET"] == 1

    def test_uppercase_noqa_is_still_a_suppression(self, sup: ModuleType) -> None:
        assert sup.scan_source("x = 1  # NOQA: C901\n")["noqa:C901"] == 1


# ---------------------------------------------------------------------------
# Hostile — the defect this check shipped with
# ---------------------------------------------------------------------------


class TestOnlyRealCommentsCount:
    def test_noqa_inside_a_docstring_is_not_a_suppression(self, sup: ModuleType) -> None:
        """The exact defect: this checker counted its own prose and reported a phantom."""
        source = '"""Prose explaining that a # noqa is a bypass."""\nx = 1\n'

        assert sup.scan_source(source) == Counter()

    def test_noqa_inside_a_string_literal_is_not_a_suppression(self, sup: ModuleType) -> None:
        source = 'PATTERN = "# noqa: C901"\n'

        assert sup.scan_source(source) == Counter()

    def test_type_ignore_inside_a_string_is_not_a_suppression(self, sup: ModuleType) -> None:
        source = "MSG = 'add a # type: ignore[arg-type] here'\n"

        assert sup.scan_source(source) == Counter()

    def test_a_real_comment_beside_a_string_mention_still_counts_once(
        self, sup: ModuleType
    ) -> None:
        source = 'PATTERN = "# noqa"  # noqa: C901\n'

        counts = sup.scan_source(source)

        assert counts == Counter({"noqa:C901": 1})

    def test_this_very_checker_reports_no_suppressions_of_its_own(self, sup: ModuleType) -> None:
        """Regression lock: the module is dense with the strings it hunts for."""
        source = (REPO_ROOT / "scripts" / "check_suppressions.py").read_text(encoding="utf-8")

        assert sup.scan_source(source) == Counter()


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


class TestDegradation:
    def test_unparseable_source_does_not_crash_the_sweep(self, sup: ModuleType) -> None:
        counts = sup.scan_source("def broken(:\n    x = 1  # noqa: C901\n")

        assert counts["noqa:C901"] == 1

    def test_empty_source_counts_nothing(self, sup: ModuleType) -> None:
        assert sup.scan_source("") == Counter()

    def test_source_with_no_comments_counts_nothing(self, sup: ModuleType) -> None:
        assert sup.scan_source("def f():\n    return 1\n") == Counter()


# ---------------------------------------------------------------------------
# The ratchet itself
# ---------------------------------------------------------------------------


class TestRatchet:
    def test_growth_in_a_category_is_reported(self, sup: ModuleType) -> None:
        grown = sup.compare(Counter({"noqa:C901": 21}), {"noqa:C901": 20})

        assert grown == [("noqa:C901", 20, 21)]

    def test_matching_the_baseline_exactly_is_not_growth(self, sup: ModuleType) -> None:
        assert sup.compare(Counter({"noqa:C901": 20}), {"noqa:C901": 20}) == []

    def test_falling_below_the_baseline_is_not_growth(self, sup: ModuleType) -> None:
        assert sup.compare(Counter({"noqa:C901": 3}), {"noqa:C901": 20}) == []

    def test_an_entirely_new_category_is_growth(self, sup: ModuleType) -> None:
        """Switching to a rule nobody suppressed before must not slip through as 'not in baseline'."""
        grown = sup.compare(Counter({"noqa:PLR0913": 4}), {"noqa:C901": 20})

        assert grown == [("noqa:PLR0913", 0, 4)]

    def test_a_drop_elsewhere_cannot_pay_for_growth_here(self, sup: ModuleType) -> None:
        """Per-category, not per-total: fixing 30 N802 must not buy 5 new C901."""
        grown = sup.compare(
            Counter({"noqa:N802": 10, "noqa:C901": 25}), {"noqa:N802": 40, "noqa:C901": 20}
        )

        assert grown == [("noqa:C901", 20, 25)]

    def test_every_grown_category_is_listed_not_just_the_first(self, sup: ModuleType) -> None:
        grown = sup.compare(
            Counter({"noqa:A001": 2, "noqa:B002": 2}), {"noqa:A001": 1, "noqa:B002": 1}
        )

        assert len(grown) == 2


class TestConfigLevelSuppressions:
    def test_pyproject_per_file_ignores_are_counted(self, sup: ModuleType) -> None:
        """A per-file-ignore silences a whole file in one line — cheaper than any inline comment."""
        counts = sup.scan_config()

        assert counts["config:per-file-ignore:TID251"] >= 1

    def test_config_census_is_not_empty_for_this_repo(self, sup: ModuleType) -> None:
        assert sum(sup.scan_config().values()) > 0
