# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A code file's tests are found by its language's convention, one way.

Proves: TECH-078 FR-3

| Bucket | Case |
|---|---|
| Happy | Python, Java, Kotlin, TypeScript, JavaScript and Rust each find their test file |
| Boundary | a nearer `tests/` wins; a JVM test in a deeper package folder is found |
| Degradation | no test file names the one expected; a language with no convention says so |
| Hostile | a Rust test in a subfolder is not a test target; nothing above the project is searched |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.project_root import find_tests

if TYPE_CHECKING:
    from pathlib import Path


def _files(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")


@pytest.mark.parametrize(
    ("code", "test"),
    [
        ("src/orders.py", "tests/unit/test_orders.py"),
        ("src/main/java/com/shop/Orders.java", "src/test/java/com/shop/OrdersTest.java"),
        ("src/main/kotlin/com/shop/Orders.kt", "src/test/kotlin/com/shop/OrdersTest.kt"),
        ("src/orders.ts", "tests/orders.test.ts"),
        ("src/orders.js", "tests/shop/orders.test.js"),
        ("src/orders.rs", "tests/orders.rs"),
    ],
)
def test_each_language_finds_its_test_file(tmp_path: Path, code: str, test: str) -> None:
    _files(tmp_path, code, test)

    assert find_tests(tmp_path / code, tmp_path) == tmp_path / test


def test_a_nearer_tests_folder_wins(tmp_path: Path) -> None:
    _files(tmp_path, "pkg/src/orders.py", "pkg/tests/test_orders.py", "tests/test_orders.py")

    assert (
        find_tests(tmp_path / "pkg/src/orders.py", tmp_path)
        == tmp_path / "pkg/tests/test_orders.py"
    )


def test_a_jvm_test_in_another_package_folder_is_found(tmp_path: Path) -> None:
    _files(tmp_path, "src/main/java/a/Orders.java", "src/test/java/a/b/OrdersTest.java")

    found = find_tests(tmp_path / "src/main/java/a/Orders.java", tmp_path)

    assert found == tmp_path / "src/test/java/a/b/OrdersTest.java"


def test_no_test_file_names_the_one_expected(tmp_path: Path) -> None:
    _files(tmp_path, "src/main/kotlin/Orders.kt", "src/test/kotlin/Other.kt")

    assert find_tests(tmp_path / "src/main/kotlin/Orders.kt", tmp_path) == (
        "No test file 'OrdersTest.kt' found"
    )


def test_a_language_without_a_convention_says_so(tmp_path: Path) -> None:
    _files(tmp_path, "main.go", "tests/main_test.go")

    assert find_tests(tmp_path / "main.go", tmp_path) == "no test convention for go"


def test_a_rust_test_in_a_subfolder_is_not_one(tmp_path: Path) -> None:
    _files(tmp_path, "src/orders.rs", "tests/common/orders.rs")

    assert find_tests(tmp_path / "src/orders.rs", tmp_path) == "No test file 'orders.rs' found"


def test_nothing_above_the_project_is_searched(tmp_path: Path) -> None:
    _files(tmp_path, "tests/test_orders.py", "proj/src/orders.py")

    assert find_tests(tmp_path / "proj/src/orders.py", tmp_path / "proj") == (
        "No test file 'test_orders.py' found"
    )
