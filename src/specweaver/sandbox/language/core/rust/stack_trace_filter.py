# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rust stack trace filter — strips _scenarios:: module frames from cargo test output.

Implements ``StackTraceFilterInterface`` for Rust/Cargo projects.
Rust integration test frames contain the module segment from the file path.
``RustScenarioConverter.output_path()`` produces ``tests/{stem}_scenarios.rs``,
which Cargo compiles to a crate named ``{stem}_scenarios``. Backtrace frames
then contain ``{stem}_scenarios::`` as a module segment.

We match on ``_scenarios::`` (trailing underscore + module separator) because:
  - It appears in both fully-qualified symbols and short frames
  - It is unlikely to appear in production code symbols
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.interfaces import StackTraceFilterInterface

# Matches the module segment Cargo derives from tests/{stem}_scenarios.rs
_SCENARIO_MARKER = "_scenarios::"


class RustStackTraceFilter(StackTraceFilterInterface):
    """Strips ``_scenarios::`` module frames from Rust cargo test backtraces."""

    def is_scenario_frame(self, line: str) -> bool:
        """Return True if the line contains a _scenarios:: symbol."""
        return _SCENARIO_MARKER in line

    def filter(self, stack_trace: str) -> str:
        """Remove scenario frames; preserve source frames and note lines."""
        if not stack_trace:
            return stack_trace
        return "".join(
            line
            for line in stack_trace.splitlines(keepends=True)
            if not self.is_scenario_frame(line)
        )
