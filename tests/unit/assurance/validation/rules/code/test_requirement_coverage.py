# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Per requirement of one spec: do the coder's tests, the scenario tests, both or neither cover it.

Proves: B-FLOW-01 FR-13

Real test files, read by the real analyzers.

| Bucket | Case |
|---|---|
| Happy | one requirement each: both, coder, scenario, none |
| Boundary | a lettered id is its own requirement; a spec with no ids reports nothing |
| Degradation | no scenario store, or a store not made yet: the scenario side covers nothing |
| Hostile | a traced id the spec does not have is not reported; a file that is not a test counts for nothing |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.validation.rules.code.c09_traceability import requirement_coverage

if TYPE_CHECKING:
    from pathlib import Path

_SPEC = "## Functional Requirements\n\n| FR-1 | a |\n| FR-2 | b |\n| FR-3 | c |\n| NFR-1 | d |\n"


def _test(folder: Path, name: str, *ids: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f"def test_{i}():  # @trace({rid})\n    assert 1 + 1 == 2\n" for i, rid in enumerate(ids)
    )
    (folder / name).write_text(body or "x = 1\n", encoding="utf-8")


def test_each_requirement_gets_its_side(tmp_path: Path) -> None:
    project, store = tmp_path / "project", tmp_path / "store"
    _test(project / "tests", "test_greet.py", "FR-1", "FR-2")
    _test(store / "generated", "test_greet_scenarios.py", "FR-1", "FR-3")

    assert requirement_coverage(_SPEC, project, store) == {
        "FR-1": "both",
        "FR-2": "coder",
        "FR-3": "scenario",
        "NFR-1": "none",
    }


def test_a_lettered_id_is_its_own_requirement(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _test(project / "tests", "test_greet.py", "FR-5")

    coverage = requirement_coverage("| FR-5 | a |\n| FR-5a | b |\n", project, None)

    assert coverage == {"FR-5": "coder", "FR-5a": "none"}


def test_a_spec_without_ids_reports_nothing(tmp_path: Path) -> None:
    _test(tmp_path / "tests", "test_greet.py", "FR-1")

    assert requirement_coverage("# Greet\n\nNo ids here.\n", tmp_path, None) == {}


def test_without_a_store_the_scenario_side_covers_nothing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _test(project / "tests", "test_greet.py", "FR-1")

    for store in (None, tmp_path / "not-made-yet"):
        coverage = requirement_coverage(_SPEC, project, store)
        assert coverage["FR-1"] == "coder"
        assert coverage["FR-3"] == "none"


def test_ids_outside_the_spec_and_non_tests_count_for_nothing(tmp_path: Path) -> None:
    project, store = tmp_path / "project", tmp_path / "store"
    _test(project / "tests", "test_greet.py", "FR-9")
    _test(project / "tests", "helpers.py", "FR-2")
    _test(store / "generated", "test_greet_scenarios.py", "FR-77")

    coverage = requirement_coverage(_SPEC, project, store)

    assert set(coverage) == {"FR-1", "FR-2", "FR-3", "NFR-1"}
    assert set(coverage.values()) == {"none"}
