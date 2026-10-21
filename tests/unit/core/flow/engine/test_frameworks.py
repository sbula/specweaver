# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which framework a task is written for, and what the model is told about it.

Proves: D-INTL-08 FR-8

| Bucket | Case |
|---|---|
| Happy | each of the six shipped frameworks has its idioms and test style; the archetype names the framework; each build-file rule detects its framework |
| Boundary | Spring Boot wins over Spring; an archetype that is no framework falls to detection; a project-only framework is found through its archetype; nothing found is none |
| Degradation | an unreadable build file detects nothing; a project file missing a section is refused, naming it |
| Hostile | an archetype for another language is ignored; a path-like archetype is never read as a file |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.frameworks import project_framework
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
    (tmp_path / "pom.xml").write_text("<project>spring-boot</project>", encoding="utf-8")

    choice = project_framework(tmp_path, _code(tmp_path, "quarkus"), "java")

    assert _name(choice) == "Quarkus"
    assert choice.source == "archetype"  # type: ignore[union-attr]


def test_a_project_only_framework_comes_from_its_archetype(tmp_path: Path) -> None:
    _own(tmp_path, "micronaut")

    assert _name(project_framework(tmp_path, _code(tmp_path, "micronaut"), "java")) == "Micronaut"


def test_an_archetype_that_is_no_framework_falls_to_detection(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<parent>spring-boot-starter-parent</parent>", "utf-8")

    choice = project_framework(tmp_path, _code(tmp_path, "orchestrator"), "java")

    assert _name(choice) == "Spring Boot"
    assert choice.source == "build file"  # type: ignore[union-attr]


def test_an_archetype_for_another_language_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "context.yaml").write_text("archetype: spring-boot\n", encoding="utf-8")

    assert project_framework(tmp_path, tmp_path / "src" / "greeter.py", "python") is None


@pytest.mark.parametrize(
    ("manifest", "text", "language", "expected"),
    [
        ("pom.xml", "<groupId>io.quarkus</groupId>", "java", "Quarkus"),
        ("build.gradle.kts", 'plugins { id("io.quarkus") }', "kotlin", "Quarkus"),
        ("build.gradle", "id 'org.springframework.boot' version '3.3.0'", "java", "Spring Boot"),
        ("pom.xml", "<groupId>org.springframework</groupId>", "java", "Spring"),
        (
            "Cargo.toml",
            '[package]\nname = "g"\n[dependencies]\nactix-web = "4"\n',
            "rust",
            "Actix-web",
        ),
        ("pyproject.toml", '[project]\ndependencies = ["fastapi>=0.110"]\n', "python", "FastAPI"),
        ("requirements.txt", "fastapi==0.110\nuvicorn\n", "python", "FastAPI"),
    ],
)
def test_the_build_file_names_the_framework(
    tmp_path: Path, manifest: str, text: str, language: str, expected: str
) -> None:
    (tmp_path / manifest).write_text(text, encoding="utf-8")

    assert _name(project_framework(tmp_path, tmp_path / "src" / "x", language)) == expected


@pytest.mark.parametrize("key", ["dependencies", "devDependencies"])
def test_nest_is_detected_from_package_json(tmp_path: Path, key: str) -> None:
    (tmp_path / "package.json").write_text(json.dumps({key: {"@nestjs/core": "^10"}}), "utf-8")

    assert _name(project_framework(tmp_path, tmp_path / "src" / "x.ts", "typescript")) == "NestJS"


def test_spring_boot_wins_over_spring(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        "<groupId>org.springframework</groupId><artifactId>spring-boot-starter-web</artifactId>",
        encoding="utf-8",
    )

    assert _name(project_framework(tmp_path, tmp_path / "src" / "X.java", "java")) == "Spring Boot"


def test_a_build_file_of_another_language_detects_nothing(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("io.quarkus", encoding="utf-8")

    assert project_framework(tmp_path, tmp_path / "src" / "x.py", "python") is None


def test_nothing_found_is_none(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")

    assert project_framework(tmp_path, tmp_path / "src" / "X.java", "java") is None


@pytest.mark.parametrize("manifest", ["package.json", "Cargo.toml"])
def test_an_unreadable_build_file_detects_nothing(tmp_path: Path, manifest: str) -> None:
    (tmp_path / manifest).write_text("{not [valid", encoding="utf-8")
    language = "typescript" if manifest == "package.json" else "rust"

    assert project_framework(tmp_path, tmp_path / "src" / "x", language) is None
