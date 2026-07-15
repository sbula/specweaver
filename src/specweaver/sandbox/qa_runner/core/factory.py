# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""QARunner Factory.

Auto-discovers the target project language based on presence of manifest files
in a given directory without communicating with explicit Database layers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.execution.executor import SubprocessExecutor
    from specweaver.sandbox.qa_runner.core.interface import QARunnerInterface

logger = logging.getLogger(__name__)


def _warn_if_container_non_python(executor: SubprocessExecutor | None, language_name: str) -> None:
    """INT-US-09 SF-01 Finding #9: container sandboxing is only validated for Python
    projects — warn (don't silently no-op) when a container executor is threaded
    into a non-Python runner, whose toolchain may not exist in the sandbox image."""
    from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

    if isinstance(executor, ContainerSubprocessExecutor):
        logger.warning(
            "resolve_runner: container sandboxing is validated for Python projects only; "
            "%s may not have its toolchain available in the sandbox image",
            language_name,
        )


def resolve_runner(cwd: Path, executor: SubprocessExecutor | None = None) -> QARunnerInterface:
    """Auto-discover the native QA pipeline runner for the target repository.

    Args:
        cwd: Target directory to sniff for manifests.
        executor: Optional SubprocessExecutor (or subclass, e.g.
            ContainerSubprocessExecutor) DI seam, threaded through to whichever
            language runner is selected. Defaults to None (each runner builds
            its own default host SubprocessExecutor — NFR-7 backward compat).

    Returns:
        The matching QARunnerInterface adapter. Defaults to PythonQARunner.
    """
    if (cwd / "package.json").exists():
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        _warn_if_container_non_python(executor, "typescript")
        return TypeScriptRunner(cwd=cwd, executor=executor)

    if (cwd / "Cargo.toml").exists():
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        _warn_if_container_non_python(executor, "rust")
        return RustRunner(cwd=cwd, executor=executor)

    if (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        _warn_if_container_non_python(executor, "kotlin")
        return KotlinRunner(cwd=cwd, executor=executor)

    if (cwd / "pom.xml").exists():
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        _warn_if_container_non_python(executor, "java")
        return JavaRunner(cwd=cwd, executor=executor)

    # By default, or if pyproject.toml is found
    from specweaver.sandbox.language.core.python.runner import PythonQARunner

    return PythonQARunner(cwd=cwd, executor=executor)
