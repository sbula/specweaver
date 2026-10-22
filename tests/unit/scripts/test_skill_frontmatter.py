# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every skill's frontmatter is in a shape Claude Code reads.

Claude Code loads a skill whose frontmatter it cannot parse "with no fields set": no description,
no `disable-model-invocation`, no `allowed-tools`. A quoted value that spans lines is such a shape.
PyYAML reads it, Claude Code did not: every `specweaver-*` skill was listed by its title alone, and
a skill marked manual-only stayed model-invocable. A folded block (`description: >-`) is read by
both, and keeps each line short for `_entry_depth.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = sorted((REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md"))

_QUOTED_START = re.compile(r"""^[A-Za-z-]+:\s*(["'])""")


def frontmatter_problems(text: str, skill: str) -> list[str]:
    """Why Claude Code would load this skill with no fields set, or with the wrong ones."""
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        return ["no frontmatter between --- markers"]
    block = parts[1]
    problems = []
    for line in block.strip("\n").splitlines():
        match = _QUOTED_START.match(line)
        if match and line.rstrip().count(match.group(1)) < 2:
            problems.append(f"quoted value spans lines: {line.strip()[:40]}")
    try:
        fields = yaml.safe_load(block) or {}
    except yaml.YAMLError as exc:  # expected: a broken block is the finding, not a crash
        return [*problems, f"YAML does not parse: {exc}"]
    if fields.get("name") != skill:
        problems.append(f"name {fields.get('name')!r} is not the folder name {skill!r}")
    if not str(fields.get("description", "")).strip():
        problems.append("no description")
    return problems


class TestFrontmatterProblems:
    def test_a_folded_description_is_accepted(self) -> None:
        text = "---\nname: demo\ndescription: >-\n  Does a thing.\n  Use for x.\n---\n# Demo\n"
        assert frontmatter_problems(text, "demo") == []

    def test_a_quoted_description_over_two_lines_is_refused(self) -> None:
        text = '---\nname: demo\ndescription: "Does a thing.\n  Use for x."\n---\n# Demo\n'
        assert any("spans lines" in p for p in frontmatter_problems(text, "demo"))

    def test_a_single_line_quoted_value_is_accepted(self) -> None:
        text = '---\nname: demo\ndescription: "Does a thing."\nargument-hint: "[x]"\n---\n'
        assert frontmatter_problems(text, "demo") == []

    def test_a_missing_description_is_refused(self) -> None:
        assert frontmatter_problems("---\nname: demo\n---\n# Demo\n", "demo") == ["no description"]

    def test_a_name_that_is_not_the_folder_is_refused(self) -> None:
        text = "---\nname: other\ndescription: x\n---\n"
        assert frontmatter_problems(text, "demo") == ["name 'other' is not the folder name 'demo'"]

    def test_no_frontmatter_is_refused(self) -> None:
        assert frontmatter_problems("# Demo\n", "demo") == ["no frontmatter between --- markers"]

    def test_unparseable_yaml_is_reported_not_raised(self) -> None:
        problems = frontmatter_problems("---\nname: [demo\n---\n", "demo")
        assert any("does not parse" in p for p in problems)


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_every_skill_frontmatter_is_readable(path: Path) -> None:
    assert frontmatter_problems(path.read_text(encoding="utf-8"), path.parent.name) == []


def test_the_skills_are_found() -> None:
    """An empty glob would pass the parametrized test vacuously."""
    assert len(SKILLS) >= 9
