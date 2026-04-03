# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Shared test runner infrastructure — used by both atoms and tools.

Contains the language-agnostic TestRunnerInterface ABC, result types,
and language-specific implementations (currently Python).
"""

from specweaver.loom.commons.test_runner.interface import (
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    TestFailure,
    TestRunnerInterface,
    TestRunResult,
)
from specweaver.loom.commons.test_runner.python import PythonTestRunner
from specweaver.loom.commons.test_runner.typescript import TypeScriptRunner

__all__ = [
    "ComplexityRunResult",
    "ComplexityViolation",
    "LintError",
    "LintRunResult",
    "PythonTestRunner",
    "TestFailure",
    "TestRunResult",
    "TestRunnerInterface",
    "TypeScriptRunner",
]
