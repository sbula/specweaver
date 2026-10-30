# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""JVM stack trace filter — strips scenarios.generated. frames, for Java and Kotlin.

Implements ``StackTraceFilterInterface`` for Java and Kotlin JUnit 5 projects. Kotlin compiles to
JVM bytecode, so both give the same frame format, e.g.
``\tat scenarios.generated.PaymentScenariosTest.testCharge(PaymentScenariosTest.kt:42)``.
Frames are identified by the package prefix ``scenarios.generated.``, which matches both scenario
converters' ``output_path()`` and the ``package scenarios.generated`` declaration they write.
"""

from __future__ import annotations

import logging

from specweaver.workspace.ast.parsers.interfaces import StackTraceFilterInterface

logger = logging.getLogger(__name__)

# JVM at-frame format: \tat package.ClassName.methodName(FileName.java:line)
_SCENARIO_PACKAGE_PREFIX = "scenarios.generated."


class JvmStackTraceFilter(StackTraceFilterInterface):
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
