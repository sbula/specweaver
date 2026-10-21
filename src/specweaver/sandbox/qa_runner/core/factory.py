# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""QARunner Factory.

Auto-discovers the target project language based on presence of manifest files
in a given directory without communicating with explicit Database layers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.execution.executor import SubprocessExecutor
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
    cwd: Path, executor: SubprocessExecutor | None = None, language: str | None = None
) -> QARunnerInterface:
    """The QA runner for the project's language: `language` when given, else detected.

    Args:
        cwd: The project root.
        executor: Optional SubprocessExecutor (or a container one) threaded through to the runner;
            None lets each runner build its own host executor.
        language: The run's language; None asks `detect_language`, the one detector.
    """
    from specweaver.sandbox.language.core._detect import detect_language

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
