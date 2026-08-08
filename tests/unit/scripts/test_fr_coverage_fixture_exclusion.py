# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The citation scan must ignore files whose requirement strings are fixture data.

`check_fr_coverage.py` credits a requirement when a file under `tests/` names the story and
mentions the requirement id. Its own test suite does both -- it names the story in the docstring
explaining why the checker exists, and it feeds requirement ids to the function under test as
inputs. Eight of that story's ten requirements were being counted as proven by a file that asserts
nothing whatsoever about it.

Proves: TECH-025 FR-9.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check_fr_coverage.py"

#: A story id that cannot collide with a real one. Naming a real story here would hand it every
#: requirement id in this file -- the exact defect under test, one file over.
STORY = "SAMPLE-1"


#: Requirement ids are assembled rather than written out. A literal id anywhere in this module
#: would be picked up by the very scan under test and credited to TECH-025 -- whose first three
#: requirements are the ledger closures SF-04, SF-05 and SF-06 exist to deliver, so writing them
#: here would let this ticket certify work nobody has done. The `Proves:` tag above is the single
#: literal this file may hold, and TestProvesTagIsTheOnlyFrLiteral pins that. The helper runs at
#: test time, so the files written below still contain the real text the scanner reads.
def _fr(n: int) -> str:
    return f"FR-{n}"


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


def _cited(mod: ModuleType, text: str) -> str:
    """A file body that names the story and cites one requirement."""
    return f'"""{STORY} {text}."""\n'


class TestIsFixtureData:
    """The predicate deciding whether a file declares itself fixture data."""

    def test_marked_text_is_recognised(self, mod: ModuleType) -> None:
        assert mod.is_fixture_data("# fr-coverage: fixture-data\n") is True

    def test_the_marker_constant_matches_the_documented_text(self, mod: ModuleType) -> None:
        """Pinned separately: renaming the marker is a decision, not a refactor."""
        assert mod.FIXTURE_DATA_MARKER == "# fr-coverage: fixture-data"

    def test_unmarked_text_is_not_fixture_data(self, mod: ModuleType) -> None:
        assert mod.is_fixture_data('"""An ordinary test module."""\n') is False

    def test_empty_text_is_not_fixture_data(self, mod: ModuleType) -> None:
        assert mod.is_fixture_data("") is False

    def test_marker_on_the_last_line_of_the_window_is_recognised(self, mod: ModuleType) -> None:
        text = "\n".join(["# filler"] * 9 + [mod.FIXTURE_DATA_MARKER])

        assert mod.is_fixture_data(text) is True

    def test_marker_past_the_window_is_ignored(self, mod: ModuleType) -> None:
        """The window is a real boundary, not 'somewhere near the top'."""
        text = "\n".join(["# filler"] * 10 + [mod.FIXTURE_DATA_MARKER])

        assert mod.is_fixture_data(text) is False

    def test_marker_prefix_of_a_longer_token_is_not_recognised(self, mod: ModuleType) -> None:
        """Hostile: a bare substring check would accept this and silently hide a real proof."""
        assert mod.is_fixture_data("# fr-coverage: fixture-database\n") is False

    def test_indented_marker_is_not_recognised(self, mod: ModuleType) -> None:
        """Column 0 is required. Exempting a file is a file-level declaration, and anything
        indented is inside something else -- a docstring, a function body, a data literal.
        """
        assert mod.is_fixture_data(f"    {mod.FIXTURE_DATA_MARKER}\n") is False

    def test_marker_quoted_in_a_docstring_does_not_exempt_the_file(self, mod: ModuleType) -> None:
        """Hostile, and the reason column 0 matters.

        A module that *documents* the marker within the scan window would otherwise exempt
        itself, silently discarding whatever it genuinely proves. Silent exclusion is the worst
        failure this predicate can have: the gate stays green and the proof stops counting.
        """
        text = (
            '"""Helper conventions.\n'
            "\n"
            "Mark a fixture-heavy module by putting this line at the top of the file::\n"
            "\n"
            f"    {mod.FIXTURE_DATA_MARKER}\n"
            '"""\n'
        )

        assert mod.is_fixture_data(text) is False


class TestMarkerOnTheRealTree:
    """The marker is only worth anything if it is actually on the file that needs it."""

    def test_the_checker_own_test_module_declares_itself_fixture_data(
        self, mod: ModuleType
    ) -> None:
        """Deleting the marker line breaks no other test in this boundary. This is that test."""
        target = REPO_ROOT / "tests" / "unit" / "scripts" / "test_check_fr_coverage.py"

        assert mod.is_fixture_data(target.read_text(encoding="utf-8")) is True

    def test_a_sibling_module_does_not(self, mod: ModuleType) -> None:
        """Control: proves the assertion above is about the marker, not about the directory."""
        sibling = REPO_ROOT / "tests" / "unit" / "scripts" / "test_tests_runner.py"

        assert mod.is_fixture_data(sibling.read_text(encoding="utf-8")) is False


class TestCitedFrsInTests:
    """The sweep must honour the marker, and only for the file carrying it."""

    def test_marked_file_contributes_no_citations(self, mod: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "test_a.py").write_text(
            f"{mod.FIXTURE_DATA_MARKER}\n{_cited(mod, _fr(2))}", encoding="utf-8"
        )

        assert mod.cited_frs_in_tests(tmp_path, STORY) == {}

    def test_identical_unmarked_file_still_contributes(
        self, mod: ModuleType, tmp_path: Path
    ) -> None:
        """Control for the test above. Without it, that one could pass for an unrelated reason."""
        (tmp_path / "test_a.py").write_text(_cited(mod, _fr(2)), encoding="utf-8")

        assert mod.cited_frs_in_tests(tmp_path, STORY) == {_fr(2): ["test_a.py"]}

    def test_marker_skips_only_the_marked_file(self, mod: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "test_marked.py").write_text(
            f"{mod.FIXTURE_DATA_MARKER}\n{_cited(mod, _fr(3))}", encoding="utf-8"
        )
        (tmp_path / "test_plain.py").write_text(_cited(mod, _fr(4)), encoding="utf-8")

        cited = mod.cited_frs_in_tests(tmp_path, STORY)

        assert cited == {_fr(4): ["test_plain.py"]}

    def test_marked_and_undecodable_file_does_not_abort_the_sweep(
        self, mod: ModuleType, tmp_path: Path
    ) -> None:
        """Graceful degradation: the new skip sits on the same chain as the undecodable guard."""
        (tmp_path / "test_bad.py").write_bytes(b"\xff\xfe\x00garbage\x00")
        (tmp_path / "test_good.py").write_text(_cited(mod, _fr(6)), encoding="utf-8")

        assert mod.cited_frs_in_tests(tmp_path, STORY) == {_fr(6): ["test_good.py"]}


class TestProvesTagIsTheOnlyFrLiteral:
    """This module must not credit TECH-025 with the ledger closures it has not done."""

    def test_module_source_holds_exactly_one_requirement_literal(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")

        assert len(re.findall(r"(?<![\w-])FR-\d+(?![\w-])", source)) == 1
