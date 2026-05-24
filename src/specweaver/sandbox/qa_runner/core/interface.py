# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Language-agnostic test runner interface.

Defines the ABC that all language-specific runners must implement,
plus structured result types used across the system.

Currently supported: Python (via PythonQARunner).
Future: TypeScript, Go, etc.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from specweaver.commons.qa import (
    ArchitectureRunResult,
    ArchitectureViolation,
    CompileError,
    CompileRunResult,
    ComplexityRunResult,
    ComplexityViolation,
    DebugRunResult,
    LintError,
    LintRunResult,
    OutputEvent,
    TestFailure,
    TestRunResult,
)

if TYPE_CHECKING:
    from specweaver.commons.enums.dal import DALLevel

logger = logging.getLogger(__name__)

__all__ = [
    "ArchitectureRunResult",
    "ArchitectureViolation",
    "CompileError",
    "CompileRunResult",
    "ComplexityRunResult",
    "ComplexityViolation",
    "DebugRunResult",
    "LintError",
    "LintRunResult",
    "OutputEvent",
    "QARunnerInterface",
    "TestFailure",
    "TestRunResult",
]




# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class QARunnerInterface(ABC):
    """Language-agnostic interface for running tests, linting, and complexity checks.

    Each language implementation (Python, TypeScript, Go, etc.)
    subclasses this and provides concrete implementations.
    """

    __test__ = False

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Canonical language identifier for this runner.

        Returns:
            One of: ``"python"``, ``"java"``, ``"kotlin"``, ``"typescript"``, ``"rust"``.
        """

    @abstractmethod
    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
    ) -> TestRunResult:
        """Run tests and return structured results.

        Args:
            target: File or directory to test (relative to cwd).
            kind: Test marker/category — "unit", "integration", "e2e".
            scope: Module/service/class filter (e.g., "flow").
            timeout: Max seconds before aborting.
            coverage: Whether to measure code coverage.
            coverage_threshold: Minimum acceptable coverage %.

        Returns:
            TestRunResult with pass/fail counts and failure details.
        """

    @abstractmethod
    def run_linter(
        self,
        target: str,
        fix: bool = False,
    ) -> LintRunResult:
        """Run linter and return structured results.

        Args:
            target: File or directory to lint (relative to cwd).
            fix: Whether to auto-fix fixable issues.

        Returns:
            LintRunResult with error counts and details.
        """

    @abstractmethod
    def run_complexity(
        self,
        target: str,
        max_complexity: int = 10,
    ) -> ComplexityRunResult:
        """Run complexity checks and return structured results.

        Args:
            target: File or directory to check (relative to cwd).
            max_complexity: McCabe threshold — functions above this fail.

        Returns:
            ComplexityRunResult with violation counts and details.
        """

    @abstractmethod
    def run_compiler(
        self,
        target: str,
    ) -> CompileRunResult:
        """Run compilation/build and return structured results.

        Args:
            target: File or directory to compile (relative to cwd).

        Returns:
            CompileRunResult with error counts and details.
        """

    @abstractmethod
    def run_debugger(
        self,
        target: str,
        entrypoint: str,
    ) -> DebugRunResult:
        """Execute a process and stream runtime outputs.

        Args:
            target: File or directory to run.
            entrypoint: Command or specific script to use as entrypoint.

        Returns:
            DebugRunResult with exit records and DAP-mapped output events.
        """

    @abstractmethod
    def run_architecture_check(
        self,
        target: str,
        dal_level: DALLevel | None = None,
    ) -> ArchitectureRunResult:
        """Run architectural boundary checks and return structured results.

        Args:
            target: File or directory to compile (relative to cwd).
            dal_level: Active target strictness boundary resolving dynamic config payloads.

        Returns:
            ArchitectureRunResult with error counts and details.
        """
