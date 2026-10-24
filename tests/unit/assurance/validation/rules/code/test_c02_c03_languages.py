# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C02, C03 and the C03 hydrator judge a code file on its own language's tests.

Proves: TECH-078 FR-3

| Bucket | Case |
|---|---|
| Happy | C02 finds a Kotlin test; the hydrator runs a Rust file's test file |
| Boundary | C03 without hydration still names the test file it would judge |
| Degradation | C02 and C03 name the expected `OrdersTest.kt` when it is missing |
| Hostile | Go has no test convention: C02 and C03 skip and say so, never fail on a Python name |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c02_tests_exist import TestsExistRule
from specweaver.assurance.validation.rules.code.c03_tests_pass import TestsPassRule
from specweaver.core.flow.handlers.validation_hydrator import _hydrate_tests

if TYPE_CHECKING:
    from pathlib import Path


def _files(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")


def _rule(rule: type, root: Path, **context: object):
    built = rule()
    built.context = {"project_root": root, **context}
    return built


def test_c02_finds_a_kotlin_test(tmp_path: Path) -> None:
    _files(tmp_path, "src/main/kotlin/shop/Orders.kt", "src/test/kotlin/shop/OrdersTest.kt")

    result = _rule(TestsExistRule, tmp_path).check("", tmp_path / "src/main/kotlin/shop/Orders.kt")

    assert result.status == Status.PASS, result


def test_c02_names_the_missing_kotlin_test(tmp_path: Path) -> None:
    _files(tmp_path, "src/main/kotlin/shop/Orders.kt", "src/test/kotlin/shop/test_Orders.py")

    result = _rule(TestsExistRule, tmp_path).check("", tmp_path / "src/main/kotlin/shop/Orders.kt")

    assert result.status == Status.FAIL
    assert "OrdersTest.kt" in result.message


def test_c02_skips_a_language_without_a_convention(tmp_path: Path) -> None:
    _files(tmp_path, "main.go")

    result = _rule(TestsExistRule, tmp_path).check("", tmp_path / "main.go")

    assert result.status == Status.SKIP
    assert "no test convention for go" in result.message


def test_c03_skips_a_language_without_a_convention(tmp_path: Path) -> None:
    _files(tmp_path, "main.go")

    result = _rule(TestsPassRule, tmp_path).check("", tmp_path / "main.go")

    assert result.status == Status.SKIP
    assert "no test convention for go" in result.message


def test_c03_names_the_missing_kotlin_test_after_hydration(tmp_path: Path) -> None:
    _files(tmp_path, "src/main/kotlin/Orders.kt")

    result = _rule(TestsPassRule, tmp_path, qa_test_file=None).check(
        "", tmp_path / "src/main/kotlin/Orders.kt"
    )

    assert result.status == Status.SKIP
    assert "OrdersTest.kt" in result.message


def test_c03_finds_a_rust_test_without_hydration(tmp_path: Path) -> None:
    _files(tmp_path, "src/orders.rs", "tests/orders.rs")

    result = _rule(TestsPassRule, tmp_path).check("", tmp_path / "src/orders.rs")

    assert result.status == Status.FAIL
    assert "not hydrated" in result.message


def test_the_hydrator_runs_a_rust_files_test_file(tmp_path: Path) -> None:
    _files(tmp_path, "src/orders.rs", "tests/orders.rs")
    atom = MagicMock()
    atom.run.return_value = MagicMock(status=MagicMock(value="SUCCESS"), message="", exports={})

    _hydrate_tests(atom, tmp_path / "src/orders.rs", tmp_path)

    assert atom.run.call_args.args[0]["target"] == "tests/orders.rs"
