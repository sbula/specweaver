# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A spec under an archetype is checked by that archetype's own pipeline, S12 included.

Proves: B-INTL-01 FR-1, FR-4

Nothing is mocked: a real `context.yaml`, the shipped `spring-boot` pipeline, the real Markdown
structure reader. The earlier tests mocked the pipeline loader, which is how the handler asked
for a pipeline that does not exist for years without anyone seeing it.

| Bucket | Case |
|---|---|
| Happy | a spec with both required sections passes S12 |
| Boundary | a spec with no archetype gets the default pipeline, which has no bounds |
| Degradation | an archetype with no pipeline of its own falls back to the default |
| Hostile | a spec missing a required section fails S12, naming the section |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.core.flow.handlers.validation import ValidateSpecHandler

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_FULL = "# Orders\n\n## 1. Purpose\n\nTake orders.\n\n## 2. Boundaries\n\nOnly orders.\n"
_HALF = "# Orders\n\n## 1. Purpose\n\nTake orders.\n"


def _results(tmp_path: Path, spec: str, archetype: str | None) -> dict:
    if archetype:
        (tmp_path / "context.yaml").write_text(f"archetype: {archetype}\n", encoding="utf-8")
    spec_path = tmp_path / "orders_spec.md"
    spec_path.write_text(spec, encoding="utf-8")
    results = ValidateSpecHandler()._run_validation(spec_path, None, project_path=tmp_path)
    return {r.rule_id: r for r in results}


def test_the_archetype_pipeline_bounds_the_spec(tmp_path: Path) -> None:
    assert _results(tmp_path, _FULL, "spring-boot")["S12"].status is Status.PASS


def test_a_missing_required_section_fails_naming_it(tmp_path: Path) -> None:
    s12 = _results(tmp_path, _HALF, "spring-boot")["S12"]

    assert s12.status is Status.FAIL
    assert any("2. Boundaries" in f.message for f in s12.findings)


def test_no_archetype_means_no_bounds(tmp_path: Path) -> None:
    s12 = _results(tmp_path, _HALF, None).get("S12")

    assert s12 is None or s12.status is Status.PASS


def test_an_archetype_without_its_own_pipeline_gets_the_default(tmp_path: Path) -> None:
    results = _results(tmp_path, _HALF, "no-such-archetype")

    assert "S01" in results


def test_a_list_of_headers_fails_instead_of_crashing() -> None:
    from specweaver.assurance.validation.rules.spec.s12_archetype_spec_bounds import (
        S12ArchetypeSpecBoundsRule,
    )

    result = S12ArchetypeSpecBoundsRule(required_headers=["1. Purpose"]).check(_HALF)

    assert result.status is Status.FAIL


def test_the_structure_reader_gets_a_project_relative_path(tmp_path: Path) -> None:
    from specweaver.core.flow.handlers.archetype_pipelines import _inside

    assert _inside(tmp_path / "specs" / "a.md", tmp_path) == "specs/a.md"
    assert _inside(tmp_path.parent / "elsewhere.md", tmp_path) == str(
        tmp_path.parent / "elsewhere.md"
    )


def test_the_archetype_bounds_the_one_s12_step(tmp_path: Path) -> None:
    """The archetype sets the default pipeline's S12 step; it does not add a second one."""
    (tmp_path / "context.yaml").write_text("archetype: spring-boot\n", encoding="utf-8")
    spec_path = tmp_path / "orders_spec.md"
    spec_path.write_text(_HALF, encoding="utf-8")

    results = ValidateSpecHandler()._run_validation(spec_path, None, project_path=tmp_path)

    assert [r.status for r in results if r.rule_id == "S12"] == [Status.FAIL]
