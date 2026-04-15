# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Kotlin stack trace filter — strips scenarios.generated JVM frames.

Implements ``StackTraceFilterInterface`` for Kotlin/JUnit 5 projects.
Uses the same ``scenarios.generated.`` package prefix as the Java filter
because Kotlin compiles to JVM bytecode and produces identical frame format:
  \tat scenarios.generated.PaymentScenariosTest.testChargeScenarios(PaymentScenariosTest.kt:42)
"""

from __future__ import annotations

from specweaver.core.loom.commons.language.interfaces import StackTraceFilterInterface

_SCENARIO_PACKAGE_PREFIX = "scenarios.generated."


class KotlinStackTraceFilter(StackTraceFilterInterface):
    """Strips JVM frames from the ``scenarios.generated`` package (Kotlin source)."""

    def is_scenario_frame(self, line: str) -> bool:
        """Return True if this is a JVM frame referencing a Kotlin scenario file."""
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
