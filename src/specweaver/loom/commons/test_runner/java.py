# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Java test runner using Maven and Gradle."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.loom.commons.test_runner.interface import (
    CompileRunResult,
    ComplexityRunResult,
    DebugRunResult,
    LintRunResult,
    TestRunnerInterface,
    TestRunResult,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class JavaRunner(TestRunnerInterface):
    """Java compilation, testing, and linting pipeline."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
        coverage_threshold: int = 70,
    ) -> TestRunResult:
        raise NotImplementedError

    def run_linter(
        self,
        target: str,
        fix: bool = False,
    ) -> LintRunResult:
        raise NotImplementedError

    def run_complexity(
        self,
        target: str,
        max_complexity: int = 10,
    ) -> ComplexityRunResult:
        raise NotImplementedError

    def run_compiler(
        self,
        target: str,
    ) -> CompileRunResult:
        raise NotImplementedError

    def run_debugger(
        self,
        target: str,
        entrypoint: str,
    ) -> DebugRunResult:
        raise NotImplementedError
