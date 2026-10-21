# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's own build wrapper is started from the project folder, not looked up on PATH.

Proves: D-INTL-08 FR-5

A bare `gradlew` is searched on PATH only, so a project with a wrapper failed every build with
"not found". The wrapper is the normal way to run Gradle and Maven; the machine's own install may
be too old for the project (this workstation's Gradle is 4.4).

| Bucket | Case |
|---|---|
| Happy | Gradle and Maven wrappers start as `./gradlew` / `./mvnw` for every intent of both runners |
| Boundary | without a wrapper, the tool on PATH (`gradle`, `mvn`) runs |
| Degradation | not applicable — only the command is built here; the real start is the integration test |
| Hostile | a `gradlew` folder is not a wrapper; a Kotlin-DSL Gradle build is Gradle, not Maven |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.run_targets import build_launcher

if TYPE_CHECKING:
    from pathlib import Path


def _executor() -> MagicMock:
    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.return_value = SubprocessResult(
        exit_code=0, stdout="", stderr="", timed_out=False, duration_seconds=0.1
    )
    return executor


def _project(root: Path, build: str, wrapper: str | None) -> Path:
    (root / build).write_text("", encoding="utf-8")
    if wrapper:
        (root / wrapper).write_text("#!/bin/sh\n", encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("build", "wrapper", "expected"),
    [
        ("build.gradle", "gradlew", "./gradlew"),
        ("build.gradle", None, "gradle"),
        ("pom.xml", "mvnw", "./mvnw"),
        ("pom.xml", None, "mvn"),
    ],
)
def test_the_launcher(tmp_path: Path, build: str, wrapper: str | None, expected: str) -> None:
    _project(tmp_path, build, wrapper)
    tool = "gradle" if build.startswith("build.gradle") else "maven"

    assert build_launcher(tmp_path, tool) == expected


def test_a_wrapper_folder_is_no_wrapper(tmp_path: Path) -> None:
    (tmp_path / "gradlew").mkdir()

    assert build_launcher(tmp_path, "gradle") == "gradle"


_INTENTS = [
    ("run_tests", {"target": "."}),
    ("run_linter", {"target": "."}),
    ("run_compiler", {"target": "."}),
]


@pytest.mark.parametrize("runner_type", [JavaRunner, KotlinRunner])
@pytest.mark.parametrize(
    ("build", "wrapper"),
    [("build.gradle", "gradlew"), ("build.gradle.kts", "gradlew"), ("pom.xml", "mvnw")],
)
@pytest.mark.parametrize(("intent", "kwargs"), _INTENTS)
def test_every_intent_starts_the_wrapper(
    tmp_path: Path, runner_type: type, build: str, wrapper: str, intent: str, kwargs: dict
) -> None:
    _project(tmp_path, build, wrapper)
    executor = _executor()

    getattr(runner_type(cwd=tmp_path, executor=executor), intent)(**kwargs)

    assert executor.execute.call_args[0][0][0] == f"./{wrapper}"
