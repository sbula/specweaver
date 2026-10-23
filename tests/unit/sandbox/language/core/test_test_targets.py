# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test target runs exactly what it names: one test, one file, one folder, the project.

Proves: TECH-078 FR-7

| Bucket | Case |
|---|---|
| Happy | each size turns into the tool's own filter: pytest, Gradle, Maven, cargo |
| Boundary | a folder with subfolders; the test root is the project; `./` and a trailing `/`; `lib.rs`, `mod.rs`, `main.rs` |
| Degradation | a run that ran no test fails, naming the target; a JVM folder outside the test sources fails before any build |
| Hostile | a Windows path with a drive letter; `::` with no name; a name full of regex characters goes through as written |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.language.core.run_targets import (
    TargetError,
    cargo_test_args,
    jvm_test_args,
    parse_target,
)
from specweaver.sandbox.language.core.rust.runner import RustRunner

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("target", "path", "name", "kind"),
    [
        ("tests/test_a.py::test_one", "tests/test_a.py", "test_one", "test"),
        ("tests/test_a.py", "tests/test_a.py", "", "file"),
        ("tests/unit", "tests/unit", "", "folder"),
        ("tests/unit/", "tests/unit", "", "folder"),
        ("./tests/unit/", "tests/unit", "", "folder"),
        ("", "", "", "project"),
        (".", "", "", "project"),
        ("./", "", "", "project"),
        ("C:\\p\\src\\test\\java\\T.java::m", "C:/p/src/test/java/T.java", "m", "test"),
        ("tests/test_a.py::", "tests/test_a.py", "", "file"),
        ("tests/test_a.py::TestX::test_y", "tests/test_a.py", "TestX::test_y", "test"),
    ],
)
def test_a_target_says_its_size(target: str, path: str, name: str, kind: str) -> None:
    parsed = parse_target(target)

    assert (parsed.path, parsed.name, parsed.kind) == (path, name, kind)


_JVM = [
    # (target, gradle args, maven args)
    (
        "src/test/java/com/acme/OrderTest.java::places",
        ["--tests", "com.acme.OrderTest.places"],
        ["-Dtest=com.acme.OrderTest#places"],
    ),
    (
        "src/test/java/com/acme/OrderTest.java",
        ["--tests", "com.acme.OrderTest"],
        ["-Dtest=com.acme.OrderTest"],
    ),
    ("src/test/java/com/acme", ["--tests", "com.acme.*"], ["-Dtest=com/acme/**/*"]),
    ("src/test/java/com/acme/", ["--tests", "com.acme.*"], ["-Dtest=com/acme/**/*"]),
    ("src/test/java", [], []),
    ("src/main/java/com/acme", ["--tests", "com.acme.*"], ["-Dtest=com/acme/**/*"]),
    ("src/", [], []),
    (".", [], []),
]


@pytest.mark.parametrize(("target", "gradle", "maven"), _JVM)
def test_jvm_filters_at_every_size(target: str, gradle: list[str], maven: list[str]) -> None:
    parsed = parse_target(target)

    assert jvm_test_args(parsed, "java", "gradle") == gradle
    assert jvm_test_args(parsed, "java", "maven")[: len(maven)] == maven


def test_maven_with_a_filter_leaves_the_empty_verdict_to_specweaver() -> None:
    args = jvm_test_args(parse_target("src/test/java/com/acme"), "java", "maven")

    assert "-Dsurefire.failIfNoSpecifiedTests=false" in args


def test_a_kotlin_folder_uses_its_own_test_root() -> None:
    assert jvm_test_args(parse_target("src/test/kotlin/com/acme"), "kotlin", "gradle") == [
        "--tests",
        "com.acme.*",
    ]


def test_a_jvm_folder_outside_the_test_sources_is_refused() -> None:
    with pytest.raises(TargetError, match="lib/helpers"):
        jvm_test_args(parse_target("lib/helpers"), "java", "gradle")


_CARGO = [
    ("tests/orders.rs::places", ["--test", "orders", "--", "places", "--exact"]),
    ("tests/orders.rs", ["--test", "orders"]),
    ("tests", ["--test", "*"]),
    ("tests/", ["--test", "*"]),
    ("tests/orders", ["--test", "orders"]),
    ("src/orders.rs::places", ["--lib", "--", "orders::tests::places", "--exact"]),
    ("src/orders.rs", ["--lib", "orders::"]),
    ("src/shop/orders.rs", ["--lib", "shop::orders::"]),
    ("src/shop/mod.rs", ["--lib", "shop::"]),
    ("src/shop", ["--lib", "shop::"]),
    ("src/", ["--lib"]),
    ("src/lib.rs", ["--lib"]),
    ("src/lib.rs::places", ["--lib", "--", "tests::places", "--exact"]),
    ("src/main.rs", ["--bins"]),
    ("src/tests/helpers.rs", ["--lib", "tests::helpers::"]),
    ("src/main.rs::starts", ["--bins", "--", "tests::starts", "--exact"]),
    (".", []),
]


@pytest.mark.parametrize(("target", "args"), _CARGO)
def test_cargo_filters_at_every_size(target: str, args: list[str]) -> None:
    assert cargo_test_args(parse_target(target)) == args


def test_a_cargo_target_outside_src_and_tests_is_refused() -> None:
    with pytest.raises(TargetError, match=r"benches/speed\.rs"):
        cargo_test_args(parse_target("benches/speed.rs"))


def test_a_name_with_regex_characters_goes_through_as_written() -> None:
    args = cargo_test_args(parse_target("tests/orders.rs::place (EUR)*"))

    assert args[args.index("--") + 1] == "place (EUR)*"


