# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The review step judges by the project's rubric, and still parses.

Proves: C-VAL-05 FR-2, C-VAL-05 FR-3, C-VAL-05 FR-5

The loader is proven in `tests/unit/assurance/validation/test_rubrics.py`. This is the seam: the
handler is what turns a rubric file into the instructions the model actually receives, and it is
where the two halves are joined — criteria from content, output format from code.

FR-5 is the half that keeps the feature safe. If a project could edit the response format, an
override would break the parser and the failure would surface as an unrelated verdict bug.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.flow.handlers.review import resolve_review_instructions
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _context(tmp_path: Path, dal: DALLevel | None = None) -> RunContext:
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    if dal is not None:
        context.isolation = context.isolation.model_copy(update={"dal_level": dal})
    return context


def _write_rubric(tmp_path: Path, name: str, body: str) -> None:
    directory = tmp_path / ".specweaver" / "rubrics"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(body, encoding="utf-8")


def test_the_shipped_criteria_reach_the_model(tmp_path: Path) -> None:
    instructions = resolve_review_instructions(_context(tmp_path), "spec_review")

    assert "Single Responsibility" in instructions


def test_a_project_rubric_replaces_the_criteria(tmp_path: Path) -> None:
    """FR-2 at the seam. Editing a file is the whole delivery mechanism."""
    _write_rubric(tmp_path, "spec_review.md", "Only ever ask whether it rhymes.\n")

    instructions = resolve_review_instructions(_context(tmp_path), "spec_review")

    assert "Only ever ask whether it rhymes." in instructions
    assert "Single Responsibility" not in instructions


def test_the_output_contract_survives_a_project_rubric(tmp_path: Path) -> None:
    """FR-5. The parser's contract is code; no override can drop it."""
    _write_rubric(tmp_path, "spec_review.md", "Only ever ask whether it rhymes.\n")

    instructions = resolve_review_instructions(_context(tmp_path), "spec_review")

    assert "VERDICT: ACCEPTED" in instructions
    assert "[confidence: N]" in instructions


def test_the_output_contract_is_present_without_any_override(tmp_path: Path) -> None:
    """The control for FR-5: it must come from code, not from the shipped rubric's text."""
    instructions = resolve_review_instructions(_context(tmp_path), "spec_review")

    assert "VERDICT: ACCEPTED" in instructions


def test_a_dal_a_run_is_judged_by_the_strict_rubric(tmp_path: Path) -> None:
    """FR-3 at the seam. The run's own DAL picks the criteria, with no step parameter to forget."""
    instructions = resolve_review_instructions(_context(tmp_path, DALLevel.DAL_A), "spec_review")

    assert "catastrophic" in instructions


def test_an_ordinary_run_is_not_judged_by_the_strict_rubric(tmp_path: Path) -> None:
    """The control for FR-3. Applying DAL-A criteria everywhere would bury every review."""
    instructions = resolve_review_instructions(_context(tmp_path, DALLevel.DAL_D), "spec_review")

    assert "catastrophic" not in instructions
