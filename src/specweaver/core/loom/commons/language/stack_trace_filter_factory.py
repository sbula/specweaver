# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Factory that creates the correct ``StackTraceFilterInterface`` for a project."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.loom.commons.language._detect import detect_language

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.loom.commons.language.interfaces import StackTraceFilterInterface


def create_stack_trace_filter(cwd: Path) -> StackTraceFilterInterface:
    """Create the appropriate ``StackTraceFilterInterface`` for the detected language.

    Args:
        cwd: Project root directory to inspect for language manifest files.

    Returns:
        A concrete ``StackTraceFilterInterface`` for the detected language.
    """
    language = detect_language(cwd)

    if language == "java":
        from specweaver.core.loom.commons.language.java.stack_trace_filter import (
            JavaStackTraceFilter,
        )

        return JavaStackTraceFilter()

    if language == "kotlin":
        from specweaver.core.loom.commons.language.kotlin.stack_trace_filter import (
            KotlinStackTraceFilter,
        )

        return KotlinStackTraceFilter()

    if language == "typescript":
        from specweaver.core.loom.commons.language.typescript.stack_trace_filter import (
            TypeScriptStackTraceFilter,
        )

        return TypeScriptStackTraceFilter()

    if language == "rust":
        from specweaver.core.loom.commons.language.rust.stack_trace_filter import (
            RustStackTraceFilter,
        )

        return RustStackTraceFilter()

    # Default: Python
    from specweaver.core.loom.commons.language.python.stack_trace_filter import (
        PythonStackTraceFilter,
    )

    return PythonStackTraceFilter()
