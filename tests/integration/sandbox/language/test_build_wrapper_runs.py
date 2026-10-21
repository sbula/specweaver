# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The real executor starts a project's own `gradlew`, and the runner reads what it wrote.

Proves: D-INTL-08 FR-5

The wrapper here is a stand-in script that writes one JUnit report, so no Gradle and no network
are needed: what is real is the process start from the project folder, which a bare `gradlew`
never reached.

| Bucket | Case |
|---|---|
| Happy | the Kotlin and Java runners start `./gradlew` and count its one passing test |
| Boundary | not applicable — the command shapes are in the unit tests |
| Degradation | a wrapper that exits 1 and writes nothing is a failed run, never "0 tests" |
| Hostile | not applicable — the wrapper is the project's own file |
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform == "win32", reason="a POSIX shell script is not installed"),
]

_REPORT = (
    '<testsuite name="GreeterTest" tests="1" failures="0" errors="0" skipped="0">'
    '<testcase classname="com.example.GreeterTest" name="greets"/></testsuite>'
)


def _wrapper(root: Path, body: str) -> None:
    (root / "build.gradle.kts").write_text("", encoding="utf-8")
    script = root / "gradlew"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)


@pytest.mark.parametrize("runner_type", [KotlinRunner, JavaRunner])
def test_the_projects_wrapper_runs(tmp_path: Path, runner_type: type) -> None:
    _wrapper(
        tmp_path,
        f"mkdir -p build/test-results/test && echo '{_REPORT}' > build/test-results/test/TEST-g.xml",
    )

    result = runner_type(cwd=tmp_path, executor=SubprocessExecutor(cwd=tmp_path)).run_tests(".")

    assert (result.passed, result.total) == (1, 1), result


def test_a_wrapper_that_wrote_nothing_fails(tmp_path: Path) -> None:
    _wrapper(tmp_path, "exit 1")
    result = KotlinRunner(cwd=tmp_path, executor=SubprocessExecutor(cwd=tmp_path)).run_tests(".")

    assert result.passed == 0
    assert result.errors + result.failed >= 1, result
