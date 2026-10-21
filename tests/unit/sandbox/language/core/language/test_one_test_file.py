# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test target that is one test file runs only that file's tests, on the JVM and in Rust.

Proves: D-INTL-08 FR-5

| Bucket | Case |
|---|---|
| Happy | Maven `-Dtest=<class>`, Gradle `--tests <class>`, `cargo test --test <stem>` |
| Boundary | a folder or the project runs everything; a test outside `src/test/<lang>/` filters by its simple class name; no package |
| Degradation | not applicable — the command is only built here; the real tools run in the integration test |
| Hostile | a target outside the test folders, or not a test file, is never turned into a filter |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.run_targets import jvm_test_class
from specweaver.sandbox.language.core.rust.runner import RustRunner

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("target", "language", "expected"),
    [
        ("src/test/java/com/example/GreetServiceTest.java", "java", "com.example.GreetServiceTest"),
        (
            "src/test/kotlin/com/example/GreetServiceTest.kt",
            "kotlin",
            "com.example.GreetServiceTest",
        ),
        ("src/test/java/GreetServiceTest.java", "java", "GreetServiceTest"),
        ("module/src/test/java/GreetServiceTest.java", "java", "GreetServiceTest"),
        ("tests/OtherTest.kt", "kotlin", "OtherTest"),
        (".", "java", None),
        ("src/", "java", None),
        ("src/test/java/", "java", None),
        ("src/main/java/com/example/GreetService.java", "java", None),
        ("README.md", "java", None),
    ],
)
def test_the_class_a_target_names(target: str, language: str, expected: str | None) -> None:
    assert jvm_test_class(target, language) == expected


def _executor(stdout: str = "") -> MagicMock:
    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.return_value = SubprocessResult(
        exit_code=0, stdout=stdout, stderr="", timed_out=False, duration_seconds=0.1
    )
    return executor


def _command(executor: MagicMock) -> list[str]:
    return list(executor.execute.call_args[0][0])


@pytest.mark.parametrize(
    ("runner_type", "language"), [(JavaRunner, "java"), (KotlinRunner, "kotlin")]
)
def test_maven_runs_one_class(tmp_path: Path, runner_type: type, language: str) -> None:
    (tmp_path / "pom.xml").write_text("<project/>")
    executor = _executor()

    runner_type(cwd=tmp_path, executor=executor).run_tests(
        target=f"src/test/{language}/com/example/GreetServiceTest.{'java' if language == 'java' else 'kt'}"
    )

    assert "-Dtest=com.example.GreetServiceTest" in _command(executor)


@pytest.mark.parametrize(
    ("runner_type", "language"), [(JavaRunner, "java"), (KotlinRunner, "kotlin")]
)
def test_gradle_runs_one_class(tmp_path: Path, runner_type: type, language: str) -> None:
    (tmp_path / "build.gradle").write_text("")
    executor = _executor()

    runner_type(cwd=tmp_path, executor=executor).run_tests(
        target=f"src/test/{language}/GreetServiceTest.{'java' if language == 'java' else 'kt'}"
    )

    command = _command(executor)
    assert command[command.index("--tests") + 1] == "GreetServiceTest"


@pytest.mark.parametrize(
    ("runner_type", "build"), [(JavaRunner, "pom.xml"), (KotlinRunner, "build.gradle")]
)
def test_a_folder_target_runs_everything(tmp_path: Path, runner_type: type, build: str) -> None:
    (tmp_path / build).write_text("")
    executor = _executor()

    runner_type(cwd=tmp_path, executor=executor).run_tests(target="src/")

    command = _command(executor)
    assert "--tests" not in command
    assert not any(part.startswith("-Dtest") for part in command)


_CARGO_OK = "running 1 test\ntest t ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored\n"


def test_cargo_runs_one_test_file(tmp_path: Path) -> None:
    executor = _executor(_CARGO_OK)

    RustRunner(cwd=tmp_path, executor=executor).run_tests(target="tests/greet_service.rs")

    assert _command(executor)[:4] == ["cargo", "test", "--test", "greet_service"]


@pytest.mark.parametrize("target", [".", "src/", "tests/", "src/greet_service.rs"])
def test_cargo_runs_the_crate_for_anything_else(tmp_path: Path, target: str) -> None:
    executor = _executor(_CARGO_OK)

    RustRunner(cwd=tmp_path, executor=executor).run_tests(target=target)

    assert "--test" not in _command(executor)
