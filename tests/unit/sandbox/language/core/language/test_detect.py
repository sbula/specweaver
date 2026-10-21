# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for language detection helpers.

Proves: D-INTL-08 FR-2
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.sandbox.language.core._detect import (
    detect_language,
    detect_scenario_extension,
)


class TestDetectLanguage:
    """Tests for detect_language()."""

    def test_detect_python_by_default(self, tmp_path: Path) -> None:
        """Empty directory defaults to Python."""
        assert detect_language(tmp_path) == "python"

    def test_detect_python_by_pyproject(self, tmp_path: Path) -> None:
        """pyproject.toml presence still defaults to Python."""
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]", encoding="utf-8")
        assert detect_language(tmp_path) == "python"

    def test_detect_java_by_pom_xml(self, tmp_path: Path) -> None:
        """pom.xml signals Java."""
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        assert detect_language(tmp_path) == "java"

    @pytest.mark.parametrize("build", ["build.gradle", "build.gradle.kts"])
    def test_a_gradle_build_without_kotlin_is_java(self, tmp_path: Path, build: str) -> None:
        """D-INTL-08 FR-2: a Gradle build file alone says nothing about the source language."""
        (tmp_path / build).write_text("plugins { id 'java' }", encoding="utf-8")
        assert detect_language(tmp_path) == "java"

    @pytest.mark.parametrize("build", ["build.gradle", "build.gradle.kts", "pom.xml"])
    def test_kotlin_sources_make_it_kotlin(self, tmp_path: Path, build: str) -> None:
        (tmp_path / build).write_text("plugins {}", encoding="utf-8")
        (tmp_path / "src" / "main" / "kotlin").mkdir(parents=True)
        assert detect_language(tmp_path) == "kotlin"

    @pytest.mark.parametrize(
        ("build", "text"),
        [
            ("build.gradle.kts", 'plugins { kotlin("jvm") version "2.0.0" }'),
            ("build.gradle", "plugins { id 'org.jetbrains.kotlin.jvm' }"),
            ("pom.xml", "<plugin><artifactId>kotlin-maven-plugin</artifactId></plugin>"),
        ],
    )
    def test_the_kotlin_plugin_makes_it_kotlin(self, tmp_path: Path, build: str, text: str) -> None:
        (tmp_path / build).write_text(text, encoding="utf-8")
        assert detect_language(tmp_path) == "kotlin"

    @pytest.mark.parametrize(
        ("fixture", "language"),
        [
            ("java_maven_project", "java"),
            ("java_gradle_project", "java"),
            ("kotlin_maven_project", "kotlin"),
            ("kotlin_gradle_project", "kotlin"),
            ("sample_project", "python"),
        ],
    )
    def test_the_fixture_projects_are_what_they_say(self, fixture: str, language: str) -> None:
        root = Path(__file__).resolve().parents[5] / "fixtures" / fixture
        assert root.is_dir()
        assert detect_language(root) == language

    def test_detect_typescript_by_package_json(self, tmp_path: Path) -> None:
        """`package.json` signals TypeScript."""
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        assert detect_language(tmp_path) == "typescript"

    def test_detect_rust_by_cargo_toml(self, tmp_path: Path) -> None:
        """`Cargo.toml` signals Rust."""
        (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")
        assert detect_language(tmp_path) == "rust"

    def test_typescript_wins_over_rust(self, tmp_path: Path) -> None:
        """package.json takes priority over Cargo.toml (detection order)."""
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")
        # package.json is checked first in factory order
        assert detect_language(tmp_path) == "typescript"

    def test_gradle_and_maven_without_kotlin_is_java(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        assert detect_language(tmp_path) == "java"


class TestDetectScenarioExtension:
    """Tests for detect_scenario_extension()."""

    def test_python_extension(self, tmp_path: Path) -> None:
        assert detect_scenario_extension(tmp_path) == "py"

    def test_java_extension(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        assert detect_scenario_extension(tmp_path) == "java"

    def test_kotlin_extension(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
        (tmp_path / "src" / "main" / "kotlin").mkdir(parents=True)
        assert detect_scenario_extension(tmp_path) == "kt"

    def test_typescript_extension(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        assert detect_scenario_extension(tmp_path) == "ts"

    def test_rust_extension(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")
        assert detect_scenario_extension(tmp_path) == "rs"

    def test_default_extension_is_py(self, tmp_path: Path) -> None:
        """Unknown / empty project defaults to py."""
        assert detect_scenario_extension(tmp_path) == "py"
