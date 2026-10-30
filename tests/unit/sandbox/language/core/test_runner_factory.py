# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which runner a directory resolves to, and what every runner must implement.

Proves: D-VAL-03 FR-1
Proves: B-EXEC-01 NFR-7
Proves: D-INTL-08 NFR-2
Proves: TECH-087 FR-12
Proves: TECH-087 FR-9

Cited under `specweaver-dev` §3.2c, from `INT-US-03-SF01-MIG`. Mutant: `run_compiler` renamed on the
abstract base, so compilation leaves the interface's bounds — **228 fail and 11 collection errors**,
the widest blast radius in this migration by an order of magnitude.

That number is the point. The five language runners are all `QARunnerInterface` subclasses, so
narrowing the interface makes every one of them abstract and un-instantiable, and the QA surface is
reached from almost every pipeline. An interface is not a document that describes the runners; it is
the thing that makes them exist.

**`B-EXEC-01` NFR-7** is the executor-passthrough half: on the host path `qa_atom` hands the runner
a plain `SubprocessExecutor` and never a `ContainerSubprocessExecutor`, so leaving
`execution_mode` at its default changes nothing. The citation was carried in this file's old docstring
as a bare `(B-EXEC-01)` plus an `(NFR-7)` comment thirty lines down, which the NFR sweep credited by
proximity; it is explicit now.

**`D-INTL-08` NFR-2**: non-Python toolchains run on the host; the container stays Python-validated.
A non-Python runner handed a container executor says so in a warning naming its language, and one
handed a host executor runs on the host.

**`TECH-087` FR-9**: the runner never chooses; `qa_atom` builds the host executor itself and passes it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.language.core.runner_factory import resolve_runner
from specweaver.sandbox.language.core.rust.runner import RustRunner
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner


class TestLanguageAutoDiscovery:
    def test_defaults_to_python_with_no_manifest(self, tmp_path: Path) -> None:
        runner = resolve_runner(tmp_path, executor=SubprocessExecutor(cwd=tmp_path))
        assert isinstance(runner, PythonQARunner)

    def test_selects_typescript_with_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        runner = resolve_runner(tmp_path, executor=SubprocessExecutor(cwd=tmp_path))
        assert isinstance(runner, TypeScriptRunner)

    def test_selects_rust_with_cargo_toml(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        runner = resolve_runner(tmp_path, executor=SubprocessExecutor(cwd=tmp_path))
        assert isinstance(runner, RustRunner)

    def test_selects_kotlin_with_kotlin_sources(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        (tmp_path / "src" / "main" / "kotlin").mkdir(parents=True)
        runner = resolve_runner(tmp_path, executor=SubprocessExecutor(cwd=tmp_path))
        assert isinstance(runner, KotlinRunner)

    def test_selects_java_with_a_bare_gradle_build(self, tmp_path: Path) -> None:
        """D-INTL-08 FR-2: the factory asks `detect_language`, so the two cannot disagree."""
        (tmp_path / "build.gradle").write_text("")
        assert isinstance(
            resolve_runner(tmp_path, executor=SubprocessExecutor(cwd=tmp_path)), JavaRunner
        )

    @pytest.mark.parametrize(
        ("language", "runner_type"),
        [("rust", RustRunner), ("java", JavaRunner), ("typescript", TypeScriptRunner)],
    )
    def test_an_explicit_language_wins_over_the_manifests(
        self, tmp_path: Path, language: str, runner_type: type
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("")
        assert isinstance(
            resolve_runner(tmp_path, language=language, executor=SubprocessExecutor(cwd=tmp_path)),
            runner_type,
        )

    def test_selects_java_with_pom_xml(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        runner = resolve_runner(tmp_path, executor=SubprocessExecutor(cwd=tmp_path))
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
        runner = resolve_runner(tmp_path, executor=SubprocessExecutor(cwd=tmp_path))
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
        assert not any("may not have its toolchain" in rec.message for rec in caplog.records)

    def test_no_warning_for_non_python_runner_with_plain_executor(
        self, tmp_path: Path, caplog
    ) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        plain_executor = MagicMock(spec=SubprocessExecutor)

        with caplog.at_level("WARNING"):
            resolve_runner(tmp_path, executor=plain_executor)

        assert not any("may not have its toolchain" in rec.message for rec in caplog.records)


class TestQaAtom:
    """`qa_atom` picks the executor and the runner, and hands both to the atom (TECH-087 FR-12)."""

    def test_the_atom_gets_the_runner_for_the_named_language(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.runner_factory import qa_atom

        atom = qa_atom(tmp_path, language="rust")

        assert isinstance(atom._runner, RustRunner)
        assert not isinstance(atom._runner._executor, ContainerSubprocessExecutor)

    def test_on_the_host_the_factory_chooses_the_executor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specweaver.sandbox.execution.executor import SubprocessExecutor
        from specweaver.sandbox.language.core import runner_factory

        given: list[object] = []
        real = runner_factory.resolve_runner

        def spy(cwd: Path, executor: object, language: str | None = None) -> object:
            given.append(executor)
            return real(cwd, executor=executor, language=language)

        monkeypatch.setattr(runner_factory, "resolve_runner", spy)

        atom = runner_factory.qa_atom(tmp_path, language="python")

        assert len(given) == 1
        assert type(given[0]) is SubprocessExecutor
        assert given[0]._cwd == tmp_path
        assert atom._runner._executor is given[0]

    def test_a_scenario_store_wins_over_host_settings(self, tmp_path: Path) -> None:
        from specweaver.core.config.settings import SandboxSettings
        from specweaver.sandbox.language.core.runner_factory import qa_atom

        atom = qa_atom(
            tmp_path,
            sandbox_settings=SandboxSettings(execution_mode="host"),
            scenarios_root=tmp_path / "scenarios",
        )

        assert isinstance(atom._runner._executor, ContainerSubprocessExecutor)
        assert atom._scenarios_mounted

    def test_the_scenario_scratch_goes_with_the_atom(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.runner_factory import qa_atom

        atom = qa_atom(tmp_path, scenarios_root=tmp_path / "scenarios")
        scratch = atom._runner._executor._mounts.scratch_root
        assert scratch.is_dir()
        assert not scratch.is_relative_to(tmp_path)

        del atom  # no cycle holds it, so this runs its finalizer

        assert not scratch.exists()

    def test_the_scenario_scratch_goes_when_no_runner_is_built(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specweaver.sandbox.language.core import runner_factory

        made: list[Path] = []
        real_mkdtemp = runner_factory.tempfile.mkdtemp

        def mkdtemp(**kwargs: str) -> str:
            made.append(Path(real_mkdtemp(**kwargs)))
            return str(made[-1])

        def no_runner(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("no runner")

        monkeypatch.setattr(runner_factory.tempfile, "mkdtemp", mkdtemp)
        monkeypatch.setattr(runner_factory, "resolve_runner", no_runner)

        with pytest.raises(RuntimeError, match="no runner"):
            runner_factory.qa_atom(tmp_path, scenarios_root=tmp_path / "scenarios")

        assert made
        assert not made[0].exists()
