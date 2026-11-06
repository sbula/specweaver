# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which ``StackTraceFilterInterface`` a run's language gets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.language.core.language_table import language_class

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import StackTraceFilterInterface

#: Each language's filter, as `module:class` under `sandbox.language.core`; imported on use.
_FILTERS = {
    "python": "python.stack_trace_filter:PythonStackTraceFilter",
    "java": "jvm.stack_trace_filter:JvmStackTraceFilter",
    "kotlin": "jvm.stack_trace_filter:JvmStackTraceFilter",
    "typescript": "typescript.stack_trace_filter:TypeScriptStackTraceFilter",
    "rust": "rust.stack_trace_filter:RustStackTraceFilter",
}


def create_stack_trace_filter(language: str) -> StackTraceFilterInterface:
    """The filter for the run's language; raises `ValueError` naming an unknown one."""
    trace_filter: StackTraceFilterInterface = language_class(
        _FILTERS, language, "stack trace filter"
    )()
    return trace_filter
