# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which framework a task is written for, and what the model is told about it.

Proves: D-INTL-08 FR-8

| Bucket | Case |
|---|---|
| Happy | each of the six shipped frameworks has its idioms and test style; the archetype names the framework; the profile's build-file framework brings its guide |
| Boundary | Spring Boot wins over Spring; an archetype that is no framework falls to the build file; a project-only framework is found through its archetype; nothing found is none |
| Degradation | a project file missing a section is refused, naming it |
| Hostile | an archetype for another language is ignored; a path-like archetype is never read as a file |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.workflows.implementation.frameworks import project_framework
from specweaver.workflows.implementation.languages import framework_guide

if TYPE_CHECKING:
    from pathlib import Path

_STYLE = {
    "spring": ("Spring", "SpringExtension"),
    "spring-boot": ("Spring Boot", "@WebMvcTest"),
    "quarkus": ("Quarkus", "@QuarkusTest"),
    "nestjs": ("NestJS", "Test.createTestingModule"),
    "actix-web": ("Actix-web", "actix_web::test"),
    "fastapi": ("FastAPI", "TestClient"),
}


@pytest.mark.parametrize(("key", "expected"), _STYLE.items())
def test_each_framework_names_its_test_style(key: str, expected: tuple[str, str]) -> None:
    guide = framework_guide(key)

    assert guide is not None
    assert guide.name == expected[0]
    assert expected[1] in guide.tests
    assert guide.code
    assert guide.languages


_OWN = """---
name: Micronaut
languages: java, kotlin
---
# Code
Use Micronaut beans.
# Tests
Use @MicronautTest.
"""


def _own(root: Path, name: str, text: str = _OWN) -> None:
    path = root / ".specweaver" / "frameworks" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_project_file_wins(tmp_path: Path) -> None:
    _own(tmp_path, "quarkus")

    guide = framework_guide("quarkus", tmp_path)

    assert guide is not None
    assert guide.tests == "Use @MicronautTest."


def test_an_unknown_framework_is_none(tmp_path: Path) -> None:
    assert framework_guide("micronaut", tmp_path) is None


def test_a_project_file_missing_a_section_is_refused(tmp_path: Path) -> None:
    _own(tmp_path, "micronaut", _OWN.replace("# Tests\nUse @MicronautTest.\n", ""))

    with pytest.raises(ValueError, match=r"micronaut\.md.*Tests"):
        framework_guide("micronaut", tmp_path)


@pytest.mark.parametrize("name", ["../languages/java", "Spring Boot", "", "a/b"])
def test_a_path_like_name_is_never_read(tmp_path: Path, name: str) -> None:
    assert framework_guide(name, tmp_path) is None


def _code(root: Path, archetype: str | None = None) -> Path:
    folder = root / "src" / "main" / "java" / "com" / "example"
    folder.mkdir(parents=True, exist_ok=True)
    if archetype:
        (root / "src" / "context.yaml").write_text(
            f"name: app\nlevel: module\narchetype: {archetype}\n", encoding="utf-8"
        )
    return folder / "Greeter.java"


def _name(choice: object) -> str | None:
    return None if choice is None else choice.guide.name  # type: ignore[attr-defined]


def test_the_archetype_names_the_framework(tmp_path: Path) -> None:
    choice = project_framework(tmp_path, _code(tmp_path, "quarkus"), "java", "spring-boot")

    assert _name(choice) == "Quarkus"
    assert choice.source == "archetype"  # type: ignore[union-attr]


def test_a_project_only_framework_comes_from_its_archetype(tmp_path: Path) -> None:
    _own(tmp_path, "micronaut")

    choice = project_framework(tmp_path, _code(tmp_path, "micronaut"), "java", "")

    assert _name(choice) == "Micronaut"


def test_an_archetype_that_is_no_framework_falls_to_the_build_file(tmp_path: Path) -> None:
    choice = project_framework(tmp_path, _code(tmp_path, "orchestrator"), "java", "spring-boot")

    assert _name(choice) == "Spring Boot"
    assert choice.source == "build file"  # type: ignore[union-attr]


def test_an_archetype_for_another_language_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "context.yaml").write_text("archetype: spring-boot\n", encoding="utf-8")

    assert project_framework(tmp_path, tmp_path / "src" / "greeter.py", "python", "") is None


@pytest.mark.parametrize(
    ("key", "language", "expected"),
    [
        ("quarkus", "kotlin", "Quarkus"),
        ("spring", "java", "Spring"),
        ("actix-web", "rust", "Actix-web"),
        ("fastapi", "python", "FastAPI"),
        ("nestjs", "typescript", "NestJS"),
    ],
)
def test_the_build_file_framework_brings_its_guide(
    tmp_path: Path, key: str, language: str, expected: str
) -> None:
    assert _name(project_framework(tmp_path, tmp_path / "src" / "x", language, key)) == expected


def test_no_archetype_and_no_build_file_framework_is_none(tmp_path: Path) -> None:
    assert project_framework(tmp_path, tmp_path / "src" / "X.java", "java", "") is None


def test_a_build_file_framework_without_a_guide_is_none(tmp_path: Path) -> None:
    assert project_framework(tmp_path, tmp_path / "src" / "X.java", "java", "micronaut") is None
