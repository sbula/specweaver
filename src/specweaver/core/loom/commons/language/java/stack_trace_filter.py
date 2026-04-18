# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Java stack trace filter — strips scenarios.generated. JVM frames.

Implements ``StackTraceFilterInterface`` for Java/JUnit 5 projects.
JVM frames are identified by the fully-qualified package prefix
``scenarios.generated.`` which matches ``JavaScenarioConverter.output_path()``
and the ``package scenarios.generated;`` declaration in generated files.
"""

from __future__ import annotations

from specweaver.workspace.parsers.interfaces import StackTraceFilterInterface

# JVM at-frame format: \tat package.ClassName.methodName(FileName.java:line)
_SCENARIO_PACKAGE_PREFIX = "scenarios.generated."


class JavaStackTraceFilter(StackTraceFilterInterface):
    """Strips JVM frames from the ``scenarios.generated`` package."""

    def is_scenario_frame(self, line: str) -> bool:
        """Return True if this is a JVM frame in the scenarios.generated package."""
        stripped = line.lstrip()
        return stripped.startswith("at ") and _SCENARIO_PACKAGE_PREFIX in stripped

    def filter(self, stack_trace: str) -> str:
        """Remove all JVM frames from scenarios.generated; preserve all others."""
        if not stack_trace:
            return stack_trace
        return "".join(
            line
            for line in stack_trace.splitlines(keepends=True)
            if not self.is_scenario_frame(line)
        )
