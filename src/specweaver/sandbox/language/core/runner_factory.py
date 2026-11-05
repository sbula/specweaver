# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which QA runner a project gets, and the QA atom built around it.

The runners live beside this factory, so the choice is made here; the QA atom in `sandbox/qa_runner`
takes the runner it is given and never imports a language.
"""

from __future__ import annotations

import functools
import logging
import shutil
import tempfile
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

if TYPE_CHECKING:
    from specweaver.core.config.settings import SandboxSettings
    from specweaver.sandbox.qa_runner.core.interface import QARunnerInterface

logger = logging.getLogger(__name__)


def _warn_if_container_non_python(executor: SubprocessExecutor | None, language_name: str) -> None:
    """Container sandboxing is only validated for Python
    projects — warn (don't silently no-op) when a container executor is threaded
    into a non-Python runner, whose toolchain may not exist in the sandbox image."""
    from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

    if isinstance(executor, ContainerSubprocessExecutor):
        logger.warning(
            "resolve_runner: container sandboxing is validated for Python projects only; "
            "%s may not have its toolchain available in the sandbox image",
            language_name,
        )


def resolve_runner(
    cwd: Path, executor: SubprocessExecutor, language: str | None = None
) -> QARunnerInterface:
    """The QA runner for the project's language: `language` when given, else detected.

    Args:
        cwd: The project root.
        executor: Where the runner's tools run: a host `SubprocessExecutor` or a container one.
        language: The run's language; None asks `detect_language`, the one detector.
    """
    from specweaver.sandbox.language.core.detect import detect_language

    chosen = language or detect_language(cwd)
    if chosen != "python":
        _warn_if_container_non_python(executor, chosen)
    runner: QARunnerInterface = _runner_class(chosen)(cwd=cwd, executor=executor)
    return runner


def _runner_class(language: str) -> Any:
    if language == "typescript":
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        return TypeScriptRunner
    if language == "rust":
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        return RustRunner
    if language == "kotlin":
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        return KotlinRunner
    if language == "java":
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        return JavaRunner
    from specweaver.sandbox.language.core.python.runner import PythonQARunner

    return PythonQARunner


def qa_atom(
    cwd: Path,
    language: str | None = None,
    sandbox_settings: SandboxSettings | None = None,
    scenarios_root: Path | None = None,
) -> QARunnerAtom:
    """The QA atom for `cwd`, with the runner for its language and the executor the run asks for.

    Args:
        cwd: The project root.
        language: The run's language; None detects it from the project's manifests.
        sandbox_settings: `execution_mode="container"` routes execution through a container;
            None or `"host"` runs on the host.
        scenarios_root: A scenario store to mount read-only; implies a container.
    """
    executor: SubprocessExecutor
    scratch: Path | None = None
    if scenarios_root is not None:
        scratch = Path(tempfile.mkdtemp(prefix="specweaver-scenario-"))
        executor = _build_container_executor(cwd, scenarios_root, scratch)
    elif sandbox_settings is not None and sandbox_settings.execution_mode == "container":
        executor = _build_container_executor(cwd)
    else:
        executor = SubprocessExecutor(cwd=cwd)

    try:
        runner = resolve_runner(cwd, executor=executor, language=language)
    except BaseException:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)
        raise
    from specweaver.sandbox.language.core.boundary_check import check_architecture

    atom = QARunnerAtom(
        cwd,
        runner,
        architecture=functools.partial(check_architecture, executor=executor),
        scenarios_mounted=scenarios_root is not None,
    )
    if scratch is not None:
        weakref.finalize(atom, shutil.rmtree, scratch, True)
    return atom


def _build_container_executor(
    cwd: Path, scenarios_root: Path | None = None, scratch_root: Path | None = None
) -> SubprocessExecutor:
    """Derive the RO-source / RW-scratch-cache mount layout under `.specweaver/.sandbox/`
    and build a ContainerSubprocessExecutor from it.

    A scenario run also mounts its store read-only, and writes its scratch outside the project:
    a pytest cache in the project would carry scenario test names to the coder's next run.
    """
    from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
    from specweaver.sandbox.execution.models import ContainerMounts

    sandbox_dir = cwd / ".specweaver" / ".sandbox"
    mounts = ContainerMounts(
        source_root=cwd,
        scratch_root=scratch_root or sandbox_dir / "scratch",
        cache_root=sandbox_dir / "cache",
        scenarios_root=scenarios_root,
    )
    return ContainerSubprocessExecutor(cwd=cwd, mounts=mounts)
