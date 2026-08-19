# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Loads semantic judgment criteria from markdown, shipped defaults under project overrides.

Rules stay code; rubrics are content. What counts as a good spec is a judgment that belongs to a
project and its domain, and changing it should not need a release. How a verdict is parsed is a
contract the engine depends on, and stays in Python where a project cannot break it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.commons.enums.dal import DALLevel

_SHIPPED_DIR = Path(__file__).parent

#: `---\nkey: value\n---` at the head of the file. Deliberately not YAML: a rubric is prose with a
#: label on it, and a parser dependency here would make the criteria harder to edit, not easier.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FIELD_RE = re.compile(r"^\s*([A-Za-z_]+)\s*:\s*(.+?)\s*$", re.MULTILINE)


class RubricNotFoundError(LookupError):
    """No file provides the requested rubric."""


@dataclass(frozen=True)
class Rubric:
    """Judgment criteria, and enough provenance to answer *which rubric judged this run*."""

    id: str
    version: str
    criteria: str
    checksum: str
    source: Path
    dal: DALLevel | None


def _candidates(rubric_id: str, project_dir: Path | None, dal: DALLevel | None) -> list[Path]:
    """Search order, most specific first: project variant, project, shipped variant, shipped."""
    roots = [(_SHIPPED_DIR, False)]
    if project_dir is not None:
        roots.insert(0, (project_dir / ".specweaver" / "rubrics", True))

    ordered: list[Path] = []
    for root, _ in roots:
        if dal is not None:
            ordered.append(root / f"{rubric_id}.{dal.value}.md")
    # A project's plain rubric outranks a shipped variant: an override that named no DAL still
    # means *use mine*, and silently preferring the shipped stricter file would ignore it.
    for root, _ in roots:
        ordered.append(root / f"{rubric_id}.md")
    return ordered


def _parse(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}, text
    fields = dict(_FIELD_RE.findall(match.group(1)))
    return fields, text[match.end() :]


def load_rubric(
    rubric_id: str,
    *,
    project_dir: Path | None = None,
    dal: DALLevel | None = None,
) -> Rubric:
    """Resolve `rubric_id` to the criteria that should judge this run.

    Raises `RubricNotFoundError` rather than returning empty criteria — a rubric that resolved to
    nothing would send the model no standard to judge against and still look like it worked.
    """
    ordered = _candidates(rubric_id, project_dir, dal)
    for path in ordered:
        if not path.is_file():
            continue
        fields, criteria = _parse(path.read_text(encoding="utf-8"))
        return Rubric(
            id=fields.get("id", rubric_id),
            version=fields.get("version", "0"),
            criteria=criteria,
            checksum=hashlib.sha256(criteria.encode("utf-8")).hexdigest(),
            source=path,
            dal=dal if dal is not None and path.name.endswith(f".{dal.value}.md") else None,
        )
    raise RubricNotFoundError(f"No rubric named {rubric_id!r} in: {', '.join(map(str, ordered))}")
