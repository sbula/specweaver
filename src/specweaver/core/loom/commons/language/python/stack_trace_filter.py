# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python stack trace filter — strips scenarios/generated/ frames from pytest tracebacks.

Implements ``StackTraceFilterInterface`` for Python projects.
Scenario frames are identified by the path segment ``scenarios/generated/``
which matches ``PythonScenarioConverter.output_path()`` convention.
"""

from __future__ import annotations

from specweaver.workspace.parsers.interfaces import StackTraceFilterInterface

_SCENARIO_MARKER = "scenarios/generated/"


class PythonStackTraceFilter(StackTraceFilterInterface):
    """Strips ``scenarios/generated/`` path frames from pytest stack traces."""

    def is_scenario_frame(self, line: str) -> bool:
        """Return True if the line references a file in scenarios/generated/."""
        return _SCENARIO_MARKER in line

    def filter(self, stack_trace: str) -> str:
        """Remove scenario frames.

        Also removes the line immediately following a scenario frame if it is
        a code-context line (indented ≥4 spaces, not starting with ``File``).
        This prevents orphaned ``result = ...`` lines appearing in the output.
        """
        if not stack_trace:
            return stack_trace

        output_lines: list[str] = []
        skip_next = False
        for line in stack_trace.splitlines(keepends=True):
            if skip_next:
                # Skip the code context line that follows the scenario frame
                skip_next = False
                continue
            if self.is_scenario_frame(line):
                skip_next = True
                continue
            output_lines.append(line)

        return "".join(output_lines)