# --- the runners -------------------------------------------------------------------------------


def _executor(stdout: str = "", exit_code: int = 0) -> MagicMock:
    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.return_value = SubprocessResult(
        exit_code=exit_code, stdout=stdout, stderr="", timed_out=False, duration_seconds=0.1
    )
    return executor


def _command(executor: MagicMock) -> list[str]:
    return list(executor.execute.call_args[0][0])


def test_python_runs_one_named_test_without_the_marker(tmp_path: Path) -> None:
    executor = _executor("1 passed in 0.01s\n")

    PythonQARunner(cwd=tmp_path, executor=executor).run_tests(
        target="tests/test_a.py::test_one", kind="unit"
    )

    command = _command(executor)
    assert "tests/test_a.py::test_one" in command
    assert command[command.index("pytest") + 1 :].count("-m") == 0


def test_python_keeps_the_marker_for_a_folder(tmp_path: Path) -> None:
    executor = _executor("1 passed in 0.01s\n")

    PythonQARunner(cwd=tmp_path, executor=executor).run_tests(target="tests/unit", kind="unit")

    assert _command(executor)[-2:] == ["-m", "unit"]


def _no_test_message(result: object) -> str:
    assert result.errors + result.failed >= 1, result  # type: ignore[attr-defined]
    return " ".join(f.message for f in result.failures)  # type: ignore[attr-defined]


def test_python_with_no_test_fails_naming_the_target(tmp_path: Path) -> None:
    executor = _executor("no tests ran in 0.01s\n", exit_code=5)

    result = PythonQARunner(cwd=tmp_path, executor=executor).run_tests(target="tests/missing")

    assert "tests/missing" in _no_test_message(result)


@pytest.mark.parametrize(
    ("runner_type", "build", "folder"),
    [
        (JavaRunner, "pom.xml", "src/test/java/com/acme"),
        (KotlinRunner, "build.gradle", "src/test/kotlin/com/acme"),
    ],
)
def test_a_jvm_run_with_no_test_fails_naming_the_target(
    tmp_path: Path, runner_type: type, build: str, folder: str
) -> None:
    (tmp_path / build).write_text("")
    executor = _executor("BUILD SUCCESS")

    result = runner_type(cwd=tmp_path, executor=executor).run_tests(target=folder)

    executor.execute.assert_called_once()
    assert folder in _no_test_message(result)


@pytest.mark.parametrize(
    ("runner_type", "build"), [(JavaRunner, "pom.xml"), (KotlinRunner, "build.gradle")]
)
def test_a_jvm_folder_outside_the_test_sources_runs_no_build(
    tmp_path: Path, runner_type: type, build: str
) -> None:
    (tmp_path / build).write_text("")
    executor = _executor()

    result = runner_type(cwd=tmp_path, executor=executor).run_tests(target="lib/helpers")

    assert "lib/helpers" in _no_test_message(result)
    executor.execute.assert_not_called()


@pytest.mark.parametrize(
    ("runner_type", "language"), [(JavaRunner, "java"), (KotlinRunner, "kotlin")]
)
def test_the_jvm_runners_pass_a_named_test(
    tmp_path: Path, runner_type: type, language: str
) -> None:
    (tmp_path / "build.gradle").write_text("")
    executor = _executor()
    ext = "java" if language == "java" else "kt"

    runner_type(cwd=tmp_path, executor=executor).run_tests(
        target=f"src/test/{language}/com/acme/OrderTest.{ext}::places"
    )

    command = _command(executor)
    assert command[command.index("--tests") + 1] == "com.acme.OrderTest.places"


_CARGO_NONE = "running 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 3 filtered out\n"


def test_cargo_with_no_test_fails_naming_the_target(tmp_path: Path) -> None:
    result = RustRunner(cwd=tmp_path, executor=_executor(_CARGO_NONE)).run_tests(
        target="tests/orders.rs::gone"
    )

    assert "tests/orders.rs::gone" in _no_test_message(result)


def test_cargo_runner_passes_the_exact_name(tmp_path: Path) -> None:
    executor = _executor("test result: ok. 1 passed; 0 failed; 0 ignored\n")

    RustRunner(cwd=tmp_path, executor=executor).run_tests(target="tests/orders.rs::places")

    assert _command(executor) == [
        "cargo",
        "test",
        "--no-fail-fast",
        "--test",
        "orders",
        "--",
        "places",
        "--exact",
    ]


def test_a_cargo_target_outside_src_and_tests_runs_nothing(tmp_path: Path) -> None:
    executor = _executor()

    result = RustRunner(cwd=tmp_path, executor=executor).run_tests(target="benches/speed.rs")

    assert "benches/speed.rs" in _no_test_message(result)
    executor.execute.assert_not_called()


def test_a_broken_jvm_build_names_the_target_and_what_the_build_said(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("")
    executor = _executor("[ERROR] COMPILATION ERROR : OrderTest.java", exit_code=1)

    result = JavaRunner(cwd=tmp_path, executor=executor).run_tests(
        target="src/test/java/com/acme/OrderTest.java"
    )

    message = _no_test_message(result)
    assert "src/test/java/com/acme/OrderTest.java" in message
    assert "COMPILATION ERROR" in message


def test_an_empty_python_run_under_a_marker_says_so(tmp_path: Path) -> None:
    executor = _executor("3 deselected in 0.01s\n", exit_code=5)

    result = PythonQARunner(cwd=tmp_path, executor=executor).run_tests(
        target="tests/unit", kind="unit"
    )

    assert "marker 'unit'" in _no_test_message(result)
