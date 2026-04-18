# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript stack trace filter — strips scenarios/generated/ frames from Jest traces.

Implements ``StackTraceFilterInterface`` for TypeScript/Jest projects.
Jest stack frames reference file paths directly:
  at Object.<anonymous> (scenarios/generated/payment.scenarios.test.ts:42:5)
The marker ``scenarios/generated/`` matches ``TypeScriptScenarioConverter.output_path()``.
"""

from __future__ import annotations

from specweaver.workspace.parsers.interfaces import StackTraceFilterInterface

_SCENARIO_MARKER = "scenarios/generated/"


class TypeScriptStackTraceFilter(StackTraceFilterInterface):
    """Strips ``scenarios/generated/`` path frames from Jest stack traces."""

    def is_scenario_frame(self, line: str) -> bool:
        """Return True if the line references a file in scenarios/generated/."""
        return _SCENARIO_MARKER in line

    def filter(self, stack_trace: str) -> str:
        """Remove scenario frames; preserve Jest error message and source frames."""
        if not stack_trace:
            return stack_trace
        return "".join(
            line
            for line in stack_trace.splitlines(keepends=True)
            if not self.is_scenario_frame(line)
        )
