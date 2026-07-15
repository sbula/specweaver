# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for qa_runner factory — auto-discovery + executor DI passthrough (INT-US-09 SF-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.language.core.rust.runner import RustRunner
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner
from specweaver.sandbox.qa_runner.core.factory import resolve_runner

if TYPE_CHECKING:
    from pathlib import Path


class TestLanguageAutoDiscovery:
    def test_defaults_to_python_with_no_manifest(self, tmp_path: Path) -> None:
        runner = resolve_runner(tmp_path)
        assert isinstance(runner, PythonQARunner)

    def test_selects_typescript_with_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        runner = resolve_runner(tmp_path)
        assert isinstance(runner, TypeScriptRunner)

    def test_selects_rust_with_cargo_toml(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        runner = resolve_runner(tmp_path)
        assert isinstance(runner, RustRunner)

    def test_selects_kotlin_with_build_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        runner = resolve_runner(tmp_path)
        assert isinstance(runner, KotlinRunner)

    def test_selects_java_with_pom_xml(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        runner = resolve_runner(tmp_path)
        assert isinstance(runner, JavaRunner)


class TestExecutorPassthrough:
    def test_executor_threaded_to_python_runner(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = resolve_runner(tmp_path, executor=mock_executor)
        assert isinstance(runner, PythonQARunner)
        assert runner._executor is mock_executor

    def test_executor_threaded_to_non_python_runner(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = resolve_runner(tmp_path, executor=mock_executor)
        assert isinstance(runner, TypeScriptRunner)
        assert runner._executor is mock_executor

    def test_no_executor_defaults_to_none_passthrough(self, tmp_path: Path) -> None:
        # No explicit executor → runner builds its own default SubprocessExecutor,
        # matching pre-SF-01 behavior exactly (NFR-7).
        runner = resolve_runner(tmp_path)
        assert isinstance(runner._executor, SubprocessExecutor)
        assert not isinstance(runner._executor, ContainerSubprocessExecutor)


class TestNonPythonContainerWarning:
    def test_warns_on_non_python_runner_with_container_executor(
        self, tmp_path: Path, caplog
    ) -> None:
        (tmp_path / "package.json").write_text("{}")
        container_executor = MagicMock(spec=ContainerSubprocessExecutor)

        with caplog.at_level("WARNING"):
            runner = resolve_runner(tmp_path, executor=container_executor)

        assert isinstance(runner, TypeScriptRunner)
        assert runner._executor is container_executor
        assert any("typescript" in rec.message.lower() for rec in caplog.records)

    def test_no_warning_for_python_runner_with_container_executor(
        self, tmp_path: Path, caplog
    ) -> None:
        container_executor = MagicMock(spec=ContainerSubprocessExecutor)

        with caplog.at_level("WARNING"):
            runner = resolve_runner(tmp_path, executor=container_executor)

        assert isinstance(runner, PythonQARunner)
        assert not any(
            "may not have its toolchain" in rec.message for rec in caplog.records
        )

    def test_no_warning_for_non_python_runner_with_plain_executor(
        self, tmp_path: Path, caplog
    ) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        plain_executor = MagicMock(spec=SubprocessExecutor)

        with caplog.at_level("WARNING"):
            resolve_runner(tmp_path, executor=plain_executor)

        assert not any(
            "may not have its toolchain" in rec.message for rec in caplog.records
        )
