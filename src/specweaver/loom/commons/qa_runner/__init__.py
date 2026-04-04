# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Shared test runner infrastructure — used by both atoms and tools.

Contains the language-agnostic QARunnerInterface ABC, result types,
and language-specific implementations (currently Python).
"""

from specweaver.loom.commons.qa_runner.interface import (
    ComplexityRunResult,
    ComplexityViolation,
    LintError,
    LintRunResult,
    QARunnerInterface,
    TestFailure,
    TestRunResult,
)
from specweaver.loom.commons.qa_runner.python import PythonQARunner
from specweaver.loom.commons.qa_runner.typescript import TypeScriptRunner

__all__ = [
    "ComplexityRunResult",
    "ComplexityViolation",
    "LintError",
    "LintRunResult",
    "PythonQARunner",
    "QARunnerInterface",
    "TestFailure",
    "TestRunResult",
    "TypeScriptRunner",
]
