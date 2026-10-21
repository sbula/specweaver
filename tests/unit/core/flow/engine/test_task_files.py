# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A task's code and test files, worked out once, per language.

Proves: D-INTL-08 FR-3

| Bucket | Case |
|---|---|
| Happy | the layout for each of the five languages |
| Boundary | the Java package from the spec header, from the sources' shared prefix, from the build's group, none; sources sharing nothing; `greet-service` as `GreetService`; Rust with `lib.rs`, `main.rs`, neither — always `lib.rs`, the only crate root tests reach |
| Degradation | an unreadable build file falls through to the default package |
| Hostile | a header package that is not a dotted identifier (`../x`, `com/evil`) is refused, naming the line |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.task_files import TaskFiles, task_files_for

if TYPE_CHECKING:
    from pathlib import Path


def _spec(root: Path, name: str = "greet_service_spec.md", header: str = "") -> Path:
    spec = root / "specs" / name
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        f"# Greeter\n\n> **Status**: DRAFT\n{header}\n---\n\n## 1. Purpose\n", encoding="utf-8"
    )
    return spec


def _source(root: Path, lang: str, rel: str, package: str) -> None:
    path = root / "src" / "main" / lang / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    end = ";" if lang == "java" else ""
    path.write_text(f"package {package}{end}\n\nclass X\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("python", TaskFiles("src/greet_service.py", "tests/test_greet_service.py")),
        ("typescript", TaskFiles("src/greet_service.ts", "tests/greet_service.test.ts")),
        ("rust", TaskFiles("src/greet_service.rs", "tests/greet_service.rs", ("src/lib.rs",))),
        (
            "java",
            TaskFiles("src/main/java/GreetService.java", "src/test/java/GreetServiceTest.java"),
        ),
        (
            "kotlin",
            TaskFiles("src/main/kotlin/GreetService.kt", "src/test/kotlin/GreetServiceTest.kt"),
        ),
    ],
)
def test_the_layout_per_language(tmp_path: Path, language: str, expected: TaskFiles) -> None:
    assert task_files_for(tmp_path, _spec(tmp_path), language) == expected


def test_the_spec_header_names_the_package(tmp_path: Path) -> None:
    _source(tmp_path, "java", "org/other/A.java", "org.other")
    spec = _spec(tmp_path, header="> **Package**: com.example.greet\n")

    files = task_files_for(tmp_path, spec, "java")

    assert files.code == "src/main/java/com/example/greet/GreetService.java"
    assert files.tests == "src/test/java/com/example/greet/GreetServiceTest.java"


def test_the_sources_shared_prefix_is_the_package(tmp_path: Path) -> None:
    _source(tmp_path, "kotlin", "com/example/a/A.kt", "com.example.a")
    _source(tmp_path, "kotlin", "com/example/b/B.kt", "com.example.b")

    assert task_files_for(tmp_path, _spec(tmp_path), "kotlin").code == (
        "src/main/kotlin/com/example/GreetService.kt"
    )


def test_sources_sharing_nothing_fall_back_to_the_group(tmp_path: Path) -> None:
    _source(tmp_path, "java", "com/a/A.java", "com.a")
    _source(tmp_path, "java", "org/b/B.java", "org.b")
    (tmp_path / "pom.xml").write_text(
        "<project><groupId>io.acme</groupId><dependencies><dependency><groupId>x.y</groupId>"
        "</dependency></dependencies></project>",
        encoding="utf-8",
    )

    assert task_files_for(tmp_path, _spec(tmp_path), "java").code == (
        "src/main/java/io/acme/GreetService.java"
    )


def test_the_gradle_group_is_the_package(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text('group = "io.acme"\n', encoding="utf-8")

    assert task_files_for(tmp_path, _spec(tmp_path), "kotlin").code == (
        "src/main/kotlin/io/acme/GreetService.kt"
    )


def test_an_unreadable_build_means_the_default_package(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project><groupId>", encoding="utf-8")

    assert (
        task_files_for(tmp_path, _spec(tmp_path), "java").code == "src/main/java/GreetService.java"
    )


@pytest.mark.parametrize("package", ["../x", "com/evil", "com..x", "Com.Example"])
def test_a_header_package_that_is_not_an_identifier_is_refused(
    tmp_path: Path, package: str
) -> None:
    spec = _spec(tmp_path, header=f"> **Package**: {package}\n")

    with pytest.raises(ValueError, match=r"greet_service_spec\.md:4") as caught:
        task_files_for(tmp_path, spec, "java")

    assert package in str(caught.value)


def test_a_dashed_stem_is_pascal_case_and_a_rust_module(tmp_path: Path) -> None:
    spec = _spec(tmp_path, name="greet-service_spec.md")

    assert task_files_for(tmp_path, spec, "java").code == "src/main/java/GreetService.java"
    assert task_files_for(tmp_path, spec, "rust").code == "src/greet_service.rs"


@pytest.mark.parametrize(
    ("present", "extra"),
    [(["src/lib.rs"], "src/lib.rs"), (["src/main.rs"], "src/lib.rs"), ([], "src/lib.rs")],
)
def test_rust_names_the_file_that_declares_the_module(
    tmp_path: Path, present: list[str], extra: str
) -> None:
    for rel in present:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("", encoding="utf-8")

    assert task_files_for(tmp_path, _spec(tmp_path), "rust").extra == (extra,)


@pytest.mark.parametrize("language", ["python", "java", "kotlin", "typescript", "rust"])
def test_the_files_name_their_language(tmp_path: Path, language: str) -> None:
    assert task_files_for(tmp_path, _spec(tmp_path), language).language == language


def test_the_detected_language_is_named(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "greet"\n', encoding="utf-8")

    assert task_files_for(tmp_path, _spec(tmp_path), None).language == "rust"
