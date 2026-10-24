# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The code rules that locate files near the code stay inside the run's project.

Proves: TECH-077 FR-9

`execute_validation_flow` hands the project root to the rules; C02 (tests exist) and C09
(traceability) are run through it on real files.

| Bucket | Case |
|---|---|
| Happy | a test file inside the project is found by C02; the shared search finds the nearest `tests/` inside the project |
| Boundary | with no project root, C02 searches as before |
| Degradation | not applicable — the rules read only the disk |
| Hostile | a matching test file above the project root is never used; C09 judges the run's project, not an enclosing repository |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.pipeline import ValidationPipeline, ValidationStep
from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _run(rule: str, code: Path, root: Path | None) -> Status:
    import specweaver.assurance.validation.rules.code  # noqa: F401

    pipeline = ValidationPipeline(name="one", steps=[ValidationStep(name=rule, rule=rule)])
    results = execute_validation_flow(
        pipeline, code.read_text(encoding="utf-8"), code, project_root=root
    )
    return results[0].status


@pytest.fixture()
def nest(tmp_path: Path) -> tuple[Path, Path]:
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    code = proj / "src" / "orders.py"
    code.write_text("def order():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_orders.py").write_text(
        "def test_o():\n    pass\n", encoding="utf-8"
    )
    return proj, code


def test_a_test_file_above_the_project_is_not_used(nest: tuple[Path, Path]) -> None:
    proj, code = nest

    assert _run("C02", code, proj) == Status.FAIL


def test_a_test_file_inside_the_project_is_found(nest: tuple[Path, Path]) -> None:
    proj, code = nest
    (proj / "tests").mkdir()
    (proj / "tests" / "test_orders.py").write_text("def test_o():\n    pass\n", encoding="utf-8")

    assert _run("C02", code, proj) == Status.PASS


def test_without_a_root_the_search_is_as_before(nest: tuple[Path, Path]) -> None:
    _, code = nest

    assert _run("C02", code, None) == Status.PASS


def test_traceability_judges_the_runs_project(nest: tuple[Path, Path], tmp_path: Path) -> None:
    proj, code = nest
    (tmp_path / ".git").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "outer_spec.md").write_text(
        "## FR-1\nThe outer thing.\n", encoding="utf-8"
    )

    assert _run("C09", code, proj) == Status.PASS


def test_the_test_search_finds_the_nearest_tests_inside_the_project(tmp_path: Path) -> None:
    """C02, C03 and the hydrator share one search (TECH-078); it never looks above the project."""
    from specweaver.assurance.validation.project_root import find_tests

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_bare.py").write_text("def test_o():\n    pass\n", encoding="utf-8")
    pkg = tmp_path / "proj" / "pkg"
    (pkg / "src").mkdir(parents=True)
    (pkg / "tests").mkdir()
    (pkg / "tests" / "test_orders.py").write_text("def test_o():\n    pass\n", encoding="utf-8")
    code = pkg / "src" / "orders.py"
    code.write_text("x = 1\n", encoding="utf-8")
    bare = tmp_path / "proj" / "bare.py"
    bare.write_text("x = 1\n", encoding="utf-8")

    assert find_tests(code, tmp_path / "proj") == pkg / "tests" / "test_orders.py"
    assert find_tests(bare, tmp_path / "proj") == "No test file 'test_bare.py' found"
