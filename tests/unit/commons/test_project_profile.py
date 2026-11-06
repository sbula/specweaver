# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One pure decision names a project's language and build tool, or refuses to guess.

Proves: TECH-079 FR-1, TECH-079 FR-2, TECH-079 FR-3, TECH-079 FR-4, TECH-079 FR-5, TECH-079 FR-6

The decision gets the root's file names and a reader; it reads nothing itself.

| Bucket | Case |
|---|---|
| Happy | each build file names its language and build tool; a set pin wins over detection |
| Boundary | no build file: the root's code endings decide; package.json is TypeScript only with tsconfig.json or a root `.ts`/`.tsx` file; Kotlin by sources or by the build text |
| Degradation | an unreadable JVM build file reads as None: still Java, no crash |
| Hostile | a mixed root, a language SpecWeaver cannot generate, pom.xml with build.gradle, an empty root, pins that contradict each other or the root: each refused, naming what was found and the setting |
"""

from __future__ import annotations

import pytest

from specweaver.commons.project_profile import (
    ProjectProfile,
    ProjectUndecidedError,
    decide_profile,
)


def _decide(*names: str, texts: dict[str, str] | None = None, kotlin_sources: bool = False):
    texts = texts or {}
    return decide_profile(frozenset(names), texts.get, kotlin_sources=kotlin_sources)


def _refusal(*names: str, texts: dict[str, str] | None = None) -> str:
    with pytest.raises(ProjectUndecidedError) as caught:
        _decide(*names, texts=texts)
    return str(caught.value)


@pytest.mark.parametrize(
    ("names", "language", "build_tool"),
    [
        (("pyproject.toml",), "python", "uv"),
        (("uv.lock",), "python", "uv"),
        (("pyproject.toml", "uv.lock", "README.md"), "python", "uv"),
        (("requirements.txt",), "python", ""),
        (("requirements-dev.txt",), "python", ""),
        (("Cargo.toml", "Cargo.lock"), "rust", "cargo"),
        (("package.json", "tsconfig.json"), "typescript", "npm"),
        (("pom.xml",), "java", "maven"),
        (("build.gradle",), "java", "gradle"),
        (("build.gradle.kts",), "java", "gradle"),
    ],
)
def test_each_build_file_names_its_language_and_build_tool(
    names: tuple[str, ...], language: str, build_tool: str
) -> None:
    assert _decide(*names) == ProjectProfile(language=language, build_tool=build_tool)


@pytest.mark.parametrize(
    ("names", "language"),
    [
        (("main.py",), "python"),
        (("MAIN.PY", "README.md"), "python"),
        (("lib.rs",), "rust"),
        (("App.kt",), "kotlin"),
        (("Main.java", "Helper.java"), "java"),
        (("index.ts",), "typescript"),
    ],
)
def test_without_a_build_file_the_root_code_endings_decide(
    names: tuple[str, ...], language: str
) -> None:
    assert _decide(*names) == ProjectProfile(language=language, build_tool="")


def test_package_json_with_a_root_typescript_file_is_typescript() -> None:
    assert _decide("package.json", "index.ts").language == "typescript"
    assert _decide("package.json", "App.tsx").language == "typescript"


def test_package_json_alone_is_javascript_and_refused() -> None:
    message = _refusal("package.json", "index.js")

    assert "javascript (package.json) cannot be generated" in message
    assert "python, java, kotlin, typescript and rust" in message


def test_a_jvm_build_is_kotlin_with_kotlin_sources() -> None:
    assert _decide("pom.xml", kotlin_sources=True) == ProjectProfile("kotlin", "maven")


@pytest.mark.parametrize("build", ["pom.xml", "build.gradle", "build.gradle.kts"])
def test_a_jvm_build_naming_kotlin_is_kotlin(build: str) -> None:
    texts = {build: 'plugins { id("org.jetbrains.Kotlin.jvm") }'}

    assert _decide(build, texts=texts).language == "kotlin"


def test_a_jvm_build_without_kotlin_is_java() -> None:
    assert _decide("pom.xml", texts={"pom.xml": "<project/>"}).language == "java"


def test_an_unreadable_jvm_build_file_is_still_java() -> None:
    assert _decide("pom.xml", texts={}) == ProjectProfile("java", "maven")


@pytest.mark.parametrize(
    ("names", "found"),
    [
        (("pyproject.toml", "package.json", "tsconfig.json"), ("pyproject.toml", "package.json")),
        (("Cargo.toml", "pom.xml"), ("Cargo.toml", "pom.xml")),
        (("pyproject.toml", "package.json"), ("pyproject.toml", "package.json")),
        (("main.py", "index.ts"), ("main.py", "index.ts")),
    ],
)
def test_a_mixed_root_is_refused_naming_the_files_and_the_setting(
    names: tuple[str, ...], found: tuple[str, ...]
) -> None:
    message = _refusal(*names)

    for name in found:
        assert name in message
    assert "set [implement] language in specweaver.toml" in message


@pytest.mark.parametrize(
    ("names", "language"),
    [
        (("go.mod",), "go"),
        (("main.go",), "go"),
        (("CMakeLists.txt",), "c"),
        (("main.c",), "c"),
        (("main.cpp",), "cpp"),
        (("index.mjs",), "javascript"),
    ],
)
def test_a_language_that_cannot_be_generated_is_refused(
    names: tuple[str, ...], language: str
) -> None:
    message = _refusal(*names)

    assert message.startswith(f"{language} (")
    assert "cannot be generated" in message


@pytest.mark.parametrize("gradle", ["build.gradle", "build.gradle.kts"])
def test_pom_and_gradle_together_are_refused_naming_build_tool(gradle: str) -> None:
    message = _refusal("pom.xml", gradle)

    assert "pom.xml" in message
    assert gradle in message
    assert "set [implement] build_tool in specweaver.toml (maven or gradle)" in message


@pytest.mark.parametrize("names", [(), ("README.md", ".gitignore", "Makefile")])
def test_a_root_with_no_build_file_and_no_code_file_is_refused(names: tuple[str, ...]) -> None:
    assert "no build file and no code file" in _refusal(*names)


def test_only_the_jvm_build_files_are_read() -> None:
    asked: list[str] = []

    def read(name: str) -> str | None:
        asked.append(name)
        return None

    decide_profile(frozenset({"pyproject.toml", "main.py"}), read, kotlin_sources=False)
    decide_profile(frozenset({"pom.xml", "README.md"}), read, kotlin_sources=False)

    assert asked == ["pom.xml"]


def test_cmake_with_a_root_cpp_file_is_cpp_and_refused() -> None:
    assert _refusal("CMakeLists.txt", "main.cpp").startswith("cpp (CMakeLists.txt) cannot")


def test_a_mixed_root_names_a_jvm_build_as_java_or_kotlin() -> None:
    message = _refusal("Cargo.toml", "pom.xml", "pyproject.toml")

    assert (
        "build files for java or kotlin (pom.xml), python (pyproject.toml) and rust (Cargo.toml);"
        in message
    )


def test_a_long_file_list_is_cut_after_three_names() -> None:
    message = _refusal("a.py", "b.py", "c.py", "d.py", "e.ts")

    assert "python (a.py, b.py, c.py, ...) and typescript (e.ts)" in message


def test_build_file_names_match_case_exactly_on_every_platform() -> None:
    assert "no build file and no code file" in _refusal("REQUIREMENTS.TXT", "PyProject.toml")


def _pinned(*names: str, language: str | None = None, build_tool: str | None = None):
    return decide_profile(
        frozenset(names), {}.get, kotlin_sources=False, language=language, build_tool=build_tool
    )


@pytest.mark.parametrize(
    ("names", "language", "expected"),
    [
        (("pyproject.toml", "package.json", "tsconfig.json"), "typescript", ("typescript", "npm")),
        (("pyproject.toml", "pom.xml"), "python", ("python", "uv")),
        (("pom.xml",), "kotlin", ("kotlin", "maven")),
        (("pyproject.toml",), "rust", ("rust", "")),
        ((), "python", ("python", "")),
        (("go.mod", "main.go"), "java", ("java", "")),
    ],
)
def test_a_language_pin_wins_over_the_root(
    names: tuple[str, ...], language: str, expected: tuple[str, str]
) -> None:
    assert _pinned(*names, language=language) == ProjectProfile(*expected)


@pytest.mark.parametrize("tool", ["maven", "gradle"])
def test_a_build_tool_pin_wins_over_pom_and_gradle(tool: str) -> None:
    assert _pinned("pom.xml", "build.gradle", build_tool=tool) == ProjectProfile("java", tool)


def test_both_pins_that_agree_decide_alone() -> None:
    profile = _pinned(
        "pyproject.toml", "pom.xml", "build.gradle", language="kotlin", build_tool="gradle"
    )

    assert profile == ProjectProfile("kotlin", "gradle")


@pytest.mark.parametrize(
    ("language", "tool"),
    [("python", "maven"), ("rust", "npm"), ("typescript", "uv"), ("java", "cargo")],
)
def test_pins_that_contradict_are_refused_naming_both(language: str, tool: str) -> None:
    with pytest.raises(ProjectUndecidedError) as caught:
        _pinned("pyproject.toml", language=language, build_tool=tool)

    assert f'[implement] language = "{language}" and build_tool = "{tool}" do not agree' in str(
        caught.value
    )


def test_a_build_tool_pin_that_does_not_build_the_root_language_is_refused() -> None:
    with pytest.raises(ProjectUndecidedError) as caught:
        _pinned("pyproject.toml", build_tool="maven")

    assert '[implement] build_tool = "maven" does not build python' in str(caught.value)


def test_a_build_tool_pin_does_not_pick_the_language_of_a_mixed_root() -> None:
    with pytest.raises(ProjectUndecidedError, match=r"set \[implement\] language"):
        _pinned("pyproject.toml", "pom.xml", build_tool="maven")


@pytest.mark.parametrize("language", ["go", "javascript", "PYTHON", ""])
def test_a_language_pin_outside_the_generated_ones_is_refused(language: str) -> None:
    with pytest.raises(ProjectUndecidedError, match="cannot be generated"):
        _pinned("pyproject.toml", language=language)
