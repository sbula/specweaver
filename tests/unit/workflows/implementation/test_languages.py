# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the generator tells the model, per language, read from content files.

Proves: D-INTL-08 FR-4

| Bucket | Case |
|---|---|
| Happy | each of the five shipped languages has its name, instructions and role lines |
| Boundary | a project's own file wins over the shipped one; a project without one gets the shipped one |
| Degradation | a project file that lacks a section is refused, naming the file and the section |
| Hostile | a language outside the five, or a path-like one, is refused before any file is read |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.workflows.implementation.languages import language_guide

if TYPE_CHECKING:
    from pathlib import Path

_NAMES = {
    "python": "Python",
    "java": "Java",
    "kotlin": "Kotlin",
    "typescript": "TypeScript",
    "rust": "Rust",
}


@pytest.mark.parametrize(("language", "name"), _NAMES.items())
def test_each_language_speaks_its_own_name(language: str, name: str) -> None:
    guide = language_guide(language)

    assert guide.name == name
    for text in (guide.code, guide.tests, guide.code_role, guide.tests_role, guide.coder_role):
        assert name in text
        if language != "python":
            assert "Python" not in text
            assert "pytest" not in text


@pytest.mark.parametrize(
    ("language", "framework"), [("java", "JUnit 5"), ("kotlin", "kotlin.test")]
)
def test_the_jvm_tests_name_their_framework(language: str, framework: str) -> None:
    assert framework in language_guide(language).tests


_OWN = """---
name: Java
---
# Code
Write Java the house way.
# Tests
Test it the house way, in Java.
# Code role
You write Java for the house.
# Tests role
You test Java for the house.
# Coder role
You are the house Java developer.
"""


def test_a_project_file_wins(tmp_path: Path) -> None:
    own = tmp_path / ".specweaver" / "languages" / "java.md"
    own.parent.mkdir(parents=True)
    own.write_text(_OWN, encoding="utf-8")

    guide = language_guide("java", tmp_path)

    assert guide.code == "Write Java the house way."
    assert guide.coder_role == "You are the house Java developer."


def test_without_a_project_file_the_shipped_one_is_used(tmp_path: Path) -> None:
    assert language_guide("java", tmp_path) == language_guide("java")


def test_a_project_file_missing_a_section_is_refused(tmp_path: Path) -> None:
    own = tmp_path / ".specweaver" / "languages" / "java.md"
    own.parent.mkdir(parents=True)
    own.write_text(_OWN.replace("# Coder role\n", ""), encoding="utf-8")

    with pytest.raises(ValueError, match=r"java\.md.*Coder role"):
        language_guide("java", tmp_path)


def test_a_project_file_without_a_name_is_refused(tmp_path: Path) -> None:
    own = tmp_path / ".specweaver" / "languages" / "java.md"
    own.parent.mkdir(parents=True)
    own.write_text(_OWN.replace("---\nname: Java\n---\n", ""), encoding="utf-8")

    with pytest.raises(ValueError, match=r"java\.md.*name"):
        language_guide("java", tmp_path)


@pytest.mark.parametrize("language", ["cobol", "../java", "", "JAVA"])
def test_a_language_outside_the_five_is_refused(language: str) -> None:
    with pytest.raises(ValueError, match="language"):
        language_guide(language)
