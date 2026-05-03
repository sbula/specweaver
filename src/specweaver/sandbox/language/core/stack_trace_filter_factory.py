# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Factory that creates the correct ``StackTraceFilterInterface`` for a project."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.language.core._detect import detect_language

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.workspace.ast.parsers.interfaces import StackTraceFilterInterface


def create_stack_trace_filter(cwd: Path) -> StackTraceFilterInterface:
    """Create the appropriate ``StackTraceFilterInterface`` for the detected language.

    Args:
        cwd: Project root directory to inspect for language manifest files.

    Returns:
        A concrete ``StackTraceFilterInterface`` for the detected language.
    """
    language = detect_language(cwd)

    if language == "java":
        from specweaver.sandbox.language.core.java.stack_trace_filter import (
            JavaStackTraceFilter,
        )

        return JavaStackTraceFilter()

    if language == "kotlin":
        from specweaver.sandbox.language.core.kotlin.stack_trace_filter import (
            KotlinStackTraceFilter,
        )

        return KotlinStackTraceFilter()

    if language == "typescript":
        from specweaver.sandbox.language.core.typescript.stack_trace_filter import (
            TypeScriptStackTraceFilter,
        )

        return TypeScriptStackTraceFilter()

    if language == "rust":
        from specweaver.sandbox.language.core.rust.stack_trace_filter import (
            RustStackTraceFilter,
        )

        return RustStackTraceFilter()

    # Default: Python
    from specweaver.sandbox.language.core.python.stack_trace_filter import (
        PythonStackTraceFilter,
    )

    return PythonStackTraceFilter()
