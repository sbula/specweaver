# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for language detection helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.language.core._detect import (
    detect_language,
    detect_scenario_extension,
)

if TYPE_CHECKING:
    from pathlib import Path


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

    def test_detect_kotlin_by_build_gradle(self, tmp_path: Path) -> None:
        """`build.gradle` (Groovy DSL) signals Kotlin."""
        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
        assert detect_language(tmp_path) == "kotlin"

    def test_detect_kotlin_by_build_gradle_kts(self, tmp_path: Path) -> None:
        """`build.gradle.kts` (Kotlin DSL) also signals Kotlin."""
        (tmp_path / "build.gradle.kts").write_text("plugins {}", encoding="utf-8")
        assert detect_language(tmp_path) == "kotlin"

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

    def test_kotlin_wins_over_java(self, tmp_path: Path) -> None:
        """build.gradle takes priority over pom.xml (detection order)."""
        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        # build.gradle is checked before pom.xml
        assert detect_language(tmp_path) == "kotlin"


class TestDetectScenarioExtension:
    """Tests for detect_scenario_extension()."""

    def test_python_extension(self, tmp_path: Path) -> None:
        assert detect_scenario_extension(tmp_path) == "py"

    def test_java_extension(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        assert detect_scenario_extension(tmp_path) == "java"

    def test_kotlin_extension(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
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
