# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Language-agnostic test runner interface.

Defines the ABC that all language-specific runners must implement,
plus structured result types used across the system.

Currently supported: Python (via PythonTestRunner).
Future: TypeScript, Go, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Result types (language-agnostic)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TestFailure:
    """A single test failure.

    Attributes:
        nodeid: Test identifier (e.g., "tests/test_a.py::test_x").
        message: Failure message / assertion error.
        stdout: Captured stdout from the test, if any.
        stacktrace: Detailed stacktrace from the test failure.
        rule_uri: Optional URI to the documentation for the error.
    """

    nodeid: str
    message: str
    stdout: str = ""
    stacktrace: str = ""
    rule_uri: str = ""

    __test__ = False


@dataclass(frozen=True)
class TestRunResult:
    """Structured result from running tests.

    Attributes:
        passed: Number of passing tests.
        failed: Number of failing tests.
        errors: Number of collection/setup errors.
        skipped: Number of skipped tests.
        total: Total test count (passed + failed + errors + skipped).
        failures: Details of each failure.
        coverage_pct: Code coverage percentage (None if not measured).
        duration_seconds: Wall-clock time for the test run.
    """

    passed: int
    failed: int
    errors: int
    skipped: int
    total: int
    failures: list[TestFailure] = field(default_factory=list)
    coverage_pct: float | None = None
    duration_seconds: float = 0.0

    __test__ = False


@dataclass(frozen=True)
class LintError:
    """A single linter finding.

    Attributes:
        file: Relative file path.
        line: Line number.
        code: Rule code (e.g., "E501").
        message: Human-readable description.
        rule_uri: Optional URI to the documentation for the rule.
    """

    file: str
    line: int
    code: str
    message: str
    rule_uri: str = ""

    __test__ = False


@dataclass(frozen=True)
class LintRunResult:
    """Structured result from running a linter.

    Attributes:
        error_count: Total number of lint errors.
        fixable_count: How many errors are auto-fixable.
        fixed_count: How many errors were actually fixed (when fix=True).
        errors: Details of each error.
    """

    error_count: int
    fixable_count: int
    fixed_count: int
    errors: list[LintError] = field(default_factory=list)

    __test__ = False


@dataclass(frozen=True)
class ComplexityViolation:
    """A single complexity threshold violation.

    Attributes:
        file: Relative file path.
        line: Line number.
        function: Function/method name.
        complexity: Measured McCabe complexity score.
        message: Human-readable description.
    """

    file: str
    line: int
    function: str
    complexity: int
    message: str

    __test__ = False


@dataclass(frozen=True)
class ComplexityRunResult:
    """Structured result from running complexity checks.

    Attributes:
        violation_count: Number of functions exceeding the threshold.
        max_complexity: The configured threshold.
        violations: Details of each violation.
    """

    violation_count: int
    max_complexity: int
    violations: list[ComplexityViolation] = field(default_factory=list)

    __test__ = False


@dataclass(frozen=True)
class CompileError:
    """A single compilation error or warning.

    Attributes:
        file: Relative file path.
        line: Line number.
        column: Column number.
        code: Error code (e.g., TS1005, E0432).
        message: Human-readable description.
        is_warning: True if warning, False if hard error.
    """

    file: str
    line: int
    column: int
    code: str
    message: str
    is_warning: bool = False

    __test__ = False


@dataclass(frozen=True)
class CompileRunResult:
    """Structured result from running a compiler.

    Attributes:
        error_count: Total hard errors.
        warning_count: Total warnings.
        errors: Details of each compilation error.
    """

    error_count: int
    warning_count: int
    errors: list[CompileError] = field(default_factory=list)

    __test__ = False


@dataclass(frozen=True)
class OutputEvent:
    """A standard debug output event mapped from DAP protocol.

    Attributes:
        category: Output channel (stdout, stderr, console).
        output: Raw text output.
        file: Source file associated with the output block.
        line: Associated line number.
    """

    category: str
    output: str
    file: str = ""
    line: int = 0

    __test__ = False


@dataclass(frozen=True)
class DebugRunResult:
    """Structured result from a debug execution.

    Attributes:
        exit_code: Process exit code.
        duration_seconds: Wall-clock duration of the run.
        events: Streamed output events.
    """

    exit_code: int
    duration_seconds: float
    events: list[OutputEvent] = field(default_factory=list)

    __test__ = False


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class TestRunnerInterface(ABC):
    """Language-agnostic interface for running tests, linting, and complexity checks.

    Each language implementation (Python, TypeScript, Go, etc.)
    subclasses this and provides concrete implementations.
    """

    __test__ = False

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
