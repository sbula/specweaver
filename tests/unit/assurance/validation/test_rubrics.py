# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Judgment criteria are content a project can edit; the engine contract is not.

Proves: C-VAL-05 FR-1, C-VAL-05 FR-2, C-VAL-05 FR-3, C-VAL-05 FR-4

"Rules as code, rubrics as content" cuts one line: **what counts as good** is content, **how the
verdict is read** is code. A project that dislikes a review criterion should not need a SpecWeaver
release to change it, and should not be able to break the response parser by trying.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.rubrics import Rubric, RubricNotFoundError, load_rubric
from specweaver.commons.enums.dal import DALLevel

if TYPE_CHECKING:
    from pathlib import Path

SHIPPED = ("spec_review", "code_review")


def _override(project: Path, name: str, body: str) -> Path:
    directory = project / ".specweaver" / "rubrics"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


@pytest.mark.parametrize("rubric_id", SHIPPED)
def test_a_shipped_rubric_loads(rubric_id: str) -> None:
    """FR-1. The criteria are files now, so an install has them without a project."""
    rubric = load_rubric(rubric_id)

    assert isinstance(rubric, Rubric)
    assert rubric.id == rubric_id
    assert rubric.criteria.strip()


@pytest.mark.parametrize("rubric_id", SHIPPED)
def test_a_shipped_rubric_declares_a_version(rubric_id: str) -> None:
    assert load_rubric(rubric_id).version


def test_an_unknown_rubric_is_an_error_not_an_empty_string() -> None:
    """An empty rubric would send the model no criteria and still look like it worked."""
    with pytest.raises(RubricNotFoundError):
        load_rubric("no_such_rubric")


def test_a_project_overrides_a_shipped_rubric(tmp_path: Path) -> None:
    """FR-2. The whole point: tune the criteria to the domain without a release."""
    _override(tmp_path, "spec_review", "---\nid: spec_review\nversion: 9.9\n---\nJudge kindly.\n")

    rubric = load_rubric("spec_review", project_dir=tmp_path)

    assert "Judge kindly." in rubric.criteria
    assert rubric.version == "9.9"


def test_without_an_override_the_shipped_rubric_still_wins(tmp_path: Path) -> None:
    """The control for precedence: an empty project must not silently lose its criteria."""
    rubric = load_rubric("spec_review", project_dir=tmp_path)

    assert rubric.criteria == load_rubric("spec_review").criteria


def test_an_override_of_one_rubric_leaves_the_others_alone(tmp_path: Path) -> None:
    _override(tmp_path, "spec_review", "---\nid: spec_review\nversion: 9.9\n---\nJudge kindly.\n")

    assert load_rubric("code_review", project_dir=tmp_path).criteria == (
        load_rubric("code_review").criteria
    )


def test_a_stricter_dal_selects_its_own_variant() -> None:
    """FR-3. DAL-A is aerospace-grade; it should not be judged by the everyday rubric."""
    strict = load_rubric("spec_review", dal=DALLevel.DAL_A)
    ordinary = load_rubric("spec_review")

    assert strict.criteria != ordinary.criteria
    assert strict.dal is DALLevel.DAL_A


def test_a_dal_without_a_variant_falls_back(tmp_path: Path) -> None:
    """The control for FR-3. A missing variant means the default criteria, never no criteria."""
    rubric = load_rubric("code_review", dal=DALLevel.DAL_A)

    assert rubric.criteria == load_rubric("code_review").criteria
    assert rubric.dal is None


def test_a_project_variant_beats_a_shipped_variant(tmp_path: Path) -> None:
    directory = tmp_path / ".specweaver" / "rubrics"
    directory.mkdir(parents=True)
    (directory / "spec_review.DAL_A.md").write_text(
        "---\nid: spec_review\nversion: 2.0\n---\nProject strictness.\n", encoding="utf-8"
    )

    rubric = load_rubric("spec_review", project_dir=tmp_path, dal=DALLevel.DAL_A)

    assert "Project strictness." in rubric.criteria


def test_the_rubric_records_which_file_judged_the_run(tmp_path: Path) -> None:
    """FR-4. DAL-C auditability: *which* criteria produced this verdict must be answerable."""
    path = _override(tmp_path, "spec_review", "---\nid: spec_review\nversion: 9.9\n---\nBody.\n")

    rubric = load_rubric("spec_review", project_dir=tmp_path)

    assert rubric.source == path
    assert rubric.checksum == hashlib.sha256(rubric.criteria.encode("utf-8")).hexdigest()


def test_editing_a_rubric_changes_its_checksum(tmp_path: Path) -> None:
    """The control for FR-4. A checksum that never moves records nothing."""
    _override(tmp_path, "spec_review", "---\nid: spec_review\nversion: 1\n---\nFirst.\n")
    first = load_rubric("spec_review", project_dir=tmp_path).checksum

    _override(tmp_path, "spec_review", "---\nid: spec_review\nversion: 1\n---\nSecond.\n")
    second = load_rubric("spec_review", project_dir=tmp_path).checksum

    assert first != second


def test_a_rubric_without_frontmatter_is_still_usable(tmp_path: Path) -> None:
    """Graceful degradation: the criteria are the point, the metadata is bookkeeping."""
    _override(tmp_path, "spec_review", "Just the criteria, no frontmatter.\n")

    rubric = load_rubric("spec_review", project_dir=tmp_path)

    assert "Just the criteria" in rubric.criteria
    assert rubric.version == "0"
