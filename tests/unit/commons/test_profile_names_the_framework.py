# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The profile names the framework the root's build files declare, for the decided language.

Proves: TECH-079 FR-10

| Bucket | Case |
|---|---|
| Happy | Spring Boot, Spring, Quarkus, NestJS, Actix-web and FastAPI each named from their build file |
| Boundary | Quarkus before Spring Boot before Spring; FastAPI from any `requirements*.txt`; no marker is none; a pinned language takes only its own build files' framework |
| Degradation | an unreadable build file, a manifest that is not JSON or TOML, or not a table: none, no crash |
| Hostile | a framework named outside the dependencies (a description) is not a dependency |
"""

from __future__ import annotations

import pytest

from specweaver.commons.project_profile import ProjectProfile, decide_profile


def _framework(texts: dict[str, str], *extra: str, language: str | None = None) -> str:
    names = frozenset((*texts, *extra))
    return decide_profile(names, texts.get, kotlin_sources=False, language=language).framework


@pytest.mark.parametrize(
    ("texts", "framework"),
    [
        ({"pom.xml": "<groupId>org.springframework.boot</groupId>"}, "spring-boot"),
        ({"build.gradle": "id 'org.springframework.boot' version '3'"}, "spring-boot"),
        ({"build.gradle.kts": 'implementation("spring-boot-starter-web")'}, "spring-boot"),
        ({"pom.xml": "<groupId>org.springframework</groupId>"}, "spring"),
        ({"pom.xml": "<groupId>io.quarkus</groupId>"}, "quarkus"),
        (
            {"package.json": '{"dependencies": {"@nestjs/core": "10"}}', "tsconfig.json": "{}"},
            "nestjs",
        ),
        (
            {"package.json": '{"devDependencies": {"@nestjs/core": "10"}}', "tsconfig.json": "{}"},
            "nestjs",
        ),
        ({"Cargo.toml": '[dependencies]\nactix-web = "4"\n'}, "actix-web"),
        ({"pyproject.toml": 'dependencies = ["FastAPI>=0.100"]'}, "fastapi"),
        ({"requirements-dev.txt": "fastapi==0.110\n"}, "fastapi"),
    ],
)
def test_each_build_file_names_its_framework(texts: dict[str, str], framework: str) -> None:
    assert _framework(texts) == framework


def test_quarkus_wins_over_spring_and_spring_boot_over_spring() -> None:
    both = "<g>org.springframework.boot</g><g>org.springframework</g>"
    assert _framework({"pom.xml": both}) == "spring-boot"
    assert _framework({"pom.xml": f"<g>io.quarkus</g>{both}"}) == "quarkus"


def test_a_build_file_with_no_marker_names_none() -> None:
    assert _framework({"pyproject.toml": "[project]\nname = 'x'\n"}) == ""
    assert _framework({"Cargo.toml": '[dependencies]\nserde = "1"\n'}) == ""


def test_a_pinned_language_takes_only_its_own_framework() -> None:
    texts = {
        "pyproject.toml": "[project]\nname = 'x'\n",
        "package.json": '{"dependencies": {"@nestjs/core": "10"}}',
        "tsconfig.json": "{}",
    }
    assert _framework(texts, language="python") == ""
    assert _framework(texts, language="typescript") == "nestjs"


def test_the_profile_without_a_framework_is_none() -> None:
    assert ProjectProfile("python", "uv").framework == ""


@pytest.mark.parametrize(
    "texts",
    [
        {"package.json": "not json", "tsconfig.json": "{}"},
        {"package.json": '["@nestjs/core"]', "tsconfig.json": "{}"},
        {"package.json": '{"dependencies": "@nestjs/core"}', "tsconfig.json": "{}"},
        {"Cargo.toml": "[dependencies\nactix-web"},
        {"Cargo.toml": 'dependencies = "actix-web"'},
    ],
    ids=["not-json", "json-list", "deps-not-table", "broken-toml", "toml-deps-not-table"],
)
def test_a_broken_manifest_names_none(texts: dict[str, str]) -> None:
    assert _framework(texts) == ""


def test_an_unreadable_build_file_names_none() -> None:
    names = frozenset({"pom.xml"})
    assert decide_profile(names, lambda _name: None, kotlin_sources=False).framework == ""


def test_a_framework_outside_the_dependencies_is_not_one() -> None:
    texts = {"package.json": '{"description": "@nestjs/core clone"}', "tsconfig.json": "{}"}
    assert _framework(texts) == ""


def test_a_file_the_root_does_not_hold_is_never_read() -> None:
    asked: list[str] = []

    def read(name: str) -> str | None:
        asked.append(name)
        return None

    for language in ("typescript", "rust", "python", "java"):
        decide_profile(frozenset({"main.py"}), read, kotlin_sources=False, language=language)

    assert asked == []
