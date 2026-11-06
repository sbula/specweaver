# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The reader lists a real project root once and hands the decision only what the root holds.

Proves: TECH-079 FR-1, TECH-079 FR-2, TECH-079 FR-3, TECH-079 FR-4
Proves: TECH-079 FR-10, TECH-079 NFR-4

Real files in `tmp_path`; the reader and the pure decision run unchanged.

| Bucket | Case |
|---|---|
| Happy | a Python root; the pins reach the decision |
| Boundary | `src/main/kotlin` makes Kotlin; a root reached through a link reads its own files; a folder named `pom.xml` is no build file; files in subfolders never count |
| Degradation | a build file that cannot be read, or is not UTF-8, still names its language; a missing root is an OS error, not a refusal |
| Hostile | a root `pom.xml` linked to a file outside the root is read as nothing; a mixed root is refused naming both files |
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from specweaver.commons.project_profile import ProjectProfile, ProjectUndecidedError
from specweaver.workspace.project.project_profile import read_project_profile

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")


def test_a_python_root_is_python_with_uv(tmp_path: Path) -> None:
    _write(tmp_path, {"pyproject.toml": "[project]\nname = 'x'\n", "main.py": ""})

    assert read_project_profile(tmp_path) == ProjectProfile("python", "uv")


def test_the_pins_reach_the_decision(tmp_path: Path) -> None:
    _write(tmp_path, {"pyproject.toml": "", "pom.xml": "<project/>", "build.gradle": ""})

    profile = read_project_profile(tmp_path, language="java", build_tool="gradle")

    assert profile == ProjectProfile("java", "gradle")


def test_kotlin_sources_make_kotlin(tmp_path: Path) -> None:
    _write(tmp_path, {"pom.xml": "<project/>", "src/main/kotlin/App.kt": ""})

    assert read_project_profile(tmp_path) == ProjectProfile("kotlin", "maven")


def test_the_kotlin_plugin_in_the_build_file_makes_kotlin(tmp_path: Path) -> None:
    _write(tmp_path, {"build.gradle.kts": 'plugins { kotlin("jvm") }'})

    assert read_project_profile(tmp_path) == ProjectProfile("kotlin", "gradle")


def test_a_folder_named_like_a_build_file_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path, {"pom.xml/readme.txt": "", "pyproject.toml": ""})

    assert read_project_profile(tmp_path) == ProjectProfile("python", "uv")


def test_build_files_in_subfolders_never_count(tmp_path: Path) -> None:
    _write(tmp_path, {"pyproject.toml": "", "web/package.json": "{}", "web/tsconfig.json": "{}"})

    assert read_project_profile(tmp_path) == ProjectProfile("python", "uv")


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs POSIX file modes")
def test_a_build_file_that_cannot_be_read_still_names_its_language(tmp_path: Path) -> None:
    _write(tmp_path, {"pom.xml": "<plugin>kotlin-maven-plugin</plugin>"})
    (tmp_path / "pom.xml").chmod(0)
    try:
        profile = read_project_profile(tmp_path)
    finally:
        (tmp_path / "pom.xml").chmod(0o644)

    assert profile == ProjectProfile("java", "maven")


def test_a_build_file_linked_outside_the_root_is_read_as_nothing(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "pom.xml"
    _write(tmp_path, {"elsewhere/pom.xml": "<plugin>kotlin-maven-plugin</plugin>"})
    root = tmp_path / "project"
    root.mkdir()
    (root / "pom.xml").symlink_to(outside)

    assert read_project_profile(root) == ProjectProfile("java", "maven")


def test_a_mixed_root_is_refused_naming_both_files(tmp_path: Path) -> None:
    _write(tmp_path, {"pyproject.toml": "", "package.json": "{}", "tsconfig.json": "{}"})

    with pytest.raises(ProjectUndecidedError) as caught:
        read_project_profile(tmp_path)

    assert "pyproject.toml" in str(caught.value)
    assert "package.json" in str(caught.value)


def test_a_build_file_that_is_not_utf8_still_names_its_language(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_bytes(b"<plugin>kotlin\xff\xfe</plugin>")

    assert read_project_profile(tmp_path) == ProjectProfile("java", "maven")


def test_a_root_reached_through_a_link_reads_its_own_files(tmp_path: Path) -> None:
    _write(tmp_path, {"real/build.gradle.kts": 'plugins { kotlin("jvm") }'})
    (tmp_path / "link").symlink_to(tmp_path / "real")

    assert read_project_profile(tmp_path / "link") == ProjectProfile("kotlin", "gradle")


def test_a_missing_root_is_an_os_error_not_a_refusal(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_project_profile(tmp_path / "missing")


def test_a_spring_boot_root_names_its_framework(tmp_path: Path) -> None:
    _write(
        tmp_path, {"build.gradle.kts": 'plugins { kotlin("jvm"); id("org.springframework.boot") }'}
    )

    assert read_project_profile(tmp_path) == ProjectProfile("kotlin", "gradle", "spring-boot")


def test_each_root_file_is_read_at_most_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proves: TECH-079 NFR-4"""
    from pathlib import Path as RealPath

    _write(
        tmp_path, {"build.gradle.kts": 'plugins { kotlin("jvm"); id("org.springframework.boot") }'}
    )
    reads: list[str] = []
    real_read = RealPath.read_text

    def counting(self: RealPath, *args: object, **kwargs: object) -> str:
        reads.append(self.name)
        return real_read(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(RealPath, "read_text", counting)

    read_project_profile(tmp_path)

    assert reads == ["build.gradle.kts"]
