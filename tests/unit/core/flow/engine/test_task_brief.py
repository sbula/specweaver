# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the model must know to write a task's files so they build together.

Proves: D-INTL-08 FR-4

| Bucket | Case |
|---|---|
| Happy | Java/Kotlin: the paths, the package and the classes; Rust: the crate and module; TypeScript: the import path and the test tool |
| Boundary | the default package; a hyphenated crate name; Vitest, Jest or neither; Python gets no brief (NFR-1) |
| Degradation | no `Cargo.toml` `[package]`, or an unreadable `package.json`, still gives a brief that says so |
| Hostile | not applicable — every input is a derived path or a manifest value, never a path to open |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.task_files import TaskFiles, task_brief

if TYPE_CHECKING:
    from pathlib import Path


def _java(language: str = "java", package: str = "com/example/") -> TaskFiles:
    ext = "java" if language == "java" else "kt"
    return TaskFiles(
        f"src/main/{language}/{package}GreetService.{ext}",
        f"src/test/{language}/{package}GreetServiceTest.{ext}",
        language=language,
    )


@pytest.mark.parametrize("language", ["java", "kotlin"])
def test_the_jvm_brief_names_package_and_classes(tmp_path: Path, language: str) -> None:
    files = _java(language)

    brief = task_brief(files, tmp_path) or ""

    assert files.code in brief
    assert files.tests in brief
    assert "package `com.example`" in brief
    assert "class `GreetService`" in brief
    assert "class `GreetServiceTest`" in brief
    assert "`com.example.GreetService`" in brief


def test_the_default_package_is_said(tmp_path: Path) -> None:
    brief = task_brief(_java(package=""), tmp_path) or ""

    assert "default package" in brief
    assert "package `" not in brief


def _rust() -> TaskFiles:
    return TaskFiles(
        "src/greet_service.rs", "tests/greet_service.rs", ("src/lib.rs",), language="rust"
    )


def test_the_rust_brief_names_crate_and_module(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "greet-app"\n', encoding="utf-8")

    brief = task_brief(_rust(), tmp_path) or ""

    assert "`pub mod greet_service;`" in brief
    assert "`src/lib.rs`" in brief
    assert "`greet_app::greet_service`" in brief


def test_a_crate_without_a_name_is_said(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")

    brief = task_brief(_rust(), tmp_path) or ""

    assert "Cargo.toml names no package" in brief


def _ts() -> TaskFiles:
    return TaskFiles("src/greet_service.ts", "tests/greet_service.test.ts", language="typescript")


@pytest.mark.parametrize(
    ("manifest", "tool"),
    [
        ({"devDependencies": {"vitest": "^3"}}, "Vitest"),
        ({"devDependencies": {"jest": "^29"}}, "Jest"),
        ({"dependencies": {}}, "the project's `npm test` script"),
    ],
)
def test_the_typescript_brief_names_import_and_tool(
    tmp_path: Path, manifest: dict, tool: str
) -> None:
    (tmp_path / "package.json").write_text(json.dumps(manifest), encoding="utf-8")

    brief = task_brief(_ts(), tmp_path) or ""

    assert "`../src/greet_service`" in brief
    assert tool in brief


def test_an_unreadable_package_json_falls_back_to_the_script(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{not json", encoding="utf-8")

    assert "the project's `npm test` script" in (task_brief(_ts(), tmp_path) or "")


def test_python_gets_no_brief(tmp_path: Path) -> None:
    files = TaskFiles("src/greet_service.py", "tests/test_greet_service.py", language="python")

    assert task_brief(files, tmp_path) is None
