# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Language-agnostic QA result data models.

Resides in L0 commons to prevent domain/adapter layers from depending on the sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TestFailure:
    """A single test failure."""

    nodeid: str
    message: str
    stdout: str = ""
    stacktrace: str = ""
    rule_uri: str = ""

    __test__ = False


@dataclass(frozen=True)
class TestRunResult:
    """Structured result from running tests."""

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
    """A single linter finding."""

    file: str
    line: int
    code: str
    message: str
    rule_uri: str = ""

    __test__ = False


@dataclass(frozen=True)
class LintRunResult:
    """Structured result from running a linter."""

    error_count: int
    fixable_count: int
    fixed_count: int
    errors: list[LintError] = field(default_factory=list)

    __test__ = False


@dataclass(frozen=True)
class ComplexityViolation:
    """A single complexity threshold violation."""

    file: str
    line: int
    function: str
    complexity: int
    message: str

    __test__ = False


@dataclass(frozen=True)
class ComplexityRunResult:
    """Structured result from running complexity checks."""

    violation_count: int
    max_complexity: int
    violations: list[ComplexityViolation] = field(default_factory=list)

    __test__ = False


@dataclass(frozen=True)
class CompileError:
    """A single compilation error or warning."""

    file: str
    line: int
    column: int
    code: str
    message: str
    is_warning: bool = False

    __test__ = False


@dataclass(frozen=True)
class CompileRunResult:
    """Structured result from running a compiler."""

    error_count: int
    warning_count: int
    errors: list[CompileError] = field(default_factory=list)

    __test__ = False


@dataclass(frozen=True)
class OutputEvent:
    """A standard debug output event mapped from DAP protocol."""

    category: str
    output: str
    file: str = ""
    line: int = 0

    __test__ = False


@dataclass(frozen=True)
class DebugRunResult:
    """Structured result from a debug execution."""

    exit_code: int
    duration_seconds: float
    events: list[OutputEvent] = field(default_factory=list)

    __test__ = False


@dataclass(frozen=True)
class ArchitectureViolation:
    """A single architectural boundary finding."""

    file: str
    code: str
    message: str
    rule_uri: str = ""

    __test__ = False


@dataclass(frozen=True)
class ArchitectureRunResult:
    """Structured result from running an architectural linters."""

    violation_count: int
    violations: list[ArchitectureViolation] = field(default_factory=list)

    __test__ = False
